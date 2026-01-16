from __future__ import annotations

import time

from loralink_mllc.radio.base import IRadio
from loralink_mllc.radio.uart_framing import UartFrameParser


class UartE22Radio(IRadio):
    """
    Minimal UART radio transport that expects application frames on the wire:
    LEN(1B) | SEQ(1B) | PAYLOAD(LEN bytes).

    If the module is configured to append an RSSI byte after each received frame,
    enable `rssi_byte_enabled` to keep framing aligned (the RSSI byte is consumed).

    This does not configure module parameters. It only reads and writes raw bytes.
    """

    def __init__(
        self,
        port: str,
        baudrate: int,
        timeout_ms: int = 1000,
        max_payload_bytes: int = 238,
        rssi_byte_enabled: bool = False,
    ) -> None:
        try:
            import serial  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "pyserial is required for UART mode. Install with `pip install -e .[uart]`."
            ) from exc

        if max_payload_bytes <= 0 or max_payload_bytes > 255:
            raise ValueError("max_payload_bytes must be 1..255")

        self._serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=0,
            write_timeout=max(0.0, timeout_ms / 1000.0),
            )
        self._max_payload_bytes = int(max_payload_bytes)
        self._parser = UartFrameParser(
            max_payload_bytes=self._max_payload_bytes,
            rssi_byte_enabled=rssi_byte_enabled,
        )
        self._last_rx_rssi_dbm: int | None = None

    def _read_available(self) -> bytes:
        try:
            waiting = int(self._serial.in_waiting)
        except Exception:
            waiting = 0
        if waiting <= 0:
            return b""
        return self._serial.read(waiting)

    def _write_all(self, frame: bytes) -> None:
        remaining = memoryview(frame)
        while remaining:
            written = self._serial.write(remaining)
            if written <= 0:
                raise RuntimeError("UART write returned no bytes")
            remaining = remaining[written:]
        self._serial.flush()

    def send(self, frame: bytes) -> None:
        self._write_all(frame)

    def recv(self, timeout_ms: int) -> bytes | None:
        deadline = time.monotonic() + max(0, timeout_ms) / 1000.0
        while True:
            parsed = self._parser.pop()
            if parsed is not None:
                self._last_rx_rssi_dbm = parsed.rssi_dbm
                return parsed.frame
            chunk = self._read_available()
            if chunk:
                self._parser.feed(chunk)
                continue
            if timeout_ms <= 0 or time.monotonic() >= deadline:
                return None
            time.sleep(0.001)

    def last_rx_rssi_dbm(self) -> int | None:
        return self._last_rx_rssi_dbm

    def close(self) -> None:
        try:
            self._serial.close()
        except Exception:
            return None


