from __future__ import annotations

from loralink_mllc.codecs.bam import BamCodec
from loralink_mllc.codecs.bam_placeholder import BamPlaceholderCodec
from loralink_mllc.codecs.base import ICodec
from loralink_mllc.codecs.raw import RawCodec
from loralink_mllc.codecs.sensor12_packed import Sensor12PackedCodec
from loralink_mllc.codecs.sensor12_packed_truncate import Sensor12PackedTruncateCodec
from loralink_mllc.codecs.zlib_codec import ZlibCodec
from loralink_mllc.config.runspec import CodecSpec


def create_codec(spec: CodecSpec) -> ICodec:
    codec_id = spec.id.lower()
    params = spec.params
    if codec_id == "raw":
        scale = float(params.get("scale", 32767.0))
        return RawCodec(scale=scale)
    if codec_id == "sensor12_packed":
        accel_scale = float(params.get("accel_scale", 1000.0))
        gyro_scale = float(params.get("gyro_scale", 10.0))
        rpy_scale = float(params.get("rpy_scale", 10.0))
        return Sensor12PackedCodec(
            accel_scale=accel_scale,
            gyro_scale=gyro_scale,
            rpy_scale=rpy_scale,
        )
    if codec_id == "sensor12_packed_truncate":
        payload_bytes = params.get("payload_bytes")
        if payload_bytes is None:
            raise ValueError("sensor12_packed_truncate requires codec.params.payload_bytes")
        window_W = int(params.get("window_W", 1))
        accel_scale = float(params.get("accel_scale", 1000.0))
        gyro_scale = float(params.get("gyro_scale", 10.0))
        rpy_scale = float(params.get("rpy_scale", 10.0))
        return Sensor12PackedTruncateCodec(
            payload_bytes=int(payload_bytes),
            window_W=window_W,
            accel_scale=accel_scale,
            gyro_scale=gyro_scale,
            rpy_scale=rpy_scale,
        )
    if codec_id == "zlib":
        level = int(params.get("level", 6))
        inner_scale = float(params.get("scale", 32767.0))
        return ZlibCodec(inner=RawCodec(scale=inner_scale), level=level)
    if codec_id == "bam_placeholder":
        reason = params.get("reason") or "BAM codec artifacts not configured"
        return BamPlaceholderCodec(reason=reason)
    if codec_id == "bam":
        manifest_path = params.get("manifest_path")
        if not manifest_path:
            raise ValueError("bam codec requires codec.params.manifest_path")
        return BamCodec.from_manifest(manifest_path)
    raise ValueError(f"unknown codec id: {spec.id}")


