import pytest

from loralink_mllc.radio.base import IRadio


class _CallsSuper(IRadio):
    def send(self, frame: bytes) -> None:
        return super().send(frame)

    def recv(self, timeout_ms: int) -> bytes | None:
        return super().recv(timeout_ms)

    def close(self) -> None:
        return super().close()


def test_iradio_default_methods_raise() -> None:
    radio = _CallsSuper()
    with pytest.raises(NotImplementedError):
        radio.send(b"")
    with pytest.raises(NotImplementedError):
        radio.recv(0)
    with pytest.raises(NotImplementedError):
        radio.close()

