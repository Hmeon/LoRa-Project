from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from loralink_mllc.codecs.bam_artifacts import BamArtifacts
from loralink_mllc.codecs.base import CodecError


def _require_numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise CodecError(
            "BAM codec requires numpy. Install with `python -m pip install -e .[bam]`."
        ) from exc
    return np


@dataclass(frozen=True)
class BamLayer:
    W: Any
    V: Any


@dataclass(frozen=True)
class BamNorm:
    mean: Any
    std: Any


def _parse_layer_index(path: Path) -> int:
    match = re.match(r"layer_(\d+)\.npz$", path.name)
    if not match:
        raise CodecError(f"invalid layer filename: {path.name}")
    return int(match.group(1))


class BamCodec:
    codec_id = "bam"
    codec_version = "0"

    def __init__(self, artifacts: BamArtifacts, base_dir: Path | None = None) -> None:
        self._artifacts = artifacts
        self._base_dir = base_dir or Path(".")
        self._layers: list[BamLayer] = []
        self._norm: BamNorm | None = None
        self._validate_dynamics()
        self._load_layers()
        self._load_norm()

    def _validate_dynamics(self) -> None:
        if self._artifacts.encode_cycles < 0 or self._artifacts.decode_cycles < 0:
            raise CodecError("bam encode_cycles/decode_cycles must be >= 0")
        delta = self._artifacts.delta
        if (self._artifacts.encode_cycles or self._artifacts.decode_cycles) and delta is not None:
            if float(delta) >= 0.5:
                raise CodecError(
                    "bam delta must be < 0.5 when encode_cycles/decode_cycles are enabled"
                )

    @classmethod
    def from_manifest(cls, manifest_path: str) -> "BamCodec":
        path = Path(manifest_path)
        artifacts = BamArtifacts.load(path)
        return cls(artifacts, base_dir=path.parent)

    def _resolve_path(self, path: str) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return (self._base_dir / candidate).resolve()

    def _load_layers(self) -> None:
        if self._artifacts.model_format != "layer_npz_v1":
            raise CodecError(f"unsupported bam model_format: {self._artifacts.model_format}")
        model_path = self._resolve_path(self._artifacts.model_path)
        if not model_path.exists():
            raise CodecError(f"bam model_path does not exist: {model_path}")
        if not model_path.is_dir():
            raise CodecError("layer_npz_v1 requires model_path to be a directory")

        layer_files = sorted(model_path.glob("layer_*.npz"), key=_parse_layer_index)
        if not layer_files:
            raise CodecError(f"no layer_*.npz files found in {model_path}")

        np = _require_numpy()
        expected_input = self._artifacts.expected_input_len()
        prev_out = None
        layers: list[BamLayer] = []
        for layer_path in layer_files:
            with np.load(layer_path) as data:
                if "W" not in data or "V" not in data:
                    raise CodecError(f"layer file missing W/V: {layer_path}")
                W = np.asarray(data["W"], dtype=np.float32)
                V = np.asarray(data["V"], dtype=np.float32)
            if W.ndim != 2 or V.ndim != 2:
                raise CodecError(f"layer weights must be 2D: {layer_path}")
            if V.shape != (W.shape[1], W.shape[0]):
                raise CodecError(f"layer V shape mismatch with W: {layer_path}")
            if prev_out is None:
                if W.shape[1] != expected_input:
                    raise CodecError(
                        f"layer input dim {W.shape[1]} does not match expected {expected_input}"
                    )
            else:
                if W.shape[1] != prev_out:
                    raise CodecError(
                        f"layer input dim {W.shape[1]} does not match previous {prev_out}"
                    )
            prev_out = int(W.shape[0])
            layers.append(BamLayer(W=W, V=V))

        if prev_out != self._artifacts.latent_dim:
            raise CodecError(
                f"latent_dim {self._artifacts.latent_dim} does not match model output {prev_out}"
            )
        self._layers = layers

    def _load_norm(self) -> None:
        if not self._artifacts.norm_path:
            return
        norm_path = self._resolve_path(self._artifacts.norm_path)
        if not norm_path.exists():
            raise CodecError(f"norm_path does not exist: {norm_path}")
        data = json.loads(norm_path.read_text(encoding="utf-8"))
        if "mean" not in data or "std" not in data:
            raise CodecError("norm file must contain mean and std arrays")
        mean = data["mean"]
        std = data["std"]
        if not isinstance(mean, list) or not isinstance(std, list):
            raise CodecError("norm mean/std must be lists")
        expected = self._artifacts.expected_input_len()
        if len(mean) != expected or len(std) != expected:
            raise CodecError("norm mean/std length does not match expected input length")
        np = _require_numpy()
        mean_arr = np.asarray(mean, dtype=np.float32)
        std_arr = np.asarray(std, dtype=np.float32)
        if (std_arr < 0).any():
            raise CodecError("norm std must be non-negative")
        self._norm = BamNorm(mean=mean_arr, std=std_arr)

    def _apply_norm(self, vector: Any) -> Any:
        if self._norm is None:
            return vector
        np = _require_numpy()
        mean = self._norm.mean
        std = self._norm.std
        if vector.shape[0] != mean.shape[0]:
            raise CodecError("norm input length mismatch")
        safe_std = np.where(std == 0, 1.0, std)
        out = (vector - mean) / safe_std
        return np.where(std == 0, 0.0, out)

    def _invert_norm(self, vector: Any) -> Any:
        if self._norm is None:
            return vector
        np = _require_numpy()
        mean = self._norm.mean
        std = self._norm.std
        if vector.shape[0] != mean.shape[0]:
            raise CodecError("norm input length mismatch")
        out = vector * std + mean
        return np.where(std == 0, mean, out)

    def _transmission(self, vector: Any) -> Any:
        delta = self._artifacts.delta
        if delta is None or float(delta) == 0.0:
            return vector
        np = _require_numpy()
        out = (delta + 1.0) * vector - delta * (vector**3)
        return np.clip(out, -1.0, 1.0)

    def _require_scale(self) -> float:
        scale = self._artifacts.scale
        if scale is None:
            raise CodecError("bam packing requires scale")
        if scale <= 0:
            raise CodecError("bam scale must be positive")
        return float(scale)

    def _pack(self, vector: Any) -> bytes:
        np = _require_numpy()
        packing = self._artifacts.packing.lower()
        vector = np.asarray(vector, dtype=np.float32).reshape(-1)
        if vector.shape[0] != self._artifacts.latent_dim:
            raise CodecError("latent vector length does not match latent_dim")
        if packing == "int8":
            scale = self._require_scale()
            info = np.iinfo(np.int8)
            scaled = np.rint(vector * scale)
            scaled = np.clip(scaled, info.min, info.max).astype(np.int8)
            return scaled.tobytes()
        if packing == "int16":
            scale = self._require_scale()
            info = np.iinfo(np.int16)
            scaled = np.rint(vector * scale)
            scaled = np.clip(scaled, info.min, info.max).astype(np.int16)
            return scaled.tobytes()
        if packing == "float16":
            return vector.astype(np.float16).tobytes()
        if packing == "float32":
            return vector.astype(np.float32).tobytes()
        raise CodecError(f"unsupported bam packing: {self._artifacts.packing}")

    def _unpack(self, payload: bytes) -> Any:
        np = _require_numpy()
        packing = self._artifacts.packing.lower()
        if packing == "int8":
            scale = self._require_scale()
            vector = np.frombuffer(payload, dtype=np.int8).astype(np.float32)
            if vector.shape[0] != self._artifacts.latent_dim:
                raise CodecError("payload latent length mismatch")
            return vector / scale
        if packing == "int16":
            scale = self._require_scale()
            vector = np.frombuffer(payload, dtype=np.int16).astype(np.float32)
            if vector.shape[0] != self._artifacts.latent_dim:
                raise CodecError("payload latent length mismatch")
            return vector / scale
        if packing == "float16":
            vector = np.frombuffer(payload, dtype=np.float16).astype(np.float32)
            if vector.shape[0] != self._artifacts.latent_dim:
                raise CodecError("payload latent length mismatch")
            return vector
        if packing == "float32":
            vector = np.frombuffer(payload, dtype=np.float32).astype(np.float32)
            if vector.shape[0] != self._artifacts.latent_dim:
                raise CodecError("payload latent length mismatch")
            return vector
        raise CodecError(f"unsupported bam packing: {self._artifacts.packing}")

    def encode(self, window: Sequence[float]) -> bytes:
        expected_len = self._artifacts.expected_input_len()
        if len(window) != expected_len:
            raise ValueError(
                f"bam window length {len(window)} does not match expected {expected_len}"
            )
        np = _require_numpy()
        vector = np.asarray(window, dtype=np.float32).reshape(-1)
        vector = self._apply_norm(vector)
        encode_cycles = int(self._artifacts.encode_cycles)
        for layer in self._layers:
            y0 = layer.W @ vector
            y0 = self._transmission(y0)
            if encode_cycles <= 0:
                vector = y0
                continue
            y_c = y0
            x_c = vector
            for _ in range(encode_cycles):
                x_c = layer.V @ y_c
                x_c = self._transmission(x_c)
                y_c = layer.W @ x_c
                y_c = self._transmission(y_c)
            vector = y_c
        return self._pack(vector)

    def decode(self, payload: bytes) -> Sequence[float]:
        expected_bytes = self._artifacts.expected_payload_bytes()
        if expected_bytes is not None and len(payload) != expected_bytes:
            raise CodecError(
                f"bam payload length {len(payload)} does not match expected {expected_bytes}"
            )
        vector = self._unpack(payload)
        decode_cycles = int(self._artifacts.decode_cycles)
        for layer in reversed(self._layers):
            x0 = layer.V @ vector
            x0 = self._transmission(x0)
            if decode_cycles <= 0:
                vector = x0
                continue
            x_c = x0
            y_c = vector
            for _ in range(decode_cycles):
                y_c = layer.W @ x_c
                y_c = self._transmission(y_c)
                x_c = layer.V @ y_c
                x_c = self._transmission(x_c)
            vector = x_c
        vector = self._invert_norm(vector)
        return vector.tolist()

    def payload_schema(self) -> str:
        scale = self._artifacts.scale if self._artifacts.scale is not None else "none"
        return (
            "bam:"
            f"latent_dim={self._artifacts.latent_dim}:"
            f"packing={self._artifacts.packing}:"
            f"scale={scale}"
        )
