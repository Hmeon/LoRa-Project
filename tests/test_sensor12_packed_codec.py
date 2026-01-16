import pytest

from loralink_mllc.codecs import create_codec
from loralink_mllc.codecs.base import CodecError
from loralink_mllc.config.runspec import CodecSpec


def test_sensor12_packed_roundtrip_single_step() -> None:
    spec = CodecSpec(id="sensor12_packed", version="1", params={})
    codec = create_codec(spec)

    window = [
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
    payload = codec.encode(window)
    assert len(payload) == 30
    decoded = codec.decode(payload)

    assert decoded[:3] == pytest.approx(window[:3], abs=1e-5)
    assert decoded[3:6] == pytest.approx(window[3:6], abs=0.5 / 1000.0)
    assert decoded[6:9] == pytest.approx(window[6:9], abs=0.5 / 10.0)
    assert decoded[9:12] == pytest.approx(window[9:12], abs=0.5 / 10.0)


def test_sensor12_packed_roundtrip_two_steps() -> None:
    spec = CodecSpec(id="sensor12_packed", version="1", params={})
    codec = create_codec(spec)

    step = [
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
    window = step + step
    payload = codec.encode(window)
    assert len(payload) == 60
    decoded = codec.decode(payload)
    assert decoded[:12] == pytest.approx(decoded[12:], abs=1e-6)


def test_sensor12_packed_decode_length_mismatch() -> None:
    spec = CodecSpec(id="sensor12_packed", version="1", params={})
    codec = create_codec(spec)
    with pytest.raises(CodecError):
        codec.decode(b"\x00")
