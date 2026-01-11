from __future__ import annotations

import zlib
from typing import Sequence

from loralink_mllc.codecs.base import CodecError
from loralink_mllc.codecs.raw import RawCodec


class ZlibCodec:
    codec_id = "zlib"
    codec_version = "1"

    def __init__(self, inner: RawCodec | None = None, level: int = 6) -> None:
        if level < 0 or level > 9:
            raise ValueError("zlib level must be 0..9")
        self._inner = inner or RawCodec()
        self._level = level

    def encode(self, window: Sequence[float]) -> bytes:
        raw = self._inner.encode(window)
        return zlib.compress(raw, level=self._level)

    def decode(self, payload: bytes) -> Sequence[float]:
        try:
            raw = zlib.decompress(payload)
        except zlib.error as exc:
            raise CodecError("zlib payload could not be decompressed") from exc
        return self._inner.decode(raw)

    def payload_schema(self) -> str:
        return f"zlib(level={self._level})+{self._inner.payload_schema()}"


