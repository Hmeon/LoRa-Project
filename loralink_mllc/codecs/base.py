from __future__ import annotations

import hashlib
from typing import Protocol, Sequence


class CodecError(ValueError):
    pass


class ICodec(Protocol):
    codec_id: str
    codec_version: str

    def encode(self, window: Sequence[float]) -> bytes:
        ...

    def decode(self, payload: bytes) -> Sequence[float]:
        ...

    def payload_schema(self) -> str:
        ...


def payload_schema_hash(schema: str) -> str:
    return hashlib.sha256(schema.encode("utf-8")).hexdigest()

