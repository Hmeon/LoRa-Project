import pytest

from loralink_mllc.protocol.packet import (
    Packet,
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


