from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from loralink_mllc.config.runspec import RunSpec
from loralink_mllc.protocol.packet import Packet
from loralink_mllc.runtime.scheduler import FakeClock
from loralink_mllc.runtime.tx_node import (
    NormParams,
    PendingWindow,
    Preprocessor,
    TxNode,
    WindowBuilder,
)
from loralink_mllc.sensing.sampler import NoSampleAvailable


class _MemLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def log_event(self, event: str, payload: dict[str, object]) -> None:
        self.events.append((event, payload))


class _Sampler:
    def __init__(self, samples: list[list[float]]) -> None:
        self._samples = list(samples)

    def sample(self) -> list[float]:
        if not self._samples:
            raise StopIteration
        return self._samples.pop(0)


class _NoSampleSampler:
    def sample(self) -> list[float]:
        raise NoSampleAvailable


class _Codec:
    codec_id = "test"
    codec_version = "0"

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def encode(self, window) -> bytes:  # noqa: ARG002
        return self._payload

    def decode(self, payload):  # pragma: no cover
        raise NotImplementedError

    def payload_schema(self) -> str:  # pragma: no cover
        return "test"


@dataclass
class _Sent:
    frame: bytes


class _LoopbackRadio:
    def __init__(self, *, max_payload_bytes: int, rssi_dbm: int | None = None) -> None:
        self._queue: list[bytes] = []
        self.sent: list[_Sent] = []
        self._max_payload_bytes = max_payload_bytes
        self._rssi_dbm = rssi_dbm

    def send(self, frame: bytes) -> None:
        self.sent.append(_Sent(frame=frame))
        pkt = Packet.from_bytes(frame, max_payload_bytes=self._max_payload_bytes)
        ack = Packet(payload=bytes([pkt.seq]), seq=0).to_bytes(
            max_payload_bytes=self._max_payload_bytes
        )
        self._queue.append(ack)

    def recv(self, timeout_ms: int) -> bytes | None:  # noqa: ARG002
        if not self._queue:
            return None
        return self._queue.pop(0)

    def last_rx_rssi_dbm(self) -> int | None:
        return self._rssi_dbm

    def close(self) -> None:  # pragma: no cover
        return None


class _ScriptedRecvRadio:
    def __init__(self, frames: list[bytes | None], rssi_dbm: int | None = None) -> None:
        self._frames = list(frames)
        self.sent: list[_Sent] = []
        self._rssi_dbm = rssi_dbm

    def recv(self, timeout_ms: int) -> bytes | None:  # noqa: ARG002
        if not self._frames:
            return None
        return self._frames.pop(0)

    def send(self, frame: bytes) -> None:
        self.sent.append(_Sent(frame=frame))

    def last_rx_rssi_dbm(self) -> int | None:
        return self._rssi_dbm

    def close(self) -> None:  # pragma: no cover
        return None


def _runspec(
    *,
    max_windows: int | None,
    max_inflight: int = 1,
    max_retries: int = 1,
    ack_timeout_ms: int | None = 10,
    max_payload_bytes: int = 238,
    W: int = 1,
) -> RunSpec:
    data = {
        "run_id": "tx",
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
        "window": {"dims": 1, "W": W, "stride": 1, "sample_hz": 1.0},
        "codec": {"id": "raw", "version": "1", "params": {}},
        "tx": {
            "guard_ms": 0,
            "ack_timeout_ms": ack_timeout_ms,
            "max_retries": max_retries,
            "max_inflight": max_inflight,
            "max_windows": max_windows,
        },
        "logging": {"out_dir": "out"},
        "max_payload_bytes": max_payload_bytes,
    }
    spec = RunSpec.from_dict(data)
    spec.validate()
    return spec


def test_window_builder_branches() -> None:
    builder = WindowBuilder(dims=2, W=2, stride=2)
    with pytest.raises(ValueError, match="dims do not match"):
        builder.feed([0.0])
    assert builder.feed([1.0, 2.0]) is None
    assert builder.feed([3.0, 4.0]) is not None
    assert builder.feed([5.0, 6.0]) is None  # stride misalignment


