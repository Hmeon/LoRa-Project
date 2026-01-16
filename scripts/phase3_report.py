#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Sequence

from loralink_mllc.codecs import create_codec, payload_schema_hash
from loralink_mllc.config.runspec import RunSpec
from loralink_mllc.experiments.metrics import compute_metrics, load_events


def _to_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_no}: {exc}") from exc


def _load_dataset_index(
    dataset_path: Path, *, run_ids: set[str]
) -> dict[str, dict[int, list[float]]]:
    out: dict[str, dict[int, list[float]]] = {run_id: {} for run_id in run_ids}
    for record in _iter_jsonl(dataset_path):
        run_id = str(record.get("run_id", ""))
        if run_id not in run_ids:
            continue
        window_id = _to_int(record.get("window_id"))
        window = record.get("window")
        if window_id is None or not isinstance(window, list):
            continue
        out[run_id][window_id] = [float(v) for v in window]
    return out


def _find_runspec(events: Iterable[Dict[str, Any]]) -> RunSpec | None:
    for event in events:
        if event.get("event") != "run_start":
            continue
        runspec = event.get("runspec")
        if not isinstance(runspec, dict):
            continue
        spec = RunSpec.from_dict(runspec)
        spec.validate()
        return spec
    return None


def _infer_acked_window_ids(events: List[Dict[str, Any]]) -> List[int]:
    tx_events = [e for e in events if e.get("role") == "tx"]
    tx_events.sort(key=lambda e: _to_int(e.get("ts_ms")) or 0)

    inflight: dict[int, int] = {}
    next_window_id = 0
    acked: list[int] = []
    for event in tx_events:
        kind = event.get("event")
        if kind == "tx_sent":
            seq = _to_int(event.get("seq"))
            if seq is None:
                continue
            attempt = _to_int(event.get("attempt")) or 1
            window_id = _to_int(event.get("window_id"))
            if attempt == 1:
                if window_id is None:
                    window_id = next_window_id
                    next_window_id += 1
                inflight[seq] = window_id
            else:
                if window_id is not None:
                    inflight.setdefault(seq, window_id)
        elif kind == "ack_received":
            ack_seq = _to_int(event.get("ack_seq"))
            if ack_seq is None:
                continue
            window_id = _to_int(event.get("window_id"))
            if window_id is None:
                window_id = inflight.get(ack_seq)
            if window_id is not None:
                acked.append(window_id)
            inflight.pop(ack_seq, None)
        elif kind == "tx_failed":
            seq = _to_int(event.get("seq"))
            if seq is None:
                continue
            inflight.pop(seq, None)
    return acked


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


def _compute_roundtrip_errors(
    *,
    codec,
    truth_windows: Mapping[int, Sequence[float]],
    window_ids: Sequence[int],
    dims: int,
    window_W: int,
) -> dict[str, object] | None:
    overall = _Agg()
    groups = _group_indices_12d(window_W) if dims == 12 else None
    by_group = {name: _Agg() for name in groups} if groups is not None else None
    samples = 0
    payload_bytes_seen: int | None = None

    for window_id in window_ids:
        truth = truth_windows.get(int(window_id))
        if truth is None:
            continue
        payload = codec.encode(truth)
        recon = codec.decode(payload)
        if len(recon) != len(truth):
            raise RuntimeError("reconstruction length mismatch")
        abs_sum = 0.0
        sq_sum = 0.0
        for a, b in zip(truth, recon, strict=True):
            diff = float(b) - float(a)
            abs_sum += abs(diff)
            sq_sum += diff * diff
        overall.update(abs_sum, sq_sum, len(truth))
        if by_group is not None and groups is not None:
            for name, idxs in groups.items():
                g_abs = 0.0
                g_sq = 0.0
                for idx in idxs:
                    diff = float(recon[idx]) - float(truth[idx])
                    g_abs += abs(diff)
                    g_sq += diff * diff
                by_group[name].update(g_abs, g_sq, len(idxs))

        samples += 1
        if payload_bytes_seen is None:
            payload_bytes_seen = len(payload)

    if samples == 0:
        return None

    return {
        "samples": samples,
        "payload_bytes_seen": payload_bytes_seen,
        "overall": {"mae": overall.mae(), "mse": overall.mse()},
        "by_group": (
            {name: {"mae": agg.mae(), "mse": agg.mse()} for name, agg in by_group.items()}
            if by_group is not None
            else None
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Phase 3 helper: aggregate TX/RX logs into a report, optionally computing "
            "reconstruction error for acked windows using dataset_raw.jsonl."
        )
    )
    p.add_argument("--log", action="append", required=True, help="Path to a JSONL log file")
    p.add_argument("--dataset", default=None, help="Optional dataset_raw.jsonl for recon metrics")
    p.add_argument("--out", default=None, help="Write JSON report to this path (default: print)")
    return p


def main() -> int:
    args = build_parser().parse_args()
    events: list[dict[str, Any]] = []
    for path in args.log:
        events.extend(load_events(path))

    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        run_id = str(event.get("run_id", "unknown"))
        grouped.setdefault(run_id, []).append(event)

    dataset_path = Path(args.dataset) if args.dataset else None
    dataset_index: dict[str, dict[int, list[float]]] | None = None
    if dataset_path is not None:
        if not dataset_path.exists():
            raise SystemExit(f"dataset not found: {dataset_path}")
        dataset_index = _load_dataset_index(dataset_path, run_ids=set(grouped.keys()))

    report: dict[str, object] = {}
    for run_id, run_events in grouped.items():
        metrics = compute_metrics(run_events)
        entry: dict[str, object] = {"metrics": metrics}

        spec = _find_runspec(run_events)
        if spec is not None:
            codec = None
            try:
                codec = create_codec(spec.codec)
            except Exception as exc:
                entry["codec_error"] = str(exc)
            if codec is not None:
                entry["payload_schema"] = codec.payload_schema()
                entry["payload_schema_hash"] = payload_schema_hash(codec.payload_schema())

                if dataset_index is not None:
                    acked_window_ids = _infer_acked_window_ids(run_events)
                    truth_windows = dataset_index.get(run_id) or {}
                    try:
                        recon = _compute_roundtrip_errors(
                            codec=codec,
                            truth_windows=truth_windows,
                            window_ids=acked_window_ids,
                            dims=spec.window.dims,
                            window_W=spec.window.W,
                        )
                    except Exception as exc:
                        entry["recon_error"] = str(exc)
                        recon = None
                    entry["roundtrip_over_acked"] = recon

        report[run_id] = entry

    output = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

