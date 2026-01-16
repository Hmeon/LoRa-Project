from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedUartFrame:
    frame: bytes
    rssi_dbm: int | None = None


class UartFrameParser:
    """
    Extracts application frames from a byte stream.

    Wire format:
      LEN(1B) | SEQ(1B) | PAYLOAD(LEN bytes) | [RSSI(1B, optional)]

    If `rssi_byte_enabled` is True, the parser consumes 1 trailing byte after each
    frame and converts it to dBm using the Ebyte convention: rssi_dbm = rssi_byte - 256.
    """

    def __init__(self, *, max_payload_bytes: int, rssi_byte_enabled: bool = False) -> None:
        if max_payload_bytes <= 0 or max_payload_bytes > 255:
            raise ValueError("max_payload_bytes must be 1..255")
        self._max_payload_bytes = int(max_payload_bytes)
        self._rssi_byte_enabled = bool(rssi_byte_enabled)
        self._buf = bytearray()

    def feed(self, data: bytes) -> None:
        if data:
            self._buf.extend(data)

    def pop(self) -> ParsedUartFrame | None:
        while True:
            if len(self._buf) < 2:
                return None
            length = self._buf[0]
            if length > self._max_payload_bytes:
                del self._buf[0]
                continue
            total_len = 2 + length + (1 if self._rssi_byte_enabled else 0)
            if len(self._buf) < total_len:
                return None
            frame_end = 2 + length
            frame = bytes(self._buf[:frame_end])
            rssi_dbm = None
            if self._rssi_byte_enabled:
                rssi_byte = self._buf[frame_end]
                rssi_dbm = int(rssi_byte) - 256
            del self._buf[:total_len]
            return ParsedUartFrame(frame=frame, rssi_dbm=rssi_dbm)

    def buffered_bytes(self) -> int:
        return len(self._buf)
