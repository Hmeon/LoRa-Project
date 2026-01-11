from __future__ import annotations

from dataclasses import dataclass


class PacketError(ValueError):
    pass


class PacketTooShort(PacketError):
    pass


class PacketLengthMismatch(PacketError):
    pass


class PacketPayloadTooLarge(PacketError):
    pass


@dataclass(frozen=True)
class Packet:
    payload: bytes
    seq: int

    def to_bytes(self) -> bytes:
        if not (0 <= self.seq <= 255):
            raise PacketError("seq must be 0..255")
        if len(self.payload) > 255:
            raise PacketPayloadTooLarge("payload length must be 0..255")
        length = len(self.payload)
        return bytes([length, self.seq]) + self.payload

    @classmethod
    def from_bytes(cls, frame: bytes) -> "Packet":
        if len(frame) < 2:
            raise PacketTooShort("frame must be at least 2 bytes")
        length = frame[0]
        if len(frame) != length + 2:
            raise PacketLengthMismatch(
                f"frame length {len(frame)} does not match LEN {length}"
            )
        seq = frame[1]
        payload = frame[2:]
        if len(payload) != length:
            raise PacketLengthMismatch("payload length mismatch")
        return cls(payload=payload, seq=seq)

