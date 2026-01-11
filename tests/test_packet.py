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


