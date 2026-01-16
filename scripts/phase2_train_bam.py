#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

from loralink_mllc.codecs import create_codec, payload_schema_hash
from loralink_mllc.config.artifacts import ArtifactsManifest, hash_file
from loralink_mllc.config.runspec import CodecSpec


def _require_numpy():
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


def _split_accept(window_id: int, *, train_ratio: float, split_seed: int) -> bool:
    if train_ratio >= 1.0:
        return True
    if train_ratio <= 0.0:
        return False
    digest = hashlib.sha256(f"{split_seed}:{window_id}".encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], byteorder="big", signed=False) / (2**64)
    return bucket < train_ratio


def _iter_dataset_records(
    dataset_path: Path,
    *,
    expected_len: int,
    expected_input_dims: int,
    max_samples: int | None = None,
    train_ratio: float = 1.0,
    split_seed: int = 0,
    shuffle_buffer: int = 0,
    shuffle_seed: int = 0,
) -> Iterator[list[float]]:
    count = 0
    buffer: list[list[float]] = []
    rng = random.Random(int(shuffle_seed))
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
            order = record.get("order")
            if isinstance(order, list) and len(order) != expected_input_dims:
                actual_order_len = len(order)
                raise ValueError(
                    f"dataset line {line_no}: order_len {actual_order_len} != expected "
                    f"{expected_input_dims}"
                )
            window_id = record.get("window_id")
            if window_id is None:
                window_id = line_no - 1
            window_id = int(window_id)
            if not _split_accept(window_id, train_ratio=train_ratio, split_seed=split_seed):
                continue
            values = [float(v) for v in window]
            if shuffle_buffer > 0:
                buffer.append(values)
                if len(buffer) >= shuffle_buffer:
                    idx = rng.randrange(len(buffer))
                    count += 1
                    yield buffer.pop(idx)
                    if max_samples is not None and count >= max_samples:
                        return
            else:
                count += 1
                yield values
                if max_samples is not None and count >= max_samples:
                    return

    if buffer:
        rng.shuffle(buffer)
        for values in buffer:
            count += 1
            yield values
            if max_samples is not None and count >= max_samples:
                return


def _compute_norm_zscore(
    dataset_path: Path,
    *,
    input_len: int,
    input_dims: int,
    max_samples: int | None,
    train_ratio: float,
    split_seed: int,
    shuffle_buffer: int,
    shuffle_seed: int,
) -> tuple[list[float], list[float], int]:
    np = _require_numpy()
    count = 0
    mean = np.zeros((input_len,), dtype=np.float64)
    m2 = np.zeros((input_len,), dtype=np.float64)

    for values in _iter_dataset_records(
        dataset_path,
        expected_len=input_len,
        expected_input_dims=input_dims,
        max_samples=max_samples,
        train_ratio=train_ratio,
        split_seed=split_seed,
        shuffle_buffer=shuffle_buffer,
        shuffle_seed=shuffle_seed,
    ):
        x = np.asarray(values, dtype=np.float64)
        count += 1
        delta = x - mean
        mean += delta / count
        delta2 = x - mean
        m2 += delta * delta2

    if count == 0:
        raise ValueError("dataset contains no windows")

    if count < 2:
        std = np.zeros((input_len,), dtype=np.float64)
    else:
        var = m2 / (count - 1)
        std = np.sqrt(np.maximum(var, 0.0))

    return mean.astype(float).tolist(), std.astype(float).tolist(), count


def _apply_zscore(
    values: Sequence[float], mean: Sequence[float], std: Sequence[float]
) -> list[float]:
    if len(values) != len(mean) or len(values) != len(std):
        raise ValueError("norm length mismatch")
    out: list[float] = []
    for v, mu, sigma in zip(values, mean, std, strict=True):
        if sigma == 0:
            out.append(0.0)
        else:
            out.append((float(v) - float(mu)) / float(sigma))
    return out


def _transmission(vector, *, delta: float | None):
    if delta is None or float(delta) == 0.0:
        return vector
    out = (delta + 1.0) * vector - delta * (vector ** 3)
    return _require_numpy().clip(out, -1.0, 1.0)


