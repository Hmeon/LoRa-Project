import json
from pathlib import Path

import pytest

from loralink_mllc.codecs import create_codec
from loralink_mllc.codecs.base import CodecError
from loralink_mllc.config.runspec import CodecSpec


def _write_manifest(
    path: Path,
    model_dir: Path,
    latent_dim: int,
    packing: str,
    input_dims: int,
    window_W: int,
    window_stride: int,
    scale: float | None = None,
    delta: float | None = None,
    encode_cycles: int | None = None,
    decode_cycles: int | None = None,
) -> None:
    data = {
        "manifest_version": "1",
        "model_format": "layer_npz_v1",
        "model_path": model_dir.name,
        "latent_dim": latent_dim,
        "packing": packing,
        "input_dims": input_dims,
        "window_W": window_W,
        "window_stride": window_stride,
    }
    if scale is not None:
        data["scale"] = scale
    if delta is not None:
        data["delta"] = delta
    if encode_cycles is not None:
        data["encode_cycles"] = int(encode_cycles)
    if decode_cycles is not None:
        data["decode_cycles"] = int(decode_cycles)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_bam_codec_identity_int16_roundtrip(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    W = np.eye(4, dtype=np.float32)
    V = np.eye(4, dtype=np.float32)
    np.savez(model_dir / "layer_0.npz", W=W, V=V)

    manifest = tmp_path / "bam_manifest.json"
    _write_manifest(
        manifest,
        model_dir,
        latent_dim=4,
        packing="int16",
        input_dims=2,
        window_W=2,
        window_stride=1,
        scale=32767,
    )

    spec = CodecSpec(id="bam", version="0", params={"manifest_path": str(manifest)})
    codec = create_codec(spec)

    window = [0.25, -0.25, 0.5, -0.5]
    payload = codec.encode(window)
    assert len(payload) == 8

    decoded = codec.decode(payload)
    assert decoded == pytest.approx(window, abs=2.0 / 32767.0)

    with pytest.raises(ValueError):
        codec.encode([0.0])
    with pytest.raises(CodecError):
        codec.decode(b"\x00")


def test_bam_codec_identity_int8_roundtrip(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    W = np.eye(4, dtype=np.float32)
    V = np.eye(4, dtype=np.float32)
    np.savez(model_dir / "layer_0.npz", W=W, V=V)

    manifest = tmp_path / "bam_manifest.json"
    _write_manifest(
        manifest,
        model_dir,
        latent_dim=4,
        packing="int8",
        input_dims=2,
        window_W=2,
        window_stride=1,
        scale=127,
    )

    spec = CodecSpec(id="bam", version="0", params={"manifest_path": str(manifest)})
    codec = create_codec(spec)

    window = [0.25, -0.25, 0.5, -0.5]
    payload = codec.encode(window)
    assert len(payload) == 4

    decoded = codec.decode(payload)
    assert decoded == pytest.approx(window, abs=1.0 / 127.0)


def test_bam_codec_delta_float32(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    W = np.eye(2, dtype=np.float32)
    V = np.eye(2, dtype=np.float32)
    np.savez(model_dir / "layer_0.npz", W=W, V=V)

    manifest = tmp_path / "bam_manifest.json"
    _write_manifest(
        manifest,
        model_dir,
        latent_dim=2,
        packing="float32",
        input_dims=2,
        window_W=1,
        window_stride=1,
        delta=0.1,
    )

    spec = CodecSpec(id="bam", version="0", params={"manifest_path": str(manifest)})
    codec = create_codec(spec)

    window = [0.2, -0.1]
    payload = codec.encode(window)
    decoded = codec.decode(payload)

    delta = 0.1
    vec = np.asarray(window, dtype=np.float32)
    expected = (delta + 1.0) * vec - delta * (vec**3)
    expected = (delta + 1.0) * expected - delta * (expected**3)
    assert decoded == pytest.approx(expected.tolist(), abs=1e-6)


def test_bam_codec_recurrent_cycles(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    W = np.eye(2, dtype=np.float32)
    V = np.eye(2, dtype=np.float32)
    np.savez(model_dir / "layer_0.npz", W=W, V=V)

    manifest = tmp_path / "bam_manifest.json"
    _write_manifest(
        manifest,
        model_dir,
        latent_dim=2,
        packing="float32",
        input_dims=2,
        window_W=1,
        window_stride=1,
        delta=0.1,
        encode_cycles=1,
        decode_cycles=1,
    )

    spec = CodecSpec(id="bam", version="0", params={"manifest_path": str(manifest)})
    codec = create_codec(spec)

    window = [0.2, -0.1]
    payload = codec.encode(window)
    decoded = codec.decode(payload)

    delta = 0.1
    vec = np.asarray(window, dtype=np.float32)
    expected = vec
    for _ in range(2 + 2 * 1 + 2 * 1):
        expected = (delta + 1.0) * expected - delta * (expected**3)
        expected = np.clip(expected, -1.0, 1.0)
    assert decoded == pytest.approx(expected.tolist(), abs=1e-6)
