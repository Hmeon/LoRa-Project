import pytest

from loralink_mllc.codecs import create_codec
from loralink_mllc.config.runspec import CodecSpec


def _window() -> list[float]:
    return [
        37.123456,
        127.123456,
        31.2,
        0.01,
        -0.03,
        9.79,
        -0.5,
        1.2,
        0.0,
        0.1,
        -0.2,
        0.0,
    ]


def _codec(*, payload_bytes: int, window_W: int = 1):
    spec = CodecSpec(
        id="sensor12_packed_truncate",
        version="1",
        params={"payload_bytes": payload_bytes, "window_W": window_W},
    )
    return create_codec(spec)


def test_sensor12_packed_truncate_pad_and_ignore_trailing_roundtrip() -> None:
    codec = _codec(payload_bytes=32, window_W=1)
    window = _window()

    payload = codec.encode(window)
    assert len(payload) == 32  # pads 30B sensor12_packed with 2B zeros

    decoded = codec.decode(payload)
    assert decoded[:3] == pytest.approx(window[:3], abs=1e-5)
    assert decoded[3:6] == pytest.approx(window[3:6], abs=0.5 / 1000.0)
    assert decoded[6:9] == pytest.approx(window[6:9], abs=0.5 / 10.0)
    assert decoded[9:12] == pytest.approx(window[9:12], abs=0.5 / 10.0)


def test_sensor12_packed_truncate_truncates_and_pads_for_decode() -> None:
    window = _window()

    codec16 = _codec(payload_bytes=16, window_W=1)
    payload16 = codec16.encode(window)
    assert len(payload16) == 16
    decoded16 = codec16.decode(payload16)
    assert decoded16[:3] == pytest.approx(window[:3], abs=1e-5)
    assert decoded16[3:5] == pytest.approx(window[3:5], abs=0.5 / 1000.0)
    assert decoded16[5:] == [0.0] * 7

    codec8 = _codec(payload_bytes=8, window_W=1)
    payload8 = codec8.encode(window)
    assert len(payload8) == 8
    decoded8 = codec8.decode(payload8)
    assert decoded8[:2] == pytest.approx(window[:2], abs=1e-5)
    assert decoded8[2:] == [0.0] * 10


def test_sensor12_packed_truncate_requires_payload_bytes_and_matching_window_W() -> None:
    with pytest.raises(ValueError, match="payload_bytes"):
        create_codec(CodecSpec(id="sensor12_packed_truncate", version="1", params={}))

    codec = _codec(payload_bytes=16, window_W=2)
    with pytest.raises(ValueError, match="window_W"):
        codec.encode(_window())


def test_sensor12_packed_truncate_additional_error_branches() -> None:
    with pytest.raises(ValueError, match="payload_bytes must be"):
        _codec(payload_bytes=0, window_W=1)
    with pytest.raises(ValueError, match="window_W must be"):
        _codec(payload_bytes=1, window_W=0)

    codec = _codec(payload_bytes=30, window_W=1)
    assert len(codec.encode(_window())) == 30
    assert "payload_bytes=30" in codec.payload_schema()

    with pytest.raises(ValueError, match="multiple of 12"):
        codec.encode([1.0])
