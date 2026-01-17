import json
from pathlib import Path

import pytest

from loralink_mllc.codecs.bam_artifacts import BamArtifacts
from loralink_mllc.codecs.bam_placeholder import BamPlaceholderCodec
from loralink_mllc.codecs.base import CodecError
from loralink_mllc.codecs.factory import create_codec
from loralink_mllc.codecs.raw import RawCodec
from loralink_mllc.codecs.sensor12_packed import Sensor12PackedCodec
from loralink_mllc.codecs.zlib_codec import ZlibCodec
from loralink_mllc.config.runspec import CodecSpec


def test_raw_codec_scale_and_clamp_and_decode_errors() -> None:
    with pytest.raises(ValueError, match="scale must be > 0"):
        RawCodec(scale=0)

    codec = RawCodec(scale=40000.0)
    payload = codec.encode([1.0, -1.0])
    assert codec.decode(payload) == pytest.approx([32767 / 40000.0, -32768 / 40000.0])

    with pytest.raises(CodecError, match="payload length must be even"):
        codec.decode(b"\x00")


def test_sensor12_packed_codec_edge_cases() -> None:
    with pytest.raises(ValueError, match="scales must be > 0"):
        Sensor12PackedCodec(accel_scale=0.0)

    codec = Sensor12PackedCodec()
    assert codec.encode([]) == b""
    assert codec.decode(b"") == []

    with pytest.raises(ValueError, match="multiple of 12"):
        codec.encode([0.0])

    window = [
        1.0,
        2.0,
        3.0,
        1e9,
        -1e9,
        0.0,
        1e9,
        -1e9,
        0.0,
        1e9,
        -1e9,
        0.0,
    ]
    payload = codec.encode(window)
    assert len(payload) == 30
    roundtrip = codec.decode(payload)
    assert len(roundtrip) == 12

    with pytest.raises(CodecError, match="payload length mismatch"):
        codec.decode(payload + b"\x00")

    assert "sensor12_packed_v1" in codec.payload_schema()


def test_zlib_codec_invalid_level_and_decode_error() -> None:
    with pytest.raises(ValueError, match="zlib level must be 0..9"):
        ZlibCodec(level=10)
    codec = ZlibCodec()
    with pytest.raises(CodecError, match="could not be decompressed"):
        codec.decode(b"not-a-zlib-payload")


def test_bam_artifacts_validation_and_payload_bytes() -> None:
    with pytest.raises(ValueError, match="missing bam_artifacts keys"):
        BamArtifacts.from_dict({"manifest_version": "1"})

    with pytest.raises(ValueError, match="encode_cycles and decode_cycles must be >= 0"):
        BamArtifacts.from_dict(
            {
                "manifest_version": "1",
                "model_format": "layer_npz_v1",
                "model_path": ".",
                "latent_dim": 2,
                "packing": "float32",
                "input_dims": 2,
                "window_W": 1,
                "window_stride": 1,
                "encode_cycles": -1,
            }
        )

    artifacts = BamArtifacts.from_dict(
        {
            "manifest_version": "1",
            "model_format": "layer_npz_v1",
            "model_path": ".",
            "latent_dim": 2,
            "packing": "unknown",
            "input_dims": 2,
            "window_W": 1,
            "window_stride": 1,
        }
    )
    assert artifacts.as_dict()["packing"] == "unknown"
    assert artifacts.expected_payload_bytes() is None


def test_codec_factory_error_paths_and_placeholder() -> None:
    with pytest.raises(ValueError, match="unknown codec id"):
        create_codec(CodecSpec(id="nope", version="1", params={}))

    with pytest.raises(ValueError, match="bam codec requires"):
        create_codec(CodecSpec(id="bam", version="0", params={}))

    placeholder = create_codec(
        CodecSpec(id="bam_placeholder", version="1", params={"reason": "no artifacts"})
    )
    assert isinstance(placeholder, BamPlaceholderCodec)
    assert placeholder.payload_schema() == "bam_placeholder"
    with pytest.raises(NotImplementedError, match="no artifacts"):
        placeholder.encode([0.0])
    with pytest.raises(NotImplementedError, match="no artifacts"):
        placeholder.decode(b"\x00")


def test_bam_artifacts_load_smoke(tmp_path: Path) -> None:
    path = tmp_path / "bam_manifest.json"
    path.write_text(
        json.dumps(
            {
                "manifest_version": "1",
                "model_format": "layer_npz_v1",
                "model_path": ".",
                "latent_dim": 2,
                "packing": "float32",
                "input_dims": 2,
                "window_W": 1,
                "window_stride": 1,
            }
        ),
        encoding="utf-8",
    )
    loaded = BamArtifacts.load(path)
    assert loaded.manifest_version == "1"
