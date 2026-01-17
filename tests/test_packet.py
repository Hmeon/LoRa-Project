import pytest

from loralink_mllc.protocol.packet import (
    Packet,
    PacketError,
    PacketLengthMismatch,
    PacketPayloadTooLarge,
    PacketTooShort,
)


def test_packet_roundtrip() -> None:
    payload = b"abc"
    packet = Packet(payload=payload, seq=7)
    decoded = Packet.from_bytes(packet.to_bytes())
    assert decoded == packet


def test_packet_too_short() -> None:
    with pytest.raises(PacketTooShort):
        Packet.from_bytes(b"\x01")


def test_packet_length_mismatch() -> None:
    with pytest.raises(PacketLengthMismatch):
        Packet.from_bytes(bytes([2, 0, 1]))


def test_packet_payload_too_large() -> None:
    with pytest.raises(PacketPayloadTooLarge):
        Packet(payload=bytes(256), seq=0).to_bytes()


def test_packet_max_payload_bytes_cap() -> None:
    packet = Packet(payload=b"abcd", seq=1)
    with pytest.raises(PacketPayloadTooLarge):
        packet.to_bytes(max_payload_bytes=3)
    frame = bytes([3, 1]) + b"abc"
    with pytest.raises(PacketPayloadTooLarge):
        Packet.from_bytes(frame, max_payload_bytes=2)


def test_packet_invalid_seq_and_max_payload_bytes() -> None:
    with pytest.raises(PacketError, match="seq must be 0..255"):
        Packet(payload=b"", seq=-1).to_bytes()
    with pytest.raises(PacketError, match="max_payload_bytes must be 1..255"):
        Packet(payload=b"", seq=0).to_bytes(max_payload_bytes=0)
    with pytest.raises(PacketError, match="max_payload_bytes must be 1..255"):
        Packet.from_bytes(b"\x00\x00", max_payload_bytes=256)


def test_packet_payload_slice_length_mismatch() -> None:
    class _WeirdFrame:
        def __init__(self, data: bytes, sliced_payload: bytes) -> None:
            self._data = data
            self._sliced_payload = sliced_payload

        def __len__(self) -> int:  # pragma: no cover
            return len(self._data)

        def __getitem__(self, key):  # pragma: no cover
            if isinstance(key, slice) and key.start == 2 and key.stop is None:
                return self._sliced_payload
            return self._data[key]

    frame = _WeirdFrame(data=bytes([3, 7]) + b"abc", sliced_payload=b"ab")
    with pytest.raises(PacketLengthMismatch, match="payload length mismatch"):
        Packet.from_bytes(frame)  # type: ignore[arg-type]


