from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


class IRadio(ABC):
    @abstractmethod
    def send(self, frame: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    def recv(self, timeout_ms: int) -> bytes | None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


@runtime_checkable
class IRxRssi(Protocol):
    def last_rx_rssi_dbm(self) -> int | None:
        ...

