from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Sequence

from loralink_mllc.codecs.base import CodecError


def _clamp_int16(value: int) -> int:
    if value < -32768:
        return -32768
    if value > 32767:
        return 32767
    return int(value)


@dataclass(frozen=True)
class _Scales:
    accel: float
    gyro: float
    rpy: float


class Sensor12PackedCodec:
    """
    Binary on-air payload codec for the fixed 12D sensor vector:
      [lat, lon, alt, ax, ay, az, gx, gy, gz, roll, pitch, yaw]

    Packing (per step, little-endian):
      - lat, lon, alt: float32
      - ax..az: int16 (scaled)
      - gx..gz: int16 (scaled)
      - roll..yaw: int16 (scaled)

    Total per step: 30 bytes. For a window with W steps, payload is 30 * W bytes.
    """

    codec_id = "sensor12_packed"
    codec_version = "1"

    _STEP_FMT = "<fff" + ("h" * 9)
    _STEP_SIZE = struct.calcsize(_STEP_FMT)

    def __init__(
        self,
        *,
        accel_scale: float = 1000.0,
        gyro_scale: float = 10.0,
        rpy_scale: float = 10.0,
    ) -> None:
        if accel_scale <= 0 or gyro_scale <= 0 or rpy_scale <= 0:
            raise ValueError("scales must be > 0")
        self._scale = _Scales(
            accel=float(accel_scale),
            gyro=float(gyro_scale),
            rpy=float(rpy_scale),
        )

    def encode(self, window: Sequence[float]) -> bytes:
        if len(window) % 12 != 0:
            raise ValueError("sensor12_packed window length must be a multiple of 12")
        if not window:
            return b""

        out = bytearray()
        for i in range(0, len(window), 12):
            lat = float(window[i + 0])
            lon = float(window[i + 1])
            alt = float(window[i + 2])

            ax = _clamp_int16(round(float(window[i + 3]) * self._scale.accel))
            ay = _clamp_int16(round(float(window[i + 4]) * self._scale.accel))
            az = _clamp_int16(round(float(window[i + 5]) * self._scale.accel))

            gx = _clamp_int16(round(float(window[i + 6]) * self._scale.gyro))
            gy = _clamp_int16(round(float(window[i + 7]) * self._scale.gyro))
            gz = _clamp_int16(round(float(window[i + 8]) * self._scale.gyro))

            roll = _clamp_int16(round(float(window[i + 9]) * self._scale.rpy))
            pitch = _clamp_int16(round(float(window[i + 10]) * self._scale.rpy))
            yaw = _clamp_int16(round(float(window[i + 11]) * self._scale.rpy))

            out.extend(
                struct.pack(
                    self._STEP_FMT,
                    lat,
                    lon,
                    alt,
                    ax,
                    ay,
                    az,
                    gx,
                    gy,
                    gz,
                    roll,
                    pitch,
                    yaw,
                )
            )
        return bytes(out)

    def decode(self, payload: bytes) -> Sequence[float]:
        if len(payload) % self._STEP_SIZE != 0:
            raise CodecError("sensor12_packed payload length mismatch")
        if not payload:
            return []

        out: list[float] = []
        for i in range(0, len(payload), self._STEP_SIZE):
            (
                lat,
                lon,
                alt,
                ax,
                ay,
                az,
                gx,
                gy,
                gz,
                roll,
                pitch,
                yaw,
            ) = struct.unpack_from(self._STEP_FMT, payload, i)
            out.extend(
                [
                    float(lat),
                    float(lon),
                    float(alt),
                    float(ax) / self._scale.accel,
                    float(ay) / self._scale.accel,
                    float(az) / self._scale.accel,
                    float(gx) / self._scale.gyro,
                    float(gy) / self._scale.gyro,
                    float(gz) / self._scale.gyro,
                    float(roll) / self._scale.rpy,
                    float(pitch) / self._scale.rpy,
                    float(yaw) / self._scale.rpy,
                ]
            )
        return out

    def payload_schema(self) -> str:
        return (
            "sensor12_packed_v1:"
            "le:"
            "gps=f32,f32,f32:"
            f"accel=i16@{self._scale.accel}:"
            f"gyro=i16@{self._scale.gyro}:"
            f"rpy=i16@{self._scale.rpy}"
        )
