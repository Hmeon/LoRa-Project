from __future__ import annotations

from typing import Sequence


class BamPlaceholderCodec:
    codec_id = "bam_placeholder"
    codec_version = "1"

    def __init__(self, reason: str | None = None) -> None:
        self._reason = reason or "BAM codec artifacts are required"

    def encode(self, window: Sequence[float]) -> bytes:
        raise NotImplementedError(self._reason)

    def decode(self, payload: bytes) -> Sequence[float]:
        raise NotImplementedError(self._reason)

    def payload_schema(self) -> str:
        return "bam_placeholder"

