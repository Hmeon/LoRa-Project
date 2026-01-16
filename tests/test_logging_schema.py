import json
from pathlib import Path

from loralink_mllc.codecs import payload_schema_hash
from loralink_mllc.codecs.raw import RawCodec
from loralink_mllc.config.artifacts import ArtifactsManifest
from loralink_mllc.config.runspec import RunSpec
from loralink_mllc.runtime.logging import JsonlLogger
from loralink_mllc.runtime.scheduler import FakeClock


def _make_runspec(tmp_path: Path) -> RunSpec:
    data = {
        "run_id": "test_run",
        "role": "tx",
        "mode": "RAW",
        "phy": {
            "sf": 7,
            "bw_hz": 125000,
            "cr": 5,
            "preamble": 8,
            "crc_on": True,
            "explicit_header": True,
            "tx_power_dbm": 14,
        },
        "window": {"dims": 12, "W": 1, "sample_hz": 1.0},
        "codec": {"id": "raw", "version": "1", "params": {}},
        "tx": {"guard_ms": 0, "ack_timeout_ms": 10, "max_retries": 0, "max_inflight": 1},
        "logging": {"out_dir": str(tmp_path)},
    }
    spec = RunSpec.from_dict(data)
    spec.validate()
    return spec


def test_jsonl_logging_schema(tmp_path: Path) -> None:
    spec = _make_runspec(tmp_path)
    codec = RawCodec()
    manifest = ArtifactsManifest.create(
        codec_id=codec.codec_id,
        codec_version=codec.codec_version,
        payload_schema_hash=payload_schema_hash(codec.payload_schema()),
    )
    clock = FakeClock()
    logger = JsonlLogger(
        spec.logging.out_dir,
        spec.run_id,
        spec.role,
        spec.mode,
        spec.phy_id(),
        clock=clock,
    )
    logger.log_run_start(spec, manifest)
    logger.log_event(
        "tx_sent",
        {"seq": 1, "payload_bytes": 2, "toa_ms_est": 5.0, "guard_ms": 0, "attempt": 1},
    )
    logger.log_event("ack_received", {"ack_seq": 1, "rtt_ms": 5})
    logger.close()

    path = tmp_path / "test_run_tx.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    for line in lines:
        event = json.loads(line)
        for field in ("ts_ms", "run_id", "event", "role", "mode", "phy_id"):
            assert field in event


