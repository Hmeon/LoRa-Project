from __future__ import annotations

from abc import ABC, abstractmethod


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

