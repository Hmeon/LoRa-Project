from __future__ import annotations

import struct
from typing import Sequence

from loralink_mllc.codecs.base import CodecError


class RawCodec:
    codec_id = "raw"
    codec_version = "1"

    def __init__(self, scale: float = 32767.0) -> None:
        if scale <= 0:
            raise ValueError("scale must be > 0")
        self._scale = float(scale)

    def encode(self, window: Sequence[float]) -> bytes:
        values = []
        for value in window:
            clamped = max(-1.0, min(1.0, float(value)))
            q = int(round(clamped * self._scale))
            if q < -32768:
                q = -32768
            if q > 32767:
                q = 32767
            values.append(q)
        fmt = "<" + "h" * len(values)
        return struct.pack(fmt, *values)

    def decode(self, payload: bytes) -> Sequence[float]:
        if len(payload) % 2 != 0:
            raise CodecError("raw payload length must be even")
        count = len(payload) // 2
        fmt = "<" + "h" * count
        ints = struct.unpack(fmt, payload)
        return [val / self._scale for val in ints]

    def payload_schema(self) -> str:
        return f"raw:int16:le:scale={self._scale}"


