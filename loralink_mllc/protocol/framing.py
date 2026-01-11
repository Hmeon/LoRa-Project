from __future__ import annotations

from loralink_mllc.protocol.packet import Packet


def make_ack_packet(ack_seq: int, seq: int) -> Packet:
    if not (0 <= ack_seq <= 255):
        raise ValueError("ack_seq must be 0..255")
    if not (0 <= seq <= 255):
        raise ValueError("seq must be 0..255")
    return Packet(payload=bytes([ack_seq]), seq=seq)


