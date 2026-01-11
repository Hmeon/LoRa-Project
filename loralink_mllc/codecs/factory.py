from __future__ import annotations

from loralink_mllc.codecs.base import ICodec
from loralink_mllc.codecs.bam_placeholder import BamPlaceholderCodec
from loralink_mllc.codecs.raw import RawCodec
from loralink_mllc.codecs.zlib_codec import ZlibCodec
from loralink_mllc.config.runspec import CodecSpec


def create_codec(spec: CodecSpec) -> ICodec:
    codec_id = spec.id.lower()
    params = spec.params
    if codec_id == "raw":
        scale = float(params.get("scale", 32767.0))
        return RawCodec(scale=scale)
    if codec_id == "zlib":
        level = int(params.get("level", 6))
        inner_scale = float(params.get("scale", 32767.0))
        return ZlibCodec(inner=RawCodec(scale=inner_scale), level=level)
    if codec_id == "bam_placeholder":
        reason = params.get("reason") or "BAM codec artifacts not configured"
        return BamPlaceholderCodec(reason=reason)
    raise ValueError(f"unknown codec id: {spec.id}")


