import json
from pathlib import Path

import pytest

from loralink_mllc.codecs.base import payload_schema_hash
from loralink_mllc.config.artifacts import (
    ArtifactsManifest,
    current_git_commit,
    hash_file,
    verify_manifest,
)
from loralink_mllc.config.runspec import RunSpec


class _DummyCodec:
    codec_id = "raw"
    codec_version = "1"

    def encode(self, window):  # pragma: no cover
        raise NotImplementedError

    def decode(self, payload):  # pragma: no cover
        raise NotImplementedError

    def payload_schema(self) -> str:
        return "raw:int16:le:scale=1"


def _make_runspec(tmp_path: Path, *, codec_id: str = "raw", params: dict | None = None) -> RunSpec:
    data = {
        "run_id": "run",
        "role": "tx",
        "mode": "RAW",
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
        "codec": {"id": codec_id, "version": "1", "params": params or {}},
        "tx": {"guard_ms": 0, "ack_timeout_ms": 10, "max_retries": 0, "max_inflight": 1},
        "logging": {"out_dir": str(tmp_path)},
    }
    spec = RunSpec.from_dict(data)
    spec.validate()
    return spec


def test_current_git_commit_handles_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    import loralink_mllc.config.artifacts as artifacts_mod

    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("no git")

    monkeypatch.setattr(artifacts_mod.subprocess, "run", boom)
    assert current_git_commit() is None

    class _Result:
        stdout = "   \n"

    monkeypatch.setattr(artifacts_mod.subprocess, "run", lambda *a, **k: _Result())  # type: ignore[no-untyped-def]
    assert current_git_commit() is None


def test_artifacts_manifest_roundtrip_and_fingerprint(tmp_path: Path) -> None:
    manifest = ArtifactsManifest(
        codec_id="raw",
        codec_version="1",
        git_commit=None,
        norm_params_hash=None,
        payload_schema_hash="00" * 32,
        created_at="2020-01-01T00:00:00+00:00",
    )
    fp = manifest.fingerprint()
    assert isinstance(fp, str) and len(fp) == 64

    path = tmp_path / "artifacts.json"
    manifest.save(path)
    assert ArtifactsManifest.load(path) == manifest


def test_verify_manifest_mismatch_paths(tmp_path: Path) -> None:
    runspec = _make_runspec(tmp_path)
    codec = _DummyCodec()
    manifest = ArtifactsManifest(
        codec_id="raw",
        codec_version="1",
        git_commit=None,
        norm_params_hash=None,
        payload_schema_hash=payload_schema_hash(codec.payload_schema()),
        created_at="2020-01-01T00:00:00+00:00",
    )
    verify_manifest(runspec, manifest, codec)

    with pytest.raises(ValueError, match="codec_id"):
        bad_id = manifest.__class__(**{**manifest.as_dict(), "codec_id": "nope"})
        verify_manifest(runspec, bad_id, codec)

    with pytest.raises(ValueError, match="codec_version"):
        bad_version = manifest.__class__(**{**manifest.as_dict(), "codec_version": "2"})
        verify_manifest(runspec, bad_version, codec)

    with pytest.raises(ValueError, match="payload_schema_hash"):
        bad_schema = manifest.__class__(**{**manifest.as_dict(), "payload_schema_hash": "11" * 32})
        verify_manifest(runspec, bad_schema, codec)


def test_verify_manifest_norm_hash_requires_paths(tmp_path: Path) -> None:
    norm_path = tmp_path / "norm.json"
    norm_path.write_text(json.dumps({"mean": [0.0], "std": [1.0]}), encoding="utf-8")

    runspec = _make_runspec(tmp_path, params={})
    codec = _DummyCodec()
    manifest = ArtifactsManifest(
        codec_id="raw",
        codec_version="1",
        git_commit=None,
        norm_params_hash=hash_file(norm_path),
        payload_schema_hash=payload_schema_hash(codec.payload_schema()),
        created_at="2020-01-01T00:00:00+00:00",
    )
    with pytest.raises(ValueError, match="runspec has no norm_path"):
        verify_manifest(runspec, manifest, codec)


def test_verify_manifest_norm_hash_non_bam_success(tmp_path: Path) -> None:
    norm_path = tmp_path / "norm.json"
    norm_path.write_text(json.dumps({"mean": [0.0], "std": [1.0]}), encoding="utf-8")

    runspec = _make_runspec(tmp_path, params={"norm_path": str(norm_path)})
    codec = _DummyCodec()
    manifest = ArtifactsManifest(
        codec_id="raw",
        codec_version="1",
        git_commit=None,
        norm_params_hash=hash_file(norm_path),
        payload_schema_hash=payload_schema_hash(codec.payload_schema()),
        created_at="2020-01-01T00:00:00+00:00",
    )
    verify_manifest(runspec, manifest, codec)


def test_verify_manifest_bam_missing_manifest_path(tmp_path: Path) -> None:
    runspec = _make_runspec(tmp_path, codec_id="bam", params={})
    codec = _DummyCodec()
    manifest = ArtifactsManifest(
        codec_id="bam",
        codec_version="1",
        git_commit=None,
        norm_params_hash="00" * 32,
        payload_schema_hash=payload_schema_hash(codec.payload_schema()),
        created_at="2020-01-01T00:00:00+00:00",
    )
    with pytest.raises(ValueError, match="bam runspec missing codec.params.manifest_path"):
        verify_manifest(runspec, manifest, codec)


def test_verify_manifest_bam_manifest_missing_norm_path(tmp_path: Path) -> None:
    norm_path = tmp_path / "norm.json"
    norm_path.write_text(json.dumps({"mean": [0.0], "std": [1.0]}), encoding="utf-8")

    bam_manifest_path = tmp_path / "bam_manifest.json"
    bam_manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "1",
                "model_format": "layer_npz_v1",
                "model_path": ".",
                "latent_dim": 1,
                "packing": "float32",
                "input_dims": 1,
                "window_W": 1,
                "window_stride": 1,
            }
        ),
        encoding="utf-8",
    )

    runspec = _make_runspec(
        tmp_path, codec_id="bam", params={"manifest_path": str(bam_manifest_path)}
    )
    codec = _DummyCodec()
    manifest = ArtifactsManifest(
        codec_id="bam",
        codec_version="1",
        git_commit=None,
        norm_params_hash=hash_file(norm_path),
        payload_schema_hash=payload_schema_hash(codec.payload_schema()),
        created_at="2020-01-01T00:00:00+00:00",
    )
    with pytest.raises(ValueError, match="bam_manifest has no norm_path"):
        verify_manifest(runspec, manifest, codec)
