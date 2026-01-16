#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator

from loralink_mllc.codecs import create_codec, payload_schema_hash
from loralink_mllc.codecs.bam_artifacts import BamArtifacts
from loralink_mllc.config.runspec import CodecSpec


def _require_numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise SystemExit(
            "numpy is required. Install with `python -m pip install -e .[bam]`."
        ) from exc
    return np


def _split_accept(window_id: int, *, train_ratio: float, split_seed: int) -> bool:
    if train_ratio >= 1.0:
        return True
    if train_ratio <= 0.0:
        return False
    digest = hashlib.sha256(f"{split_seed}:{window_id}".encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], byteorder="big", signed=False) / (2**64)
    return bucket < train_ratio


def _iter_dataset_windows(
    dataset_path: Path,
    *,
    expected_len: int,
    max_samples: int | None,
    subset: str,
    train_ratio: float,
    split_seed: int,
) -> Iterator[list[float]]:
    count = 0
    with dataset_path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_no}: {exc}") from exc
            window = record.get("window")
            if not isinstance(window, list):
                raise ValueError(f"dataset line {line_no}: missing 'window' list")
            if len(window) != expected_len:
                actual_len = len(window)
                raise ValueError(
                    f"dataset line {line_no}: window_len {actual_len} != expected {expected_len}"
                )
            window_id = record.get("window_id")
            if window_id is None:
                window_id = line_no - 1
            window_id = int(window_id)
            in_train = _split_accept(window_id, train_ratio=train_ratio, split_seed=split_seed)
            if subset == "train" and not in_train:
                continue
            if subset == "holdout" and in_train:
                continue
            yield [float(v) for v in window]
            count += 1
            if max_samples is not None and count >= max_samples:
                return


def _group_indices_12d(window_W: int) -> dict[str, list[int]]:
    groups = {"gps": [0, 1, 2], "accel": [3, 4, 5], "gyro": [6, 7, 8], "rpy": [9, 10, 11]}
    out: dict[str, list[int]] = {k: [] for k in groups}
    for t in range(window_W):
        offset = t * 12
        for name, base in groups.items():
            out[name].extend(offset + idx for idx in base)
    return out


@dataclass
class _Agg:
    abs_sum: float = 0.0
    sq_sum: float = 0.0
    n: int = 0

    def update(self, abs_sum: float, sq_sum: float, n: int) -> None:
        self.abs_sum += float(abs_sum)
        self.sq_sum += float(sq_sum)
        self.n += int(n)

    def mae(self) -> float:
        return (self.abs_sum / self.n) if self.n else 0.0

    def mse(self) -> float:
        return (self.sq_sum / self.n) if self.n else 0.0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Evaluate BAM reconstruction on dataset_raw.jsonl.")
    p.add_argument("--dataset", required=True, help="Path to dataset_raw.jsonl")
    p.add_argument("--bam-manifest", required=True, help="Path to bam_manifest.json")
    p.add_argument("--max-samples", type=int, default=None, help="Limit dataset windows (debug)")
    p.add_argument(
        "--subset",
        default="all",
        choices=["all", "train", "holdout"],
        help="Dataset subset to evaluate (default: all)",
    )
    p.add_argument(
        "--train-ratio",
        type=float,
        default=1.0,
        help=(
            "Train/holdout split ratio in (0, 1]. Uses a deterministic window_id hash; "
            "holdout is (1-ratio). Default evaluates all windows."
        ),
    )
    p.add_argument(
        "--split-seed",
        type=int,
        default=0,
        help="Seed for deterministic split hashing (default: 0)",
    )
    p.add_argument("--out", default=None, help="Write report JSON to this path (default: print)")
    return p


def main() -> int:
    args = build_parser().parse_args()
    dataset = Path(args.dataset)
    bam_manifest_path = Path(args.bam_manifest)
    if not dataset.exists():
        raise SystemExit(f"dataset not found: {dataset}")
    if not bam_manifest_path.exists():
        raise SystemExit(f"bam manifest not found: {bam_manifest_path}")
    if not (0.0 < float(args.train_ratio) <= 1.0):
        raise SystemExit("--train-ratio must be in (0, 1]")

    artifacts = BamArtifacts.load(bam_manifest_path)
    input_len = artifacts.expected_input_len()
    codec_spec = CodecSpec(id="bam", version="0", params={"manifest_path": str(bam_manifest_path)})
    codec = create_codec(codec_spec)

    np = _require_numpy()
    overall = _Agg()
    by_group: dict[str, _Agg] = {}
    groups = _group_indices_12d(artifacts.window_W) if artifacts.input_dims == 12 else None
    if groups is not None:
        by_group = {name: _Agg() for name in groups}

    samples = 0
    payload_bytes_seen: int | None = None
    sat_count = 0
    sat_total = 0
    for window in _iter_dataset_windows(
        dataset,
        expected_len=input_len,
        max_samples=args.max_samples,
        subset=str(args.subset),
        train_ratio=float(args.train_ratio),
        split_seed=int(args.split_seed),
    ):
        payload = codec.encode(window)
        packing = artifacts.packing.lower()
        if packing in {"int8", "int16"}:
            dtype = np.int8 if packing == "int8" else np.int16
            info = np.iinfo(dtype)
            raw = np.frombuffer(payload, dtype=dtype)
            sat_count += int(((raw == info.min) | (raw == info.max)).sum())
            sat_total += int(raw.size)
        recon = codec.decode(payload)
        truth = np.asarray(window, dtype=np.float32)
        recon_vec = np.asarray(recon, dtype=np.float32)
        if truth.shape != recon_vec.shape:
            raise RuntimeError("reconstruction length mismatch")

        diff = recon_vec - truth
        abs_diff = np.abs(diff)
        sq_diff = diff**2
        overall.update(abs_diff.sum(), sq_diff.sum(), diff.size)
        if groups is not None:
            for name, idxs in groups.items():
                idx = np.asarray(idxs, dtype=np.int64)
                by_group[name].update(abs_diff[idx].sum(), sq_diff[idx].sum(), idx.size)

        samples += 1
        if payload_bytes_seen is None:
            payload_bytes_seen = len(payload)

    report: Dict[str, Any] = {
        "dataset": str(dataset),
        "bam_manifest": str(bam_manifest_path),
        "payload_schema": codec.payload_schema(),
        "payload_schema_hash": payload_schema_hash(codec.payload_schema()),
        "expected_payload_bytes": artifacts.expected_payload_bytes(),
        "payload_bytes_seen": payload_bytes_seen,
        "samples": samples,
        "saturation": (
            {
                "count": sat_count,
                "total": sat_total,
                "rate": (sat_count / sat_total) if sat_total else 0.0,
            }
            if sat_total
            else None
        ),
        "overall": {"mae": overall.mae(), "mse": overall.mse()},
        "by_group": (
            {name: {"mae": agg.mae(), "mse": agg.mse()} for name, agg in by_group.items()}
            if groups is not None
            else None
        ),
    }

    out = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
