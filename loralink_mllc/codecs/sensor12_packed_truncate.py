from __future__ import annotations

from typing import Sequence

from loralink_mllc.codecs.sensor12_packed import Sensor12PackedCodec


class Sensor12PackedTruncateCodec:
    """
    Baseline lossy codec that slices or zero-pads the `sensor12_packed` byte stream to a fixed
    on-air payload length.

    Intended for payload-size experiments (e.g., 32/16/8 bytes) to compare link metrics and the
    impact of naive truncation vs learned compression (BAM).
    """

    codec_id = "sensor12_packed_truncate"
    codec_version = "1"

    def __init__(
        self,
        *,
        payload_bytes: int,
        window_W: int = 1,
        accel_scale: float = 1000.0,
        gyro_scale: float = 10.0,
        rpy_scale: float = 10.0,
    ) -> None:
        payload_bytes = int(payload_bytes)
        window_W = int(window_W)
        if payload_bytes <= 0 or payload_bytes > 255:
            raise ValueError("payload_bytes must be 1..255")
        if window_W <= 0:
            raise ValueError("window_W must be > 0")
        self._payload_bytes = payload_bytes
        self._window_W = window_W
        self._inner = Sensor12PackedCodec(
            accel_scale=accel_scale,
            gyro_scale=gyro_scale,
            rpy_scale=rpy_scale,
        )

    def _full_len(self) -> int:
        return int(self._inner._STEP_SIZE) * int(self._window_W)

    def encode(self, window: Sequence[float]) -> bytes:
        if len(window) % 12 != 0:
            raise ValueError("sensor12_packed_truncate window length must be a multiple of 12")
        inferred_W = len(window) // 12
        if inferred_W != self._window_W:
            raise ValueError(
                f"window_W {self._window_W} does not match inferred W {inferred_W} from input"
            )
        full = self._inner.encode(window)
        if len(full) > self._payload_bytes:
            return full[: self._payload_bytes]
        if len(full) < self._payload_bytes:
            return full + (b"\x00" * (self._payload_bytes - len(full)))
        return full

    def decode(self, payload: bytes) -> Sequence[float]:
        full_len = self._full_len()
        if len(payload) > full_len:
            payload = payload[:full_len]
        if len(payload) < full_len:
            payload = payload + (b"\x00" * (full_len - len(payload)))
        return self._inner.decode(payload)

    def payload_schema(self) -> str:
        return (
            "sensor12_packed_truncate_v1:"
            f"payload_bytes={self._payload_bytes}:"
            f"W={self._window_W}:"
            f"inner={self._inner.payload_schema()}"
        )

