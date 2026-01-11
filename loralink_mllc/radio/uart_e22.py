from __future__ import annotations

from loralink_mllc.radio.base import IRadio


class UartE22Radio(IRadio):
    def __init__(self, port: str, baudrate: int, timeout_ms: int = 1000) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout_ms = timeout_ms
        raise NotImplementedError(
            "UartE22Radio is a placeholder. Provide a concrete UART framing implementation "
            "for your E22 module before use."
        )

    def send(self, frame: bytes) -> None:
        raise NotImplementedError("UART send not implemented")

    def recv(self, timeout_ms: int) -> bytes | None:
        raise NotImplementedError("UART recv not implemented")

    def close(self) -> None:
        return None


