from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable


def _require_keys(data: Dict[str, Any], keys: Iterable[str], context: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"missing {context} keys: {joined}")


@dataclass(frozen=True)
class BamArtifacts:
    manifest_version: str
    model_format: str
    model_path: str
    latent_dim: int
    packing: str
    scale: float | None
    delta: float | None
    encode_cycles: int
    decode_cycles: int
    input_dims: int
    window_W: int
    window_stride: int
    norm_path: str | None
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BamArtifacts":
        _require_keys(
            data,
            [
                "manifest_version",
                "model_format",
                "model_path",
                "latent_dim",
                "packing",
                "input_dims",
                "window_W",
                "window_stride",
            ],
            "bam_artifacts",
        )
        scale = data.get("scale")
        encode_cycles = int(data.get("encode_cycles", 0) or 0)
        decode_cycles = int(data.get("decode_cycles", 0) or 0)
        if encode_cycles < 0 or decode_cycles < 0:
            raise ValueError("encode_cycles and decode_cycles must be >= 0")
        return cls(
            manifest_version=str(data["manifest_version"]),
            model_format=str(data["model_format"]),
            model_path=str(data["model_path"]),
            latent_dim=int(data["latent_dim"]),
            packing=str(data["packing"]),
            scale=(float(scale) if scale is not None else None),
            delta=(float(data["delta"]) if data.get("delta") is not None else None),
            encode_cycles=encode_cycles,
            decode_cycles=decode_cycles,
            input_dims=int(data["input_dims"]),
            window_W=int(data["window_W"]),
            window_stride=int(data["window_stride"]),
            norm_path=(str(data["norm_path"]) if data.get("norm_path") else None),
            notes=(str(data["notes"]) if data.get("notes") else None),
        )

    @classmethod
    def load(cls, path: str | Path) -> "BamArtifacts":
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "model_format": self.model_format,
            "model_path": self.model_path,
            "latent_dim": self.latent_dim,
            "packing": self.packing,
            "scale": self.scale,
            "delta": self.delta,
            "encode_cycles": self.encode_cycles,
            "decode_cycles": self.decode_cycles,
            "input_dims": self.input_dims,
            "window_W": self.window_W,
            "window_stride": self.window_stride,
            "norm_path": self.norm_path,
            "notes": self.notes,
        }

    def expected_input_len(self) -> int:
        return self.input_dims * self.window_W

    def expected_payload_bytes(self) -> int | None:
        bytes_per = {
            "int8": 1,
            "int16": 2,
            "float16": 2,
            "float32": 4,
        }.get(self.packing.lower())
        if bytes_per is None:
            return None
        return int(self.latent_dim) * bytes_per
