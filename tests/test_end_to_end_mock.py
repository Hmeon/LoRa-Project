from pathlib import Path

from loralink_mllc.codecs.base import payload_schema_hash
from loralink_mllc.codecs.raw import RawCodec
from loralink_mllc.config.artifacts import ArtifactsManifest
from loralink_mllc.config.runspec import RunSpec
from loralink_mllc.experiments.controller import run_pair
from loralink_mllc.experiments.metrics import compute_metrics, load_events
from loralink_mllc.radio.mock import create_mock_link
from loralink_mllc.runtime.logging import JsonlLogger
from loralink_mllc.runtime.rx_node import RxNode
from loralink_mllc.runtime.scheduler import FakeClock
from loralink_mllc.runtime.tx_node import DummySampler, TxNode


def _make_runspec(tmp_path: Path, role: str, run_id: str) -> RunSpec:
    data = {
        "run_id": run_id,
        "role": role,
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
        "window": {"dims": 12, "W": 1, "stride": 1, "sample_hz": 1.0},
        "codec": {"id": "raw", "version": "1", "params": {}},
        "tx": {"guard_ms": 0, "ack_timeout_ms": 50, "max_retries": 0, "max_inflight": 1},
        "logging": {"out_dir": str(tmp_path)},
        "max_payload_bytes": 238,
    }
    spec = RunSpec.from_dict(data)
    spec.validate()
    return spec


def test_end_to_end_mock(tmp_path: Path) -> None:
    run_id = "e2e"
    tx_spec = _make_runspec(tmp_path, "tx", run_id)
    rx_spec = _make_runspec(tmp_path, "rx", run_id)
    tx_data = tx_spec.as_dict()
    tx_data["tx"]["max_windows"] = 3
    tx_spec = RunSpec.from_dict(tx_data)
    tx_spec.validate()

    codec = RawCodec()
    schema_hash = payload_schema_hash(codec.payload_schema())
    manifest = ArtifactsManifest.create(
        codec_id=codec.codec_id,
        codec_version=codec.codec_version,
        payload_schema_hash=schema_hash,
    )
    clock = FakeClock()
    link = create_mock_link(clock=clock)

    tx_logger = JsonlLogger(
        tx_spec.logging.out_dir,
        tx_spec.run_id,
        tx_spec.role,
        tx_spec.mode,
        tx_spec.phy_id(),
        clock=clock,
    )
    rx_logger = JsonlLogger(
        rx_spec.logging.out_dir,
        rx_spec.run_id,
        rx_spec.role,
        rx_spec.mode,
        rx_spec.phy_id(),
        clock=clock,
    )
    tx_logger.log_run_start(tx_spec, manifest)
    rx_logger.log_run_start(rx_spec, manifest)

    sampler = DummySampler(tx_spec.window.dims)
    tx_node = TxNode(tx_spec, link.a, codec, tx_logger, sampler, clock=clock)
    rx_node = RxNode(rx_spec, link.b, codec, rx_logger, clock=clock)
    run_pair(tx_node, rx_node, clock, step_ms=1, max_steps=200)
    tx_logger.close()
    rx_logger.close()

    tx_log = tmp_path / f"{run_id}_tx.jsonl"
    events = load_events(tx_log)
    metrics = compute_metrics(events)
    assert metrics["sent_count"] > 0
    assert metrics["acked_count"] == metrics["sent_count"]
    assert metrics["pdr"] == 1.0
    tx_seqs = {e["seq"] for e in events if e.get("event") == "tx_sent"}
    ack_seqs = {e["ack_seq"] for e in events if e.get("event") == "ack_received"}
    assert ack_seqs.issubset(tx_seqs)
