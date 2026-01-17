import sys
from types import SimpleNamespace

import pytest

from loralink_mllc.radio.uart_e22 import UartE22Radio


class _FakeSerial:
    def __init__(
        self,
        *,
        port: str,
        baudrate: int,
        timeout: float,
        write_timeout: float,
        read_buffer: bytes = b"",
        max_write: int | None = None,
        write_returns_zero: bool = False,
        in_waiting_raises: bool = False,
        close_raises: bool = False,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self._read_buffer = bytearray(read_buffer)
        self._max_write = max_write
        self._write_returns_zero = write_returns_zero
        self._in_waiting_raises = in_waiting_raises
        self._close_raises = close_raises
        self.writes: list[bytes] = []
        self.flush_called = False

    @property
    def in_waiting(self) -> int:
        if self._in_waiting_raises:
            raise RuntimeError("boom")
        return len(self._read_buffer)

    def read(self, n: int) -> bytes:
        n = max(0, int(n))
        if n <= 0:
            return b""
        out = bytes(self._read_buffer[:n])
        del self._read_buffer[:n]
        return out

    def write(self, data) -> int:  # type: ignore[no-untyped-def]
        if self._write_returns_zero:
            return 0
        chunk = bytes(data)
        if self._max_write is not None:
            chunk = chunk[: self._max_write]
        self.writes.append(chunk)
        return len(chunk)

    def flush(self) -> None:
        self.flush_called = True

    def close(self) -> None:
        if self._close_raises:
            raise RuntimeError("close failed")


def test_uart_e22_requires_pyserial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "serial", raising=False)
    with pytest.raises(RuntimeError, match="pyserial is required"):
        UartE22Radio(port="COM1", baudrate=9600)


def test_uart_e22_invalid_max_payload_bytes_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=_FakeSerial))
    with pytest.raises(ValueError, match="max_payload_bytes must be 1..255"):
        UartE22Radio(port="COM1", baudrate=9600, max_payload_bytes=0)


def test_uart_e22_send_partial_writes_and_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    def serial_factory(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeSerial(**kwargs, max_write=2)

    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=serial_factory))
    radio = UartE22Radio(port="COM1", baudrate=9600)
    radio.send(b"abcdef")
    assert len(radio._serial.writes) >= 3  # type: ignore[attr-defined]
    assert radio._serial.flush_called is True  # type: ignore[attr-defined]


def test_uart_e22_send_write_zero_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def serial_factory(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeSerial(**kwargs, write_returns_zero=True)

    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=serial_factory))
    radio = UartE22Radio(port="COM1", baudrate=9600)
    with pytest.raises(RuntimeError, match="UART write returned no bytes"):
        radio.send(b"x")


def test_uart_e22_recv_parses_frame_and_rssi(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = bytes([1, 2]) + b"x"
    rssi_byte = 156  # -100 dBm

    def serial_factory(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeSerial(**kwargs, read_buffer=frame + bytes([rssi_byte]))

    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=serial_factory))
    radio = UartE22Radio(port="COM1", baudrate=9600, rssi_byte_enabled=True)
    assert radio.recv(timeout_ms=0) == frame
    assert radio.last_rx_rssi_dbm() == -100


def test_uart_e22_recv_timeout_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def serial_factory(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeSerial(**kwargs, read_buffer=b"")

    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=serial_factory))
    radio = UartE22Radio(port="COM1", baudrate=9600)
    assert radio.recv(timeout_ms=0) is None


def test_uart_e22_in_waiting_exception_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    def serial_factory(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeSerial(**kwargs, in_waiting_raises=True)

    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=serial_factory))
    radio = UartE22Radio(port="COM1", baudrate=9600)
    assert radio.recv(timeout_ms=0) is None


def test_uart_e22_recv_waits_and_sleeps(monkeypatch: pytest.MonkeyPatch) -> None:
    import loralink_mllc.radio.uart_e22 as uart_mod

    monotonic_values = [0.0, 0.0, 1.0]

    def fake_monotonic() -> float:
        return monotonic_values.pop(0) if monotonic_values else 1.0

    monkeypatch.setattr(uart_mod.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(uart_mod.time, "sleep", lambda _: None)

    def serial_factory(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeSerial(**kwargs, read_buffer=b"")

    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=serial_factory))
    radio = UartE22Radio(port="COM1", baudrate=9600)
    assert radio.recv(timeout_ms=1) is None


def test_uart_e22_close_ignores_serial_close_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def serial_factory(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeSerial(**kwargs, close_raises=True)

    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=serial_factory))
    radio = UartE22Radio(port="COM1", baudrate=9600)
    assert radio.close() is None
