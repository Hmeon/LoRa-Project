import pytest

from loralink_mllc.codecs.base import CodecError
from loralink_mllc.config.runspec import RunSpec
from loralink_mllc.protocol.packet import Packet
from loralink_mllc.runtime.rx_node import RxNode


class _MemLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def log_event(self, event: str, payload: dict[str, object]) -> None:
        self.events.append((event, payload))


class _ScriptedRadio:
    def __init__(self, frames: list[bytes | None]) -> None:
        self._frames = list(frames)
        self.sent: list[bytes] = []

    def recv(self, timeout_ms: int) -> bytes | None:  # noqa: ARG002
        if not self._frames:
            return None
        return self._frames.pop(0)

    def send(self, frame: bytes) -> None:
        self.sent.append(frame)

    def close(self) -> None:  # pragma: no cover
        return None


class _RadioWithRssi(_ScriptedRadio):
    def __init__(self, frames: list[bytes | None], rssi_dbm: int | None) -> None:
        super().__init__(frames)
        self._rssi_dbm = rssi_dbm

    def last_rx_rssi_dbm(self) -> int | None:
        return self._rssi_dbm


class _Codec:
    def __init__(self, decode_behavior: str) -> None:
        self._behavior = decode_behavior

    def encode(self, window):  # pragma: no cover
        raise NotImplementedError

    def decode(self, payload: bytes):
        if self._behavior == "ok":
            return [float(payload[0])]
        if self._behavior == "not_implemented":
            raise NotImplementedError("no decoder")
        if self._behavior == "codec_error":
            raise CodecError("bad payload")
        if self._behavior == "value_error":
            raise ValueError("bad value")
        raise RuntimeError("unknown test behavior")

    def payload_schema(self) -> str:  # pragma: no cover
        return "test"


def _runspec(*, mode: str) -> RunSpec:
    data = {
        "run_id": "rx",
        "role": "rx",
        "mode": mode,
        "phy": {
            "sf": 7,
            "bw_hz": 125000,
            "cr": 5,
            "preamble": 8,
            "crc_on": True,
            "explicit_header": True,
            "tx_power_dbm": 14,
        },
        "window": {"dims": 1, "W": 1, "sample_hz": 1.0},
        "codec": {"id": "raw", "version": "1", "params": {}},
        "tx": {"guard_ms": 0, "ack_timeout_ms": 10, "max_retries": 0, "max_inflight": 1},
        "logging": {"out_dir": "out"},
        "max_payload_bytes": 238,
    }
    spec = RunSpec.from_dict(data)
    spec.validate()
    return spec


def test_rx_node_compute_errors_branches() -> None:
    node = RxNode(_runspec(mode="LATENT"), _ScriptedRadio([]), _Codec("ok"), _MemLogger())
    with pytest.raises(ValueError, match="length mismatch"):
        node._compute_errors([1.0], [])  # type: ignore[arg-type]
    assert node._compute_errors([], []) == (0.0, 0.0)
    assert node._compute_errors([1.0, 3.0], [2.0, 1.0]) == (1.5, 2.5)


def test_rx_node_stop_and_process_once_noop_when_stopped() -> None:
    logger = _MemLogger()
    node = RxNode(_runspec(mode="RAW"), _ScriptedRadio([]), _Codec("ok"), logger)
    node.stop()
    node.process_once()
    assert logger.events == []


def test_rx_node_logs_parse_fail_and_returns() -> None:
    logger = _MemLogger()
    radio = _ScriptedRadio([b"\x01"])  # too short
    node = RxNode(_runspec(mode="RAW"), radio, _Codec("ok"), logger)
    node.process_once()
    assert logger.events[0][0] == "rx_parse_fail"


def test_rx_node_logs_rssi_and_recon_paths() -> None:
    pkt = Packet(payload=b"\x05", seq=7)
    frame = pkt.to_bytes(max_payload_bytes=238)

    logger = _MemLogger()
    radio = _RadioWithRssi([frame], rssi_dbm=-100)

    def truth_provider(seq: int):
        assert seq == 7
        return [5.0]

    node = RxNode(
        _runspec(mode="LATENT"),
        radio,
        _Codec("ok"),
        logger,
        truth_provider=truth_provider,
    )
    node.process_once()
    events = [e for e, _ in logger.events]
    assert "rx_ok" in events
    assert "recon_done" in events
    assert "ack_sent" in events

    rx_ok_payload = dict(logger.events[0][1])
    assert rx_ok_payload["rssi_dbm"] == -100


@pytest.mark.parametrize(
    ("behavior", "event"),
    [
        ("not_implemented", "recon_not_implemented"),
        ("codec_error", "recon_failed"),
        ("value_error", "recon_failed"),
    ],
)
def test_rx_node_recon_error_branches(behavior: str, event: str) -> None:
    pkt = Packet(payload=b"\x01", seq=0)
    frame = pkt.to_bytes(max_payload_bytes=238)
    logger = _MemLogger()
    radio = _ScriptedRadio([frame])
    node = RxNode(
        _runspec(mode="LATENT"),
        radio,
        _Codec(behavior),
        logger,
        truth_provider=lambda s: [1.0],
    )
    node.process_once()
    assert any(e == event for e, _ in logger.events)


def test_rx_node_run_loop_smoke() -> None:
    logger = _MemLogger()
    radio = _ScriptedRadio([None])
    node = RxNode(_runspec(mode="RAW"), radio, _Codec("ok"), logger)

    class _StopClock:
        def now_ms(self) -> int:  # pragma: no cover
            return 0

        def sleep_ms(self, ms: int) -> None:  # noqa: ARG002
            node.stop()

    node = RxNode(_runspec(mode="RAW"), radio, _Codec("ok"), logger, clock=_StopClock())
    node.run(step_ms=0)


def test_rx_node_run_stops_at_max_rx_ok() -> None:
    pkt = Packet(payload=b"\x05", seq=1)
    frame = pkt.to_bytes(max_payload_bytes=238)

    class _Clock:
        def __init__(self) -> None:
            self.now = 0

        def now_ms(self) -> int:
            return self.now

        def sleep_ms(self, ms: int) -> None:
            self.now += ms

    logger = _MemLogger()
    radio = _ScriptedRadio([frame, None, None])
    node = RxNode(_runspec(mode="RAW"), radio, _Codec("ok"), logger, clock=_Clock())
    node.run(step_ms=0, max_rx_ok=1)
    assert any(e == "rx_ok" for e, _ in logger.events)


def test_rx_node_run_stops_at_max_seconds_and_rejects_negative() -> None:
    class _Clock:
        def __init__(self) -> None:
            self.now = 0

        def now_ms(self) -> int:
            return self.now

        def sleep_ms(self, ms: int) -> None:
            self.now += ms

    logger = _MemLogger()
    radio = _ScriptedRadio([None, None, None, None, None])
    node = RxNode(_runspec(mode="RAW"), radio, _Codec("ok"), logger, clock=_Clock())
    with pytest.raises(ValueError, match="max_seconds must be"):
        node.run(step_ms=0, max_seconds=-1)

    node2 = RxNode(_runspec(mode="RAW"), radio, _Codec("ok"), logger, clock=_Clock())
    node2.run(step_ms=5, max_seconds=0.01)