@dataclass
class Layer:
    W: object
    V: object

    @property
    def in_dim(self) -> int:
        return int(self.W.shape[1])

    @property
    def out_dim(self) -> int:
        return int(self.W.shape[0])

    def encode(self, x, *, delta: float | None):
        return _transmission(self.W @ x, delta=delta)

    def decode(self, y, *, delta: float | None):
        return _transmission(self.V @ y, delta=delta)


@dataclass(frozen=True)
class LayerTrainReport:
    layer_index: int
    in_dim: int
    out_dim: int
    epochs_ran: int
    samples_seen: int
    mse_x: float
    mse_y: float


def _encode_latent(
    x_vec,
    *,
    layers: Sequence[Layer],
    delta: float | None,
    encode_cycles: int,
):
    out = x_vec
    for layer in layers:
        y0 = layer.encode(out, delta=delta)
        if encode_cycles <= 0:
            out = y0
            continue
        y_c = y0
        x_c = out
        for _ in range(encode_cycles):
            x_c = layer.decode(y_c, delta=delta)
            y_c = layer.encode(x_c, delta=delta)
        out = y_c
    return out


def _auto_scale_for_latent(
    dataset_path: Path,
    *,
    input_len: int,
    input_dims: int,
    mean: Sequence[float],
    std: Sequence[float],
    layers: Sequence[Layer],
    delta: float | None,
    encode_cycles: int,
    packing: str,
    percentile: float,
    max_samples: int,
    train_ratio: float,
    split_seed: int,
    shuffle_buffer: int,
    shuffle_seed: int,
) -> float:
    if max_samples <= 0:
        raise ValueError("auto-scale max_samples must be > 0")
    np = _require_numpy()
    abs_max_values: list[float] = []
    for values in _iter_dataset_records(
        dataset_path,
        expected_len=input_len,
        expected_input_dims=input_dims,
        max_samples=max_samples,
        train_ratio=train_ratio,
        split_seed=split_seed,
        shuffle_buffer=shuffle_buffer,
        shuffle_seed=shuffle_seed,
    ):
        x = _apply_zscore(values, mean, std)
        x_vec = np.asarray(x, dtype=np.float32)
        latent = _encode_latent(
            x_vec,
            layers=layers,
            delta=delta,
            encode_cycles=int(encode_cycles),
        )
        abs_max_values.append(float(np.max(np.abs(latent))))

    if not abs_max_values:
        raise ValueError("auto-scale failed: dataset contains no windows")

    q = float(np.percentile(np.asarray(abs_max_values, dtype=np.float64), percentile))
    if q <= 0:
        q = 1.0

    dtype_max = {"int8": 127.0, "int16": 32767.0}.get(packing.lower())
    if dtype_max is None:
        raise ValueError(f"auto-scale is only valid for int8/int16 (packing={packing})")
    return dtype_max / q


def _init_layers(
    dims: Sequence[int],
    *,
    seed: int,
    init_range: float,
) -> list[Layer]:
    if len(dims) < 2:
        raise ValueError("dims must include at least input and latent dim")
    if any(d <= 0 for d in dims):
        raise ValueError("all dims must be positive")
    np = _require_numpy()
    rng = np.random.default_rng(seed)
    layers: list[Layer] = []
    for in_dim, out_dim in zip(dims[:-1], dims[1:], strict=True):
        W = rng.uniform(-init_range, init_range, size=(out_dim, in_dim)).astype(np.float32)
        V = rng.uniform(-init_range, init_range, size=(in_dim, out_dim)).astype(np.float32)
        layers.append(Layer(W=W, V=V))
    return layers


