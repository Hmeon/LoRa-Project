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

    def to_bytes(self, max_payload_bytes: int | None = None) -> bytes:
        if not (0 <= self.seq <= 255):
            raise PacketError("seq must be 0..255")
        limit = 255 if max_payload_bytes is None else int(max_payload_bytes)
        if limit <= 0 or limit > 255:
            raise PacketError("max_payload_bytes must be 1..255")
        if len(self.payload) > limit:
            raise PacketPayloadTooLarge(
                f"payload length {len(self.payload)} exceeds max_payload_bytes {limit}"
            )
        length = len(self.payload)
        return bytes([length, self.seq]) + self.payload

    @classmethod
    def from_bytes(cls, frame: bytes, max_payload_bytes: int | None = None) -> "Packet":
        if len(frame) < 2:
            raise PacketTooShort("frame must be at least 2 bytes")
        length = frame[0]
        limit = 255 if max_payload_bytes is None else int(max_payload_bytes)
        if limit <= 0 or limit > 255:
            raise PacketError("max_payload_bytes must be 1..255")
        if length > limit:
            raise PacketPayloadTooLarge(
                f"payload length {length} exceeds max_payload_bytes {limit}"
            )
        if len(frame) != length + 2:
            raise PacketLengthMismatch(
                f"frame length {len(frame)} does not match LEN {length}"
            )
        seq = frame[1]
        payload = frame[2:]
        if len(payload) != length:
            raise PacketLengthMismatch("payload length mismatch")
        return cls(payload=payload, seq=seq)