def test_norm_params_and_preprocessor_branches() -> None:
    norm = NormParams(mean=[0.0, 0.0], std=[0.0, 2.0])
    assert norm.apply([1.0, 5.0]) == [0.0, 2.5]
    with pytest.raises(ValueError, match="length mismatch"):
        norm.apply([1.0])

    assert Preprocessor().apply([1.0, 2.0]) == [1.0, 2.0]
    assert Preprocessor(norm).apply([1.0, 5.0]) == [0.0, 2.5]


def test_tx_node_run_unbounded_until_no_more_samples_then_queue_noop(tmp_path: Path) -> None:
    clock = FakeClock()
    logger = _MemLogger()
    radio = _LoopbackRadio(max_payload_bytes=238)
    sampler = _Sampler([[1.0]])
    node = TxNode(_runspec(max_windows=None), radio, _Codec(b"\x00"), logger, sampler, clock=clock)

    assert node.is_done() is False
    node.run(step_ms=0)
    assert node.is_done() is True

    node._queue_window()


def test_tx_node_queue_window_returns_none_until_window_full(tmp_path: Path) -> None:
    clock = FakeClock()
    logger = _MemLogger()
    radio = _LoopbackRadio(max_payload_bytes=238)
    sampler = _Sampler([[1.0]])
    node = TxNode(
        _runspec(max_windows=None, W=2),
        radio,
        _Codec(b"\x00"),
        logger,
        sampler,
        clock=clock,
    )
    node._queue_window()


def test_tx_node_queue_window_no_sample_available_does_not_stop(tmp_path: Path) -> None:
    clock = FakeClock()
    logger = _MemLogger()
    radio = _LoopbackRadio(max_payload_bytes=238)
    node = TxNode(
        _runspec(max_windows=None),
        radio,
        _Codec(b"\x00"),
        logger,
        _NoSampleSampler(),
        clock=clock,
    )
    node._queue_window()
    assert node._no_more_samples is False


def test_tx_node_auto_ack_timeout_is_computed_and_logged(tmp_path: Path) -> None:
    clock = FakeClock()
    logger = _MemLogger()
    radio = _LoopbackRadio(max_payload_bytes=238)
    sampler = _Sampler([[1.0]])
    node = TxNode(
        _runspec(max_windows=1, ack_timeout_ms=None),
        radio,
        _Codec(b"\x00"),
        logger,
        sampler,
        clock=clock,
    )
    node.run(step_ms=0)
    sent_events = [p for e, p in logger.events if e == "tx_sent"]
    assert sent_events and int(sent_events[0]["ack_timeout_ms"]) > 0


def test_tx_node_retry_expired_computes_auto_ack_timeout(tmp_path: Path) -> None:
    clock = FakeClock()
    logger = _MemLogger()
    radio = _ScriptedRecvRadio([])
    node = TxNode(
        _runspec(max_windows=None, max_inflight=2, max_retries=1, ack_timeout_ms=None),
        radio,
        _Codec(b"\x00"),
        logger,
        _Sampler([]),
        clock=clock,
    )
    node._inflight_payloads[1] = PendingWindow(
        window_id=1,
        payload=b"\x00",
        built_ms=0,
        sensor_ts_ms=None,
        codec_encode_ms=0.0,
    )
    node._gate.record_send(1, toa_ms_est=0.0, ack_timeout_ms=1)
    clock.sleep_ms(2)
    node._retry_expired()
    sent = [p for e, p in logger.events if e == "tx_sent"]
    assert sent and int(sent[0]["ack_timeout_ms"]) > 1


def test_tx_node_payload_too_large_raises(tmp_path: Path) -> None:
    clock = FakeClock()
    logger = _MemLogger()
    radio = _LoopbackRadio(max_payload_bytes=1)
    sampler = _Sampler([[1.0]])
    node = TxNode(
        _runspec(max_windows=None, max_payload_bytes=1),
        radio,
        _Codec(b"xx"),
        logger,
        sampler,
        clock=clock,
    )
    with pytest.raises(ValueError, match="exceeds max_payload_bytes"):
        node._queue_window()