def _train_layer_online(
    layer: Layer,
    dataset_path: Path,
    *,
    input_len: int,
    input_dims: int,
    mean: Sequence[float] | None,
    std: Sequence[float] | None,
    prev_layers: Sequence[Layer],
    delta: float | None,
    learning_rate: float,
    cycles: int,
    epochs: int,
    min_epochs: int,
    early_stop_patience: int,
    early_stop_min_delta: float,
    target_mse_x: float | None,
    target_mse_y: float | None,
    max_samples: int | None,
    log_every: int,
    weight_clip: float | None,
    train_ratio: float,
    split_seed: int,
    shuffle_buffer: int,
    shuffle_seed: int,
) -> LayerTrainReport:
    np = _require_numpy()
    if cycles < 0:
        raise ValueError("cycles must be >= 0")
    if epochs <= 0:
        raise ValueError("epochs must be >= 1")
    if min_epochs <= 0:
        raise ValueError("min_epochs must be >= 1")
    if min_epochs > epochs:
        raise ValueError("min_epochs must be <= epochs")
    if learning_rate <= 0:
        raise ValueError("learning_rate must be > 0")
    if early_stop_patience < 0:
        raise ValueError("early_stop_patience must be >= 0")
    if early_stop_min_delta < 0:
        raise ValueError("early_stop_min_delta must be >= 0")

    total_seen = 0
    best_mse_x: float | None = None
    bad_epochs = 0
    last_epoch_mse_x = 0.0
    last_epoch_mse_y = 0.0
    for epoch in range(1, epochs + 1):
        seen_this_epoch = 0
        mse_x_sum = 0.0
        mse_y_sum = 0.0
        for raw in _iter_dataset_records(
            dataset_path,
            expected_len=input_len,
            expected_input_dims=input_dims,
            max_samples=max_samples,
            train_ratio=train_ratio,
            split_seed=split_seed,
            shuffle_buffer=shuffle_buffer,
            shuffle_seed=shuffle_seed + epoch,
        ):
            x = raw
            if mean is not None and std is not None:
                x = _apply_zscore(x, mean, std)

            x_vec = np.asarray(x, dtype=np.float32)
            for prev in prev_layers:
                x_vec = prev.encode(x_vec, delta=delta)

            if x_vec.shape[0] != layer.in_dim:
                raise RuntimeError("layer input dim mismatch (check dims and window settings)")

            y0 = layer.encode(x_vec, delta=delta)
            y_c = y0
            x_c = x_vec
            for _ in range(cycles):
                x_c = layer.decode(y_c, delta=delta)
                y_c = layer.encode(x_c, delta=delta)

            diff_x = x_vec - x_c
            diff_y = y0 - y_c
            mse_x_sum += float((diff_x**2).mean())
            mse_y_sum += float((diff_y**2).mean())

            dW = np.outer((y0 - y_c), (x_vec + x_c))
            dV = np.outer((x_vec - x_c), (y0 + y_c))
            layer.W += learning_rate * dW.astype(np.float32)
            layer.V += learning_rate * dV.astype(np.float32)

            if weight_clip is not None:
                np.clip(layer.W, -weight_clip, weight_clip, out=layer.W)
                np.clip(layer.V, -weight_clip, weight_clip, out=layer.V)

            seen_this_epoch += 1
            total_seen += 1
            if log_every > 0 and (total_seen % log_every) == 0:
                print(
                    f"layer {layer.in_dim}->{layer.out_dim}: epoch {epoch}/{epochs}, "
                    f"samples_seen={total_seen}"
                )
        if seen_this_epoch == 0:
            raise ValueError("dataset contains no windows")

        last_epoch_mse_x = mse_x_sum / seen_this_epoch
        last_epoch_mse_y = mse_y_sum / seen_this_epoch
        print(
            f"layer {layer.in_dim}->{layer.out_dim}: epoch {epoch}/{epochs} done. "
            f"mse_x={last_epoch_mse_x:.6g}, mse_y={last_epoch_mse_y:.6g}, "
            f"samples={seen_this_epoch}"
        )

        if best_mse_x is None or (best_mse_x - last_epoch_mse_x) > early_stop_min_delta:
            best_mse_x = last_epoch_mse_x
            bad_epochs = 0
        else:
            bad_epochs += 1

        if epoch >= min_epochs:
            if (
                target_mse_x is not None
                and last_epoch_mse_x <= float(target_mse_x)
                and (target_mse_y is None or last_epoch_mse_y <= float(target_mse_y))
            ):
                print("Early stop: target MSE reached.")
                return LayerTrainReport(
                    layer_index=-1,
                    in_dim=layer.in_dim,
                    out_dim=layer.out_dim,
                    epochs_ran=epoch,
                    samples_seen=total_seen,
                    mse_x=last_epoch_mse_x,
                    mse_y=last_epoch_mse_y,
                )
            if early_stop_patience and bad_epochs >= early_stop_patience:
                print("Early stop: no improvement.")
                return LayerTrainReport(
                    layer_index=-1,
                    in_dim=layer.in_dim,
                    out_dim=layer.out_dim,
                    epochs_ran=epoch,
                    samples_seen=total_seen,
                    mse_x=last_epoch_mse_x,
                    mse_y=last_epoch_mse_y,
                )

    return LayerTrainReport(
        layer_index=-1,
        in_dim=layer.in_dim,
        out_dim=layer.out_dim,
        epochs_ran=epochs,
        samples_seen=total_seen,
        mse_x=last_epoch_mse_x,
        mse_y=last_epoch_mse_y,
    )


