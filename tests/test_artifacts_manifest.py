from __future__ import annotations

import json
from pathlib import Path

import pytest

from loralink_mllc.codecs.base import payload_schema_hash
from loralink_mllc.config.artifacts import ArtifactsManifest, hash_file, verify_manifest
from loralink_mllc.config.runspec import RunSpec


class _DummyBamCodec:
    codec_id = "bam"
    codec_version = "0"

    def encode(self, window):  # pragma: no cover
        raise NotImplementedError

    def decode(self, payload):  # pragma: no cover
        raise NotImplementedError

    def payload_schema(self) -> str:
        return "bam:latent_dim=8:packing=int16:scale=32767"


def _make_bam_runspec(tmp_path: Path, manifest_path: Path) -> RunSpec:
    data = {
        "run_id": "test_bam",
        "role": "tx",
        "mode": "LATENT",
        "phy": {
            "sf": 7,
            "bw_hz": 125000,
            "cr": 5,
            "preamble": 8,
            "crc_on": True,
            "explicit_header": True,
            "tx_power_dbm": 14,
        },
        "window": {"dims": 12, "W": 1, "sample_hz": 1.0},
        "codec": {
            "id": "bam",
            "version": "0",
            "params": {"manifest_path": str(manifest_path)},
        },
        "tx": {"guard_ms": 0, "ack_timeout_ms": 10, "max_retries": 0, "max_inflight": 1},
        "logging": {"out_dir": str(tmp_path)},
    }
    spec = RunSpec.from_dict(data)
    spec.validate()
    return spec


def test_verify_manifest_bam_norm_hash_ok(tmp_path: Path) -> None:
    norm_path = tmp_path / "norm.json"
    norm_path.write_text(json.dumps({"mean": [0.0], "std": [1.0]}), encoding="utf-8")

    bam_manifest_path = tmp_path / "bam_manifest.json"
    bam_manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "1",
                "model_format": "layer_npz_v1",
                "model_path": ".",
                "latent_dim": 8,
                "packing": "int16",
                "scale": 32767,
                "input_dims": 12,
                "window_W": 1,
                "window_stride": 1,
                "norm_path": "norm.json",
            }
        ),
        encoding="utf-8",
    )

    runspec = _make_bam_runspec(tmp_path, bam_manifest_path)
    codec = _DummyBamCodec()
    manifest = ArtifactsManifest(
        codec_id="bam",
        codec_version="0",
        git_commit=None,
        norm_params_hash=hash_file(norm_path),
        payload_schema_hash=payload_schema_hash(codec.payload_schema()),
        created_at="2020-01-01T00:00:00+00:00",
    )

    verify_manifest(runspec, manifest, codec)


def test_verify_manifest_bam_norm_hash_mismatch_raises(tmp_path: Path) -> None:
    norm_path = tmp_path / "norm.json"
    norm_path.write_text(json.dumps({"mean": [0.0], "std": [1.0]}), encoding="utf-8")

    bam_manifest_path = tmp_path / "bam_manifest.json"
    bam_manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "1",
                "model_format": "layer_npz_v1",
                "model_path": ".",
                "latent_dim": 8,
                "packing": "int16",
                "scale": 32767,
                "input_dims": 12,
                "window_W": 1,
                "window_stride": 1,
                "norm_path": "norm.json",
            }
        ),
        encoding="utf-8",
    )

    runspec = _make_bam_runspec(tmp_path, bam_manifest_path)
    codec = _DummyBamCodec()
    manifest = ArtifactsManifest(
        codec_id="bam",
        codec_version="0",
        git_commit=None,
        norm_params_hash="00" * 32,
        payload_schema_hash=payload_schema_hash(codec.payload_schema()),
        created_at="2020-01-01T00:00:00+00:00",
    )

    with pytest.raises(ValueError, match="norm_params_hash does not match norm file"):
        verify_manifest(runspec, manifest, codec)

