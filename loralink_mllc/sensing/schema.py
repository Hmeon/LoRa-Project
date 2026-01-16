from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

SENSOR_ORDER = (
    "lat",
    "lon",
    "alt",
    "ax",
    "ay",
    "az",
    "gx",
    "gy",
    "gz",
    "roll",
    "pitch",
    "yaw",
)

SENSOR_UNITS = {
    "lat": "deg",
    "lon": "deg",
    "alt": "m",
    "ax": "m/s^2",
    "ay": "m/s^2",
    "az": "m/s^2",
    "gx": "deg/s",
    "gy": "deg/s",
    "gz": "deg/s",
    "roll": "deg",
    "pitch": "deg",
    "yaw": "deg",
}


class SensorSampleError(ValueError):
    pass


def _coerce_float(value: Any, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise SensorSampleError(f"invalid {field} value: {value!r}") from exc


def _coerce_ts_ms(data: Mapping[str, Any]) -> int:
    if "ts_ms" in data:
        return int(float(data["ts_ms"]))
    if "ts" in data:
        return int(float(data["ts"]) * 1000)
    if "timestamp" in data:
        text = str(data["timestamp"])
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as exc:
            raise SensorSampleError(f"invalid timestamp: {data['timestamp']!r}") from exc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    raise SensorSampleError("missing ts_ms/ts/timestamp field")


def _extract_flat_fields(data: Mapping[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    gps = data.get("gps")
    if isinstance(gps, Mapping):
        flat["lat"] = gps.get("lat")
        flat["lon"] = gps.get("lon")
        flat["alt"] = gps.get("alt") if gps.get("alt") is not None else gps.get("altitude")
    accel = data.get("accel")
    if isinstance(accel, Mapping):
        flat["ax"] = accel.get("ax")
        flat["ay"] = accel.get("ay")
        flat["az"] = accel.get("az")
    gyro = data.get("gyro")
    if isinstance(gyro, Mapping):
        flat["gx"] = gyro.get("gx")
        flat["gy"] = gyro.get("gy")
        flat["gz"] = gyro.get("gz")
    attitude = data.get("attitude")
    if isinstance(attitude, Mapping):
        flat["roll"] = attitude.get("roll")
        flat["pitch"] = attitude.get("pitch")
        flat["yaw"] = attitude.get("yaw")
    angle = data.get("angle")
    if isinstance(angle, Mapping):
        flat["roll"] = angle.get("roll")
        flat["pitch"] = angle.get("pitch")
        flat["yaw"] = angle.get("yaw")
    for key in SENSOR_ORDER:
        if key in data:
            flat[key] = data[key]
    return flat


@dataclass(frozen=True)
class SensorSample:
    ts_ms: int
    lat: float
    lon: float
    alt: float
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float
    roll: float
    pitch: float
    yaw: float

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SensorSample":
        ts_ms = _coerce_ts_ms(data)
        flat = _extract_flat_fields(data)
        missing = [field for field in SENSOR_ORDER if flat.get(field) is None]
        if missing:
            raise SensorSampleError(f"missing sensor fields: {', '.join(missing)}")
        return cls(
            ts_ms=ts_ms,
            lat=_coerce_float(flat["lat"], "lat"),
            lon=_coerce_float(flat["lon"], "lon"),
            alt=_coerce_float(flat["alt"], "alt"),
            ax=_coerce_float(flat["ax"], "ax"),
            ay=_coerce_float(flat["ay"], "ay"),
            az=_coerce_float(flat["az"], "az"),
            gx=_coerce_float(flat["gx"], "gx"),
            gy=_coerce_float(flat["gy"], "gy"),
            gz=_coerce_float(flat["gz"], "gz"),
            roll=_coerce_float(flat["roll"], "roll"),
            pitch=_coerce_float(flat["pitch"], "pitch"),
            yaw=_coerce_float(flat["yaw"], "yaw"),
        )

    def vector(self, order: Sequence[str] | None = None) -> list[float]:
        order = order or SENSOR_ORDER
        return [float(getattr(self, field)) for field in order]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ts_ms": self.ts_ms,
            "lat": self.lat,
            "lon": self.lon,
            "alt": self.alt,
            "ax": self.ax,
            "ay": self.ay,
            "az": self.az,
            "gx": self.gx,
            "gy": self.gy,
            "gz": self.gz,
            "roll": self.roll,
            "pitch": self.pitch,
            "yaw": self.yaw,
        }
