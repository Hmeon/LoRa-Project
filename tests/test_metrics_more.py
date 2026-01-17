from pathlib import Path

import pytest

from loralink_mllc.experiments.metrics import (
    _quantile,
    _to_float,
    _to_int,
    compute_metrics,
    load_events,
)


def test_to_int_and_to_float_invalid() -> None:
    assert _to_int("nope") is None
    assert _to_float(object()) is None


def test_quantile_edges_and_errors() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        _quantile([], 0.5)
    assert _quantile([1.0, 2.0, 3.0], 0.0) == 1.0
    assert _quantile([1.0, 2.0, 3.0], 1.0) == 3.0
    assert _quantile([0.0, 10.0], 0.5) == 5.0


def test_load_events_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    path.write_text("{\"event\":\"tx_sent\"}\n\n{\"event\":\"rx_ok\"}\n", encoding="utf-8")
    events = load_events(path)
    assert [e["event"] for e in events] == ["tx_sent", "rx_ok"]


def test_compute_metrics_branches() -> None:
    events = [
        {"event": "tx_sent", "attempt": 1, "window_id": 1, "toa_ms_est": 1.0, "payload_bytes": 1},
        {"event": "tx_sent", "attempt": 2, "window_id": 1, "toa_ms_est": 2.0, "payload_bytes": 1},
        {"event": "rx_ok", "window_id": 1, "rssi_dbm": -120},
        {"event": "ack_received", "window_id": 1, "rtt_ms": 5, "queue_ms": 1, "e2e_ms": 6},
        {"event": "recon_done", "mae": 0.1, "mse": 0.2},
        {"event": "tx_failed"},
        {"event": "rx_parse_fail"},
        {"event": "ack_sent"},
    ]
    report = compute_metrics(events)
    assert report["sent_count"] == 2
    assert report["rx_ok_count"] == 1
    assert report["acked_count"] == 1
    assert report["retries"] == 1
    assert report["pdr"] == 0.5  # rx_ok / tx_sent
    assert report["recon_mae"]["count"] == 1
    assert report["rssi_dbm"]["count"] == 1