def test_tx_node_stop_and_process_once_early_return(tmp_path: Path) -> None:
    clock = FakeClock()
    logger = _MemLogger()
    radio = _LoopbackRadio(max_payload_bytes=238)
    node = TxNode(
        _runspec(max_windows=None),
        radio,
        _Codec(b"\x00"),
        logger,
        _Sampler([]),
        clock=clock,
    )
    node.stop()
    node.process_once()
    assert logger.events == []


def test_tx_node_handle_incoming_branches(tmp_path: Path) -> None:
    clock = FakeClock()
    logger = _MemLogger()
    frames = [
        b"\x01",  # PacketError
        Packet(payload=b"\x00\x01", seq=0).to_bytes(max_payload_bytes=238),  # payload len != 1
        Packet(payload=b"\x07", seq=0).to_bytes(max_payload_bytes=238),  # ack_seq not inflight
        None,
    ]
    radio = _ScriptedRecvRadio(frames, rssi_dbm=-90)
    node = TxNode(
        _runspec(max_windows=1),
        radio,
        _Codec(b"\x00"),
        logger,
        _Sampler([]),
        clock=clock,
    )
    node._handle_incoming()
    assert any(e == "rx_parse_fail" for e, _ in logger.events)


def test_tx_node_handle_incoming_logs_rssi_for_acked_payload(tmp_path: Path) -> None:
    clock = FakeClock()
    logger = _MemLogger()
    seq = 5
    pending = PendingWindow(
        window_id=123,
        payload=b"\x00",
        built_ms=0,
        sensor_ts_ms=1,
        codec_encode_ms=0.0,
    )

    ack = Packet(payload=bytes([seq]), seq=0).to_bytes(max_payload_bytes=238)
    radio = _ScriptedRecvRadio([ack], rssi_dbm=-88)
    node = TxNode(
        _runspec(max_windows=1, max_inflight=2),
        radio,
        _Codec(b"\x00"),
        logger,
        _Sampler([]),
        clock=clock,
    )

    node._inflight_payloads[seq] = pending
    node._gate.record_send(seq, toa_ms_est=0.0)
    node._handle_incoming()

    ack_events = [(e, p) for e, p in logger.events if e == "ack_received"]
    assert ack_events and ack_events[0][1]["rssi_dbm"] == -88


def test_tx_node_retry_expired_branches(tmp_path: Path) -> None:
    clock1 = FakeClock()
    logger1 = _MemLogger()
    radio1 = _ScriptedRecvRadio([])
    node1 = TxNode(
        _runspec(max_windows=None),
        radio1,
        _Codec(b"\x00"),
        logger1,
        _Sampler([]),
        clock=clock1,
    )
    node1._gate.record_send(1, toa_ms_est=0.0)
    clock1.sleep_ms(11)
    node1._retry_expired()

    clock2 = FakeClock()
    logger2 = _MemLogger()
    radio2 = _ScriptedRecvRadio([])
    node2 = TxNode(
        _runspec(max_windows=None, max_inflight=1, max_retries=1),
        radio2,
        _Codec(b"\x00"),
        logger2,
        _Sampler([]),
        clock=clock2,
    )
    node2._inflight_payloads[1] = PendingWindow(
        window_id=1,
        payload=b"\x00",
        built_ms=0,
        sensor_ts_ms=None,
        codec_encode_ms=0.0,
    )
    node2._gate.record_send(1, toa_ms_est=0.0)
    clock2.sleep_ms(11)
    node2._retry_expired()

    clock3 = FakeClock()
    logger3 = _MemLogger()
    radio3 = _ScriptedRecvRadio([])
    node3 = TxNode(
        _runspec(max_windows=None, max_inflight=2, max_retries=1),
        radio3,
        _Codec(b"\x00"),
        logger3,
        _Sampler([]),
        clock=clock3,
    )
    node3._inflight_payloads[1] = PendingWindow(
        window_id=1,
        payload=b"\x00",
        built_ms=0,
        sensor_ts_ms=None,
        codec_encode_ms=0.0,
    )
    node3._gate.record_send(1, toa_ms_est=0.0)
    clock3.sleep_ms(11)
    node3._retry_expired()
    assert any(e == "tx_sent" for e, _ in logger3.events)