def _write_norm(path: Path, mean: Sequence[float], std: Sequence[float], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"norm already exists: {path}")
    payload = {"mean": [float(v) for v in mean], "std": [float(v) for v in std]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_layers(model_dir: Path, layers: Sequence[Layer], *, force: bool) -> None:
    np = _require_numpy()
    model_dir.mkdir(parents=True, exist_ok=True)
    for idx, layer in enumerate(layers):
        out_path = model_dir / f"layer_{idx}.npz"
        if out_path.exists() and not force:
            raise FileExistsError(f"layer already exists: {out_path}")
        np.savez(
            out_path,
            W=np.asarray(layer.W, dtype=np.float32),
            V=np.asarray(layer.V, dtype=np.float32),
        )


def _packing_bytes_per(packing: str) -> int:
    value = packing.lower()
    if value == "int8":
        return 1
    if value == "int16":
        return 2
    if value == "float16":
        return 2
    if value == "float32":
        return 4
    raise ValueError(f"unsupported packing: {packing}")


def _write_bam_manifest(
    path: Path,
    *,
    model_path: str,
    input_dims: int,
    window_W: int,
    window_stride: int,
    latent_dim: int,
    packing: str,
    scale: float | None,
    delta: float | None,
    encode_cycles: int,
    decode_cycles: int,
    norm_path: str | None,
    notes: str | None,
    train_ratio: float,
    split_seed: int,
    force: bool,
) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"bam manifest already exists: {path}")
    payload: dict[str, object] = {
        "manifest_version": "1",
        "model_format": "layer_npz_v1",
        "model_path": model_path,
        "latent_dim": int(latent_dim),
        "packing": packing,
        "scale": scale,
        "delta": delta,
        "encode_cycles": int(encode_cycles),
        "decode_cycles": int(decode_cycles),
        "input_dims": int(input_dims),
        "window_W": int(window_W),
        "window_stride": int(window_stride),
        "norm_path": norm_path,
        "notes": notes or None,
    }
    if train_ratio < 1.0:
        payload["train_split"] = {
            "method": "hash_window_id",
            "train_ratio": float(train_ratio),
            "split_seed": int(split_seed),
        }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_artifacts_manifest(
    path: Path,
    *,
    bam_manifest_path: Path,
    norm_path: Path | None,
    force: bool,
) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"artifacts manifest already exists: {path}")
    codec_spec = CodecSpec(id="bam", version="0", params={"manifest_path": str(bam_manifest_path)})
    codec = create_codec(codec_spec)
    norm_hash = hash_file(norm_path) if norm_path is not None else None
    manifest = ArtifactsManifest.create(
        codec_id=codec.codec_id,
        codec_version=codec.codec_version,
        payload_schema_hash=payload_schema_hash(codec.payload_schema()),
        norm_params_hash=norm_hash,
    )
    manifest.save(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 2 trainer: produce BAM inference artifacts (layer_*.npz, norm.json, "
            "bam_manifest.json) from dataset_raw.jsonl. This is a FEBAM-style online trainer "
            "inspired by ChirpChirp-main."
        )
    )
    parser.add_argument("--dataset", required=True, help="Path to dataset_raw.jsonl")
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Output directory for artifacts (created if missing)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing outputs in out-dir",
    )

    parser.add_argument("--input-dims", type=int, default=12, help="Input dims (default: 12)")
    parser.add_argument("--window-W", type=int, default=1, help="Window length (default: 1)")
    parser.add_argument("--window-stride", type=int, default=1, help="Window stride (default: 1)")

    parser.add_argument("--latent-dim", type=int, required=True, help="Latent dimension")
    parser.add_argument(
        "--hidden-dims",
        default="",
        help=(
            "Comma-separated hidden dims (e.g., '24,16'). Final dims = "
            "[input_len] + hidden + [latent_dim]."
        ),
    )
    parser.add_argument("--delta", type=float, default=None, help="Transmission delta (optional)")
    parser.add_argument(
        "--encode-cycles",
        type=int,
        default=0,
        help="Recurrent refinement cycles during encoding (default: 0)",
    )
    parser.add_argument(
        "--decode-cycles",
        type=int,
        default=0,
        help="Recurrent refinement cycles during decoding (default: 0)",
    )
    parser.add_argument("--epochs", type=int, default=1, help="Epochs per layer (default: 1)")
    parser.add_argument(
        "--min-epochs",
        type=int,
        default=1,
        help="Minimum epochs per layer before early stopping (default: 1)",
    )
    parser.add_argument(
        "--early-stop-patience",
        type=int,
        default=0,
        help="Early stop after N bad epochs (0 disables; default: 0)",
    )
    parser.add_argument(
        "--early-stop-min-delta",
        type=float,
        default=0.0,
        help="Min improvement in mse_x to reset patience (default: 0.0)",
    )
    parser.add_argument("--target-mse-x", type=float, default=None, help="Stop if mse_x <= value")
    parser.add_argument("--target-mse-y", type=float, default=None, help="Stop if mse_y <= value")
    parser.add_argument(
        "--cycles",
        type=int,
        default=1,
        help="Recurrent cycles per update (default: 1)",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=1e-4,
        help="Learning rate (default: 1e-4)",
    )
    parser.add_argument("--seed", type=int, default=0, help="RNG seed for init (default: 0)")
    parser.add_argument(
        "--init-range",
        type=float,
        default=0.05,
        help="Init weight range (default: 0.05)",
    )
    parser.add_argument(
        "--weight-clip",
        type=float,
        default=None,
        help="Optional weight clip value (e.g., 5.0). Off by default.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Limit number of windows used (debug). Default uses all windows.",
    )
    parser.add_argument(
        "--shuffle-buffer",
        type=int,
        default=0,
        help="Shuffle buffer size for streaming shuffle (0 disables; default: 0)",
    )
    parser.add_argument(
        "--shuffle-seed",
        type=int,
        default=0,
        help="Seed for streaming shuffle (default: 0)",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=1.0,
        help=(
            "Train/norm split ratio in (0, 1]. Uses a deterministic window_id hash; "
            "holdout is (1-ratio). Default trains on all windows."
        ),
    )
    parser.add_argument(
        "--split-seed",
        type=int,
        default=0,
        help="Seed for deterministic split hashing (default: 0)",
    )
    parser.add_argument(
        "--log-every",
        type=int,
        default=1000,
        help="Progress print frequency (default: 1000)",
    )

    parser.add_argument(
        "--packing",
        default="int16",
        choices=["int8", "int16", "float16", "float32"],
        help="Packing type",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=None,
        help="Scale for int8/int16 (default: 127 for int8, 32767 for int16)",
    )
    parser.add_argument(
        "--auto-scale",
        action="store_true",
        help="Auto-tune scale for int8/int16 using latent percentile stats",
    )
    parser.add_argument(
        "--auto-scale-percentile",
        type=float,
        default=99.9,
        help="Latent abs-max percentile used for auto-scale (default: 99.9)",
    )
    parser.add_argument(
        "--auto-scale-max-samples",
        type=int,
        default=10000,
        help="Max windows to scan for auto-scale (default: 10000)",
    )
    parser.add_argument(
        "--max-payload-bytes",
        type=int,
        default=238,
        help="Validate latent payload size against this limit (default: 238)",
    )
    parser.add_argument("--notes", default="", help="Optional notes")

    parser.add_argument(
        "--write-artifacts-manifest",
        default="artifacts.json",
        help=(
            "Write an ArtifactsManifest JSON (default: artifacts.json in out-dir). "
            "Use '' to skip."
        ),
    )
    parser.add_argument(
        "--train-report",
        default="train_report.json",
        help="Write a training summary JSON (default: train_report.json). Use '' to skip.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    dataset = Path(args.dataset)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not dataset.exists():
        raise SystemExit(f"dataset not found: {dataset}")
    if args.input_dims <= 0:
        raise SystemExit("--input-dims must be > 0")
    if args.window_W <= 0:
        raise SystemExit("--window-W must be > 0")
    if args.window_stride <= 0:
        raise SystemExit("--window-stride must be > 0")
    if args.latent_dim <= 0:
        raise SystemExit("--latent-dim must be > 0")
    if args.encode_cycles < 0 or args.decode_cycles < 0:
        raise SystemExit("--encode-cycles/--decode-cycles must be >= 0")
    if args.shuffle_buffer < 0:
        raise SystemExit("--shuffle-buffer must be >= 0")
    if args.max_payload_bytes <= 0:
        raise SystemExit("--max-payload-bytes must be > 0")
    if not (0.0 < float(args.train_ratio) <= 1.0):
        raise SystemExit("--train-ratio must be in (0, 1]")
    if args.auto_scale_max_samples <= 0:
        raise SystemExit("--auto-scale-max-samples must be > 0")

    input_len = int(args.input_dims) * int(args.window_W)
    hidden_dims = _parse_int_list_csv(args.hidden_dims)
    dims = [input_len, *hidden_dims, int(args.latent_dim)]

    if any(d <= 0 for d in dims):
        raise SystemExit("all dims must be positive")

    bytes_per = _packing_bytes_per(args.packing)
    expected_payload_bytes = int(args.latent_dim) * bytes_per
    if expected_payload_bytes > int(args.max_payload_bytes):
        raise SystemExit(
            f"latent payload {expected_payload_bytes}B exceeds max_payload_bytes "
            f"{args.max_payload_bytes} for packing={args.packing} latent_dim={args.latent_dim}"
        )

    scale = args.scale
    if scale is None:
        if args.packing == "int8":
            scale = 127.0
        elif args.packing == "int16":
            scale = 32767.0

    print(f"Dataset: {dataset}")
    print(f"Output dir: {out_dir}")
    print(f"Dims: {dims} (input_len={input_len})")
    print(
        f"Packing: {args.packing}, latent_payload_bytes={expected_payload_bytes}, "
        f"max_payload_bytes={args.max_payload_bytes}"
    )

    norm_path = out_dir / "norm.json"
    mean, std, n = _compute_norm_zscore(
        dataset,
        input_len=input_len,
        input_dims=int(args.input_dims),
        max_samples=args.max_samples,
        train_ratio=float(args.train_ratio),
        split_seed=int(args.split_seed),
        shuffle_buffer=int(args.shuffle_buffer),
        shuffle_seed=int(args.shuffle_seed),
    )
    _write_norm(norm_path, mean, std, force=bool(args.force))
    print(f"Wrote norm.json (n={n}): {norm_path}")

    layers = _init_layers(dims, seed=int(args.seed), init_range=float(args.init_range))
    layer_reports: list[LayerTrainReport] = []
    for layer_idx, layer in enumerate(layers):
        prev = layers[:layer_idx]
        print(f"Training layer_{layer_idx}: {layer.in_dim}->{layer.out_dim} ...")
        report = _train_layer_online(
            layer,
            dataset,
            input_len=input_len,
            input_dims=int(args.input_dims),
            mean=mean,
            std=std,
            prev_layers=prev,
            delta=(float(args.delta) if args.delta is not None else None),
            learning_rate=float(args.learning_rate),
            cycles=int(args.cycles),
            epochs=int(args.epochs),
            min_epochs=int(args.min_epochs),
            early_stop_patience=int(args.early_stop_patience),
            early_stop_min_delta=float(args.early_stop_min_delta),
            target_mse_x=(float(args.target_mse_x) if args.target_mse_x is not None else None),
            target_mse_y=(float(args.target_mse_y) if args.target_mse_y is not None else None),
            max_samples=args.max_samples,
            log_every=int(args.log_every),
            weight_clip=(float(args.weight_clip) if args.weight_clip is not None else None),
            train_ratio=float(args.train_ratio),
            split_seed=int(args.split_seed),
            shuffle_buffer=int(args.shuffle_buffer),
            shuffle_seed=int(args.shuffle_seed),
        )
        layer_reports.append(
            LayerTrainReport(
                layer_index=layer_idx,
                in_dim=report.in_dim,
                out_dim=report.out_dim,
                epochs_ran=report.epochs_ran,
                samples_seen=report.samples_seen,
                mse_x=report.mse_x,
                mse_y=report.mse_y,
            )
        )

    _write_layers(out_dir, layers, force=bool(args.force))
    print(f"Wrote {len(layers)} layer files under: {out_dir}")

    if args.packing in {"int8", "int16"} and args.auto_scale:
        scale = _auto_scale_for_latent(
            dataset,
            input_len=input_len,
            input_dims=int(args.input_dims),
            mean=mean,
            std=std,
            layers=layers,
            delta=(float(args.delta) if args.delta is not None else None),
            encode_cycles=int(args.encode_cycles),
            packing=str(args.packing),
            percentile=float(args.auto_scale_percentile),
            max_samples=int(args.auto_scale_max_samples),
            train_ratio=float(args.train_ratio),
            split_seed=int(args.split_seed),
            shuffle_buffer=int(args.shuffle_buffer),
            shuffle_seed=int(args.shuffle_seed),
        )
        print(f"Auto-scale enabled: scale={scale:.6g} (packing={args.packing})")

    bam_manifest_path = out_dir / "bam_manifest.json"
    _write_bam_manifest(
        bam_manifest_path,
        model_path=".",
        input_dims=int(args.input_dims),
        window_W=int(args.window_W),
        window_stride=int(args.window_stride),
        latent_dim=int(args.latent_dim),
        packing=str(args.packing),
        scale=(float(scale) if scale is not None else None),
        delta=(float(args.delta) if args.delta is not None else None),
        encode_cycles=int(args.encode_cycles),
        decode_cycles=int(args.decode_cycles),
        norm_path=str(norm_path.name),
        notes=str(args.notes) if args.notes else None,
        train_ratio=float(args.train_ratio),
        split_seed=int(args.split_seed),
        force=bool(args.force),
    )
    print(f"Wrote bam manifest: {bam_manifest_path}")

    if args.train_report:
        report_path = out_dir / str(args.train_report)
        np = _require_numpy()
        param_count = int(
            sum(int(np.asarray(layer.W).size) + int(np.asarray(layer.V).size) for layer in layers)
        )
        weight_bytes = param_count * 4  # float32
        ops_encode_est = int(
            sum(
                layer.in_dim * layer.out_dim * (1 + 2 * int(args.encode_cycles))
                for layer in layers
            )
        )
        ops_decode_est = int(
            sum(
                layer.in_dim * layer.out_dim * (1 + 2 * int(args.decode_cycles))
                for layer in layers
            )
        )
        bytes_per = _packing_bytes_per(str(args.packing))
        expected_payload_bytes = int(args.latent_dim) * int(bytes_per)
        train_report = {
            "dataset": str(dataset),
            "out_dir": str(out_dir),
            "dims": dims,
            "input_dims": int(args.input_dims),
            "window_W": int(args.window_W),
            "window_stride": int(args.window_stride),
            "latent_dim": int(args.latent_dim),
            "packing": str(args.packing),
            "scale": float(scale) if scale is not None else None,
            "delta": float(args.delta) if args.delta is not None else None,
            "encode_cycles": int(args.encode_cycles),
            "decode_cycles": int(args.decode_cycles),
            "expected_payload_bytes": expected_payload_bytes,
            "cost": {
                "param_count": param_count,
                "weight_bytes": weight_bytes,
                "ops_encode_est": ops_encode_est,
                "ops_decode_est": ops_decode_est,
            },
            "train_ratio": float(args.train_ratio),
            "split_seed": int(args.split_seed),
            "shuffle_buffer": int(args.shuffle_buffer),
            "shuffle_seed": int(args.shuffle_seed),
            "epochs": int(args.epochs),
            "min_epochs": int(args.min_epochs),
            "learning_rate": float(args.learning_rate),
            "cycles": int(args.cycles),
            "init_range": float(args.init_range),
            "seed": int(args.seed),
            "weight_clip": float(args.weight_clip) if args.weight_clip is not None else None,
            "max_samples": int(args.max_samples) if args.max_samples is not None else None,
            "norm_windows": int(n),
            "layer_reports": [r.__dict__ for r in layer_reports],
        }
        report_path.write_text(json.dumps(train_report, indent=2), encoding="utf-8")
        print(f"Wrote train report: {report_path}")

    if args.write_artifacts_manifest:
        artifacts_manifest_path = out_dir / str(args.write_artifacts_manifest)
        _write_artifacts_manifest(
            artifacts_manifest_path,
            bam_manifest_path=bam_manifest_path,
            norm_path=norm_path,
            force=bool(args.force),
        )
        print(f"Wrote artifacts manifest: {artifacts_manifest_path}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
