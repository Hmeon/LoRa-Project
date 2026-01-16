#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator


def _require_numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise SystemExit(
            "numpy is required. Install with `python -m pip install -e .[bam]`."
        ) from exc
    return np


def _parse_int_list_csv(value: str) -> list[int]:
    if not value.strip():
        return []
    out: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    return out


def _parse_float_list_csv(value: str) -> list[float]:
    if not value.strip():
        return []
    out: list[float] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(float(part))
    return out


def _parse_str_list_csv(value: str) -> list[str]:
    if not value.strip():
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


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
    subset: str,
    train_ratio: float,
    split_seed: int,
    max_samples: int | None,
) -> Iterator[list[float]]:
    count = 0
    with dataset_path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            window = record.get("window")
            if not isinstance(window, list):
                raise ValueError(f"dataset line {line_no}: missing 'window' list")
            if len(window) != expected_len:
                raise ValueError(
                    f"dataset line {line_no}: window_len {len(window)} != expected {expected_len}"
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


def _compute_norm_zscore(
    dataset_path: Path,
    *,
    input_len: int,
    train_ratio: float,
    split_seed: int,
    max_samples: int | None,
) -> tuple[list[float], list[float], int]:
    np = _require_numpy()
    count = 0
    mean = np.zeros((input_len,), dtype=np.float64)
    m2 = np.zeros((input_len,), dtype=np.float64)
    for values in _iter_dataset_windows(
        dataset_path,
        expected_len=input_len,
        subset="train",
        train_ratio=train_ratio,
        split_seed=split_seed,
        max_samples=max_samples,
    ):
        x = np.asarray(values, dtype=np.float64)
        count += 1
        delta = x - mean
        mean += delta / count
        delta2 = x - mean
        m2 += delta * delta2

    if count == 0:
        raise ValueError("dataset contains no windows in train split")
    if count < 2:
        std = np.zeros((input_len,), dtype=np.float64)
    else:
        var = m2 / (count - 1)
        std = np.sqrt(np.maximum(var, 0.0))
    return mean.astype(float).tolist(), std.astype(float).tolist(), count


def _zscore(values: list[float], mean: list[float], std: list[float]) -> Any:
    np = _require_numpy()
    x = np.asarray(values, dtype=np.float64)
    mu = np.asarray(mean, dtype=np.float64)
    sigma = np.asarray(std, dtype=np.float64)
    sigma_safe = np.where(sigma == 0, 1.0, sigma)
    return (x - mu) / sigma_safe


def _pca_components(
    dataset_path: Path,
    *,
    mean: list[float],
    std: list[float],
    max_k: int,
    train_ratio: float,
    split_seed: int,
    max_samples: int | None,
) -> tuple[Any, int]:
    np = _require_numpy()
    d = len(mean)
    if max_k <= 0:
        raise ValueError("max_k must be > 0")

    count = 0
    z_mean = np.zeros((d,), dtype=np.float64)
    m2 = np.zeros((d, d), dtype=np.float64)
    for values in _iter_dataset_windows(
        dataset_path,
        expected_len=d,
        subset="train",
        train_ratio=train_ratio,
        split_seed=split_seed,
        max_samples=max_samples,
    ):
        z = _zscore(values, mean, std).astype(np.float64)
        count += 1
        delta = z - z_mean
        z_mean += delta / count
        delta2 = z - z_mean
        m2 += np.outer(delta, delta2)

    if count < 2:
        raise ValueError("PCA requires at least 2 train samples")
    cov = m2 / (count - 1)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    eigvecs = eigvecs[:, order]
    return eigvecs[:, :max_k].astype(np.float64), count


@dataclass(frozen=True)
class _Agg:
    abs_sum: float = 0.0
    sq_sum: float = 0.0
    n: int = 0

    def update(self, diff: Any) -> "_Agg":
        np = _require_numpy()
        abs_sum = float(np.abs(diff).sum())
        sq_sum = float((diff**2).sum())
        return _Agg(
            abs_sum=self.abs_sum + abs_sum,
            sq_sum=self.sq_sum + sq_sum,
            n=self.n + int(diff.size),
        )

    def mae(self) -> float:
        return (self.abs_sum / self.n) if self.n else 0.0

    def mse(self) -> float:
        return (self.sq_sum / self.n) if self.n else 0.0


def _mean_baseline(
    dataset_path: Path,
    *,
    input_len: int,
    mean: list[float],
    train_ratio: float,
    split_seed: int,
    max_samples: int | None,
) -> dict[str, Any]:
    np = _require_numpy()
    mu = np.asarray(mean, dtype=np.float64)
    overall = _Agg()
    samples = 0
    for values in _iter_dataset_windows(
        dataset_path,
        expected_len=input_len,
        subset="holdout",
        train_ratio=train_ratio,
        split_seed=split_seed,
        max_samples=max_samples,
    ):
        x = np.asarray(values, dtype=np.float64)
        diff = mu - x
        overall = overall.update(diff)
        samples += 1
    return {"samples": samples, "overall": {"mae": overall.mae(), "mse": overall.mse()}}


def _pca_baseline(
    dataset_path: Path,
    *,
    input_len: int,
    mean: list[float],
    std: list[float],
    components: Any,
    ks: Iterable[int],
    train_ratio: float,
    split_seed: int,
    max_samples: int | None,
) -> dict[str, Any]:
    np = _require_numpy()
    mu = np.asarray(mean, dtype=np.float64)
    sigma = np.asarray(std, dtype=np.float64)
    sigma_safe = np.where(sigma == 0, 1.0, sigma)

    ks_sorted = sorted(set(int(k) for k in ks if int(k) > 0))
    aggs = {k: _Agg() for k in ks_sorted}
    samples = 0
    for values in _iter_dataset_windows(
        dataset_path,
        expected_len=input_len,
        subset="holdout",
        train_ratio=train_ratio,
        split_seed=split_seed,
        max_samples=max_samples,
    ):
        x = np.asarray(values, dtype=np.float64)
        z = (x - mu) / sigma_safe
        scores = components.T @ z  # (max_k,)
        for k in ks_sorted:
            Pk = components[:, :k]
            z_hat = Pk @ scores[:k]
            x_hat = z_hat * sigma_safe + mu
            aggs[k] = aggs[k].update(x_hat - x)
        samples += 1

    return {
        "samples": samples,
        "by_k": {str(k): {"mae": aggs[k].mae(), "mse": aggs[k].mse()} for k in ks_sorted},
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_python(args: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _prepare_env() -> dict[str, str]:
    env = dict(os.environ)
    root = str(_repo_root())
    py_path = env.get("PYTHONPATH", "")
    if not py_path:
        env["PYTHONPATH"] = root
    elif root not in py_path.split(os.pathsep):
        env["PYTHONPATH"] = os.pathsep.join([root, py_path])
    return env


def _pareto_front(items: list[dict[str, Any]], *, x_key: str, y_key: str) -> list[dict[str, Any]]:
    pts = [(float(it[x_key]), float(it[y_key]), it) for it in items]
    pts.sort(key=lambda t: (t[0], t[1]))
    out: list[dict[str, Any]] = []
    best_y = float("inf")
    for _x, y, it in pts:
        if y < best_y:
            best_y = y
            out.append(it)
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Phase 2 sweep: train/evaluate BAM variants and compare to mean/PCA baselines "
            "on the same deterministic train/holdout split."
        )
    )
    p.add_argument("--dataset", required=True, help="Path to dataset_raw.jsonl")
    p.add_argument("--out-dir", required=True, help="Output directory for sweep artifacts/reports")
    p.add_argument("--force", action="store_true", help="Overwrite existing sweep outputs")

    p.add_argument("--input-dims", type=int, default=12)
    p.add_argument("--window-W", type=int, default=1)
    p.add_argument("--window-stride", type=int, default=1)

    p.add_argument("--latent-dims", default="2,4,8,16", help="CSV list (default: 2,4,8,16)")
    p.add_argument("--hidden-dims", default="", help="CSV list applied to all runs (default: '')")
    p.add_argument("--packings", default="int16", help="CSV list (default: int16)")
    p.add_argument("--deltas", default="", help="CSV list of deltas; '' means no delta (linear)")
    p.add_argument("--encode-cycles", default="0", help="CSV list (default: 0)")
    p.add_argument("--decode-cycles", default="0", help="CSV list (default: 0)")

    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--min-epochs", type=int, default=1)
    p.add_argument("--learning-rate", type=float, default=1e-4)
    p.add_argument("--cycles", type=int, default=1, help="Recurrent cycles per update in training")
    p.add_argument("--init-range", type=float, default=0.05)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--weight-clip", type=float, default=None)
    p.add_argument("--max-samples", type=int, default=None, help="Limit windows for train/eval")
    p.add_argument("--shuffle-buffer", type=int, default=0)
    p.add_argument("--shuffle-seed", type=int, default=0)

    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--split-seed", type=int, default=0)

    p.add_argument("--auto-scale", action="store_true")
    p.add_argument("--auto-scale-percentile", type=float, default=99.9)
    p.add_argument("--auto-scale-max-samples", type=int, default=10000)

    p.add_argument(
        "--max-payload-bytes",
        type=int,
        default=238,
        help="Skip configs whose latent payload exceeds this limit (default: 238)",
    )
    p.add_argument("--out", default="sweep_report.json", help="Output report filename (default)")
    return p


def main() -> int:
    args = build_parser().parse_args()
    dataset = Path(args.dataset)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not dataset.exists():
        raise SystemExit(f"dataset not found: {dataset}")
    if args.input_dims <= 0 or args.window_W <= 0 or args.window_stride <= 0:
        raise SystemExit("input-dims/window-W/window-stride must be > 0")
    if not (0.0 < float(args.train_ratio) <= 1.0):
        raise SystemExit("--train-ratio must be in (0, 1]")
    if args.max_payload_bytes <= 0:
        raise SystemExit("--max-payload-bytes must be > 0")

    input_len = int(args.input_dims) * int(args.window_W)
    latent_dims = [d for d in _parse_int_list_csv(str(args.latent_dims)) if d > 0]
    if not latent_dims:
        raise SystemExit("--latent-dims must include at least one positive int")
    hidden_dims = _parse_int_list_csv(str(args.hidden_dims))
    packings = [p.lower() for p in _parse_str_list_csv(str(args.packings))]
    if not packings:
        raise SystemExit("--packings must include at least one entry")
    deltas_raw = _parse_str_list_csv(str(args.deltas))
    deltas: list[float | None] = [None] if not deltas_raw else []
    for v in deltas_raw:
        val = float(v)
        deltas.append(val)
    encode_cycles = [c for c in _parse_int_list_csv(str(args.encode_cycles)) if c >= 0]
    decode_cycles = [c for c in _parse_int_list_csv(str(args.decode_cycles)) if c >= 0]
    if not encode_cycles or not decode_cycles:
        raise SystemExit("--encode-cycles/--decode-cycles must include >=0")

    print(f"Dataset: {dataset}")
    print(f"Split: train_ratio={args.train_ratio}, split_seed={args.split_seed}")
    print(f"Search space: latent_dims={latent_dims}, packings={packings}, deltas={deltas}")

    mean, std, train_n = _compute_norm_zscore(
        dataset,
        input_len=input_len,
        train_ratio=float(args.train_ratio),
        split_seed=int(args.split_seed),
        max_samples=args.max_samples,
    )
    mean_baseline = _mean_baseline(
        dataset,
        input_len=input_len,
        mean=mean,
        train_ratio=float(args.train_ratio),
        split_seed=int(args.split_seed),
        max_samples=args.max_samples,
    )

    max_k = max(latent_dims)
    pca_components, pca_train_n = _pca_components(
        dataset,
        mean=mean,
        std=std,
        max_k=max_k,
        train_ratio=float(args.train_ratio),
        split_seed=int(args.split_seed),
        max_samples=args.max_samples,
    )
    pca_baseline = _pca_baseline(
        dataset,
        input_len=input_len,
        mean=mean,
        std=std,
        components=pca_components,
        ks=latent_dims,
        train_ratio=float(args.train_ratio),
        split_seed=int(args.split_seed),
        max_samples=args.max_samples,
    )

    env = _prepare_env()
    results: list[dict[str, Any]] = []

    bytes_per = {"int8": 1, "int16": 2, "float16": 2, "float32": 4}
    sweep = itertools.product(latent_dims, packings, deltas, encode_cycles, decode_cycles)
    for latent_dim, packing, delta, enc_c, dec_c in sweep:
        bpp = bytes_per.get(packing)
        if bpp is None:
            continue
        payload_bytes = int(latent_dim) * int(bpp)
        if payload_bytes > int(args.max_payload_bytes):
            continue

        delta_tag = "none" if delta is None else str(delta).replace(".", "p")
        model_id = (
            f"bam_ld{latent_dim}_p{packing}_d{delta_tag}_ec{enc_c}_dc{dec_c}"
            f"_hd{'-'.join(str(x) for x in hidden_dims) if hidden_dims else 'none'}"
        )
        model_dir = out_dir / model_id
        if model_dir.exists() and not args.force:
            raise SystemExit(f"model dir already exists: {model_dir} (use --force)")

        train_args = [
            "scripts/phase2_train_bam.py",
            "--dataset",
            str(dataset),
            "--out-dir",
            str(model_dir),
            "--latent-dim",
            str(latent_dim),
            "--packing",
            packing,
            "--input-dims",
            str(args.input_dims),
            "--window-W",
            str(args.window_W),
            "--window-stride",
            str(args.window_stride),
            "--hidden-dims",
            ",".join(str(x) for x in hidden_dims),
            "--encode-cycles",
            str(enc_c),
            "--decode-cycles",
            str(dec_c),
            "--epochs",
            str(args.epochs),
            "--min-epochs",
            str(args.min_epochs),
            "--learning-rate",
            str(args.learning_rate),
            "--cycles",
            str(args.cycles),
            "--init-range",
            str(args.init_range),
            "--seed",
            str(args.seed),
            "--train-ratio",
            str(args.train_ratio),
            "--split-seed",
            str(args.split_seed),
            "--max-payload-bytes",
            str(args.max_payload_bytes),
            "--shuffle-buffer",
            str(args.shuffle_buffer),
            "--shuffle-seed",
            str(args.shuffle_seed),
            "--auto-scale-percentile",
            str(args.auto_scale_percentile),
            "--auto-scale-max-samples",
            str(args.auto_scale_max_samples),
            "--force",
        ]
        if delta is not None:
            train_args.extend(["--delta", str(delta)])
        if args.weight_clip is not None:
            train_args.extend(["--weight-clip", str(args.weight_clip)])
        if args.max_samples is not None:
            train_args.extend(["--max-samples", str(args.max_samples)])
        if args.auto_scale and packing in {"int8", "int16"}:
            train_args.append("--auto-scale")

        print(f"[train] {model_id}")
        _run_python(train_args, env=env)

        bam_manifest = model_dir / "bam_manifest.json"
        eval_args = [
            "scripts/eval_bam_dataset.py",
            "--dataset",
            str(dataset),
            "--bam-manifest",
            str(bam_manifest),
            "--subset",
            "holdout",
            "--train-ratio",
            str(args.train_ratio),
            "--split-seed",
            str(args.split_seed),
        ]
        if args.max_samples is not None:
            eval_args.extend(["--max-samples", str(args.max_samples)])

        proc = _run_python(eval_args, env=env)
        report = json.loads(proc.stdout)
        report["model_id"] = model_id
        report["model_dir"] = str(model_dir)
        train_report_path = model_dir / "train_report.json"
        if train_report_path.exists():
            train_report = json.loads(train_report_path.read_text(encoding="utf-8"))
            report["train_report"] = {
                "expected_payload_bytes": train_report.get("expected_payload_bytes"),
                "cost": train_report.get("cost"),
                "layer_reports": train_report.get("layer_reports"),
            }
        results.append(report)

    report_out = out_dir / str(args.out)
    if report_out.exists() and not args.force:
        raise SystemExit(f"report already exists: {report_out} (use --force)")

    pareto_items = [
        {
            "model_id": r["model_id"],
            "payload_bytes": r["payload_bytes_seen"],
            "mae": r["overall"]["mae"],
        }
        for r in results
    ]
    pareto = _pareto_front(pareto_items, x_key="payload_bytes", y_key="mae")
    out_payload = {
        "dataset": str(dataset),
        "input_len": input_len,
        "train_ratio": float(args.train_ratio),
        "split_seed": int(args.split_seed),
        "train_n": train_n,
        "pca_train_n": pca_train_n,
        "baselines": {
            "mean": mean_baseline,
            "pca": pca_baseline,
        },
        "bam_results": results,
        "pareto": pareto,
    }
    report_out.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")
    print(f"Wrote sweep report: {report_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
