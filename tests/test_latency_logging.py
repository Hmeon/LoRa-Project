import json
from pathlib import Path
from typing import Sequence

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
from loralink_mllc.runtime.tx_node import TxNode
from loralink_mllc.sensing.dataset import DatasetLogger


class _TimedDummySampler:
    def __init__(self, dims: int, *, ts_start_ms: int = 1000) -> None:
        self._dims = int(dims)
        self._ts_ms = int(ts_start_ms)
        self._value = 0.0

    def sample_with_ts(self) -> tuple[int, Sequence[float]]:
        ts = self._ts_ms
        self._ts_ms += 1000
        values = [self._value + i for i in range(self._dims)]
        self._value += 1.0
        return ts, values

    def sample(self) -> Sequence[float]:
        return self.sample_with_ts()[1]


def _make_runspec(tmp_path: Path, role: str, run_id: str, *, max_windows: int) -> RunSpec:
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
        "tx": {
            "guard_ms": 0,
            "ack_timeout_ms": 50,
            "max_retries": 0,
            "max_inflight": 1,
            "max_windows": max_windows,
        },
        "logging": {"out_dir": str(tmp_path)},
        "max_payload_bytes": 238,
    }
    spec = RunSpec.from_dict(data)
    spec.validate()
    return spec


def test_tx_logs_latency_and_cost_fields(tmp_path: Path) -> None:
    run_id = "latency"
    tx_spec = _make_runspec(tmp_path, "tx", run_id, max_windows=2)
    rx_spec = _make_runspec(tmp_path, "rx", run_id, max_windows=2)

    codec = RawCodec()
    manifest = ArtifactsManifest.create(
        codec_id=codec.codec_id,
        codec_version=codec.codec_version,
        payload_schema_hash=payload_schema_hash(codec.payload_schema()),
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

    dataset_path = tmp_path / "dataset.jsonl"
    dataset_logger = DatasetLogger(dataset_path, run_id, order=["x"] * 12, units={})
    sampler = _TimedDummySampler(tx_spec.window.dims)
    tx_node = TxNode(
        tx_spec, link.a, codec, tx_logger, sampler, dataset_logger=dataset_logger, clock=clock
    )
    rx_node = RxNode(rx_spec, link.b, codec, rx_logger, clock=clock)
    run_pair(tx_node, rx_node, clock, step_ms=1, max_steps=500)
    dataset_logger.close()
    tx_logger.close()
    rx_logger.close()

    tx_log = tmp_path / f"{run_id}_tx.jsonl"
    events = load_events(tx_log)

    tx_sent = next(e for e in events if e.get("event") == "tx_sent")
    assert "frame_bytes" in tx_sent
    assert "age_ms" in tx_sent
    assert "codec_encode_ms" in tx_sent
    assert "sensor_ts_ms" in tx_sent

    ack = next(e for e in events if e.get("event") == "ack_received")
    assert "queue_ms" in ack
    assert "e2e_ms" in ack
    assert "codec_encode_ms" in ack
    assert "sensor_ts_ms" in ack
    assert float(ack["e2e_ms"]) >= 0.0
    assert float(ack["queue_ms"]) >= 0.0

    metrics = compute_metrics(events)
    assert metrics["codec_encode_ms"] is not None
    assert metrics["e2e_ms"] is not None


def test_dataset_logger_uses_sensor_ts_ms(tmp_path: Path) -> None:
    run_id = "dataset_ts"
    tx_spec = _make_runspec(tmp_path, "tx", run_id, max_windows=2)
    rx_spec = _make_runspec(tmp_path, "rx", run_id, max_windows=2)

    codec = RawCodec()
    manifest = ArtifactsManifest.create(
        codec_id=codec.codec_id,
        codec_version=codec.codec_version,
        payload_schema_hash=payload_schema_hash(codec.payload_schema()),
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

    dataset_path = tmp_path / "dataset.jsonl"
    dataset_logger = DatasetLogger(dataset_path, run_id, order=["x"] * 12, units={})
    sampler = _TimedDummySampler(tx_spec.window.dims, ts_start_ms=1000)
    tx_node = TxNode(
        tx_spec, link.a, codec, tx_logger, sampler, dataset_logger=dataset_logger, clock=clock
    )
    rx_node = RxNode(rx_spec, link.b, codec, rx_logger, clock=clock)
    run_pair(tx_node, rx_node, clock, step_ms=1, max_steps=500)
    dataset_logger.close()
    tx_logger.close()
    rx_logger.close()

    lines = dataset_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    records = [json.loads(line) for line in lines]
    assert [rec["ts_ms"] for rec in records] == [1000, 2000]

