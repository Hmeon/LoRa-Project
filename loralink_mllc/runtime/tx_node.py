from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Protocol, Sequence

from loralink_mllc.codecs import ICodec
from loralink_mllc.config.runspec import RunSpec
from loralink_mllc.protocol.packet import Packet, PacketError
from loralink_mllc.radio.base import IRadio, IRxRssi
from loralink_mllc.runtime.logging import JsonlLogger
from loralink_mllc.runtime.scheduler import Clock, RealClock, TxGate
from loralink_mllc.runtime.toa import estimate_toa_ms
from loralink_mllc.sensing.dataset import DatasetLogger


class Sampler(Protocol):
    def sample(self) -> Sequence[float]:
        ...


class DummySampler:
    def __init__(self, dims: int, seed: int = 0) -> None:
        self._dims = dims
        self._value = float(seed)

    def sample(self) -> Sequence[float]:
        values = [self._value + i for i in range(self._dims)]
        self._value += 1.0
        return values


class WindowBuilder:
    def __init__(self, dims: int, W: int, stride: int) -> None:
        self._dims = dims
        self._W = W
        self._stride = stride
        self._buffer: Deque[Sequence[float]] = deque(maxlen=W)
        self._samples_seen = 0

    def feed(self, sample: Sequence[float]) -> List[float] | None:
        if len(sample) != self._dims:
            raise ValueError("sample dims do not match window dims")
        self._buffer.append(list(sample))
        self._samples_seen += 1
        if len(self._buffer) < self._W:
            return None
        if (self._samples_seen - self._W) % self._stride != 0:
            return None
        window: List[float] = []
        for row in self._buffer:
            window.extend(row)
        return window


@dataclass
class NormParams:
    mean: List[float]
    std: List[float]

    def apply(self, window: Sequence[float]) -> List[float]:
        if len(window) != len(self.mean) or len(window) != len(self.std):
            raise ValueError("norm params length mismatch")
        out = []
        for value, mu, sigma in zip(window, self.mean, self.std, strict=True):
            if sigma == 0:
                out.append(0.0)
            else:
                out.append((value - mu) / sigma)
        return out


class Preprocessor:
    def __init__(self, norm: NormParams | None = None) -> None:
        self._norm = norm

    def apply(self, window: Sequence[float]) -> List[float]:
        if self._norm is None:
            return list(window)
        return self._norm.apply(window)


@dataclass(frozen=True)
class PendingWindow:
    window_id: int
    payload: bytes


class TxNode:
    def __init__(
        self,
        runspec: RunSpec,
        radio: IRadio,
        codec: ICodec,
        logger: JsonlLogger,
        sampler: Sampler,
        dataset_logger: DatasetLogger | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._runspec = runspec
        self._radio = radio
        self._codec = codec
        self._logger = logger
        self._sampler = sampler
        self._dataset_logger = dataset_logger
        self._clock = clock or RealClock()
        self._gate = TxGate(
            clock=self._clock,
            guard_ms=runspec.tx.guard_ms,
            ack_timeout_ms=runspec.tx.ack_timeout_ms,
            max_retries=runspec.tx.max_retries,
            max_inflight=runspec.tx.max_inflight,
        )
        self._seq = 0
        self._max_payload_bytes = runspec.max_payload_bytes
        self._pending: Deque[PendingWindow] = deque()
        self._inflight_payloads: Dict[int, PendingWindow] = {}
        self._builder = WindowBuilder(runspec.window.dims, runspec.window.W, runspec.window.stride)
        self._pre = Preprocessor()
        self._windows_generated = 0
        self._windows_sent = 0
        self._stop = False
        self._no_more_samples = False

    def stop(self) -> None:
        self._stop = True

    def is_done(self) -> bool:
        max_windows = self._runspec.tx.max_windows
        if max_windows is None:
            if not self._no_more_samples:
                return False
            return not self._pending and not self._gate.inflight()
        return (
            self._windows_sent >= max_windows
            and not self._pending
            and not self._gate.inflight()
        )

    def _queue_window(self) -> None:
        if self._no_more_samples:
            return
        max_windows = self._runspec.tx.max_windows
        if max_windows is not None and self._windows_generated >= max_windows:
            return
        try:
            sample = self._sampler.sample()
        except StopIteration:
            self._no_more_samples = True
            return
        window = self._builder.feed(sample)
        if window is None:
            return
        window_id = self._windows_generated
        if self._dataset_logger is not None:
            self._dataset_logger.log_window(window_id, self._clock.now_ms(), window)
        processed = self._pre.apply(window)
        payload = self._codec.encode(processed)
        if len(payload) > self._max_payload_bytes:
            raise ValueError(
                f"payload_bytes {len(payload)} exceeds max_payload_bytes {self._max_payload_bytes}"
            )
        self._pending.append(PendingWindow(window_id=window_id, payload=payload))
        self._windows_generated += 1

    def _handle_incoming(self) -> None:
        while True:
            frame = self._radio.recv(timeout_ms=0)
            if frame is None:
                return
            try:
                packet = Packet.from_bytes(frame, max_payload_bytes=self._max_payload_bytes)
            except PacketError as exc:
                self._logger.log_event("rx_parse_fail", {"reason": str(exc)})
                continue
            if len(packet.payload) != 1:
                continue
            ack_seq = packet.payload[0]
            inflight = self._gate.mark_acked(ack_seq)
            if inflight is None:
                continue
            rtt_ms = self._clock.now_ms() - inflight.first_tx_ms
            ack_payload: dict[str, object] = {"ack_seq": ack_seq, "rtt_ms": rtt_ms}
            window = self._inflight_payloads.get(ack_seq)
            if window is not None:
                ack_payload["window_id"] = window.window_id
            if isinstance(self._radio, IRxRssi):
                rssi_dbm = self._radio.last_rx_rssi_dbm()
                if rssi_dbm is not None:
                    ack_payload["rssi_dbm"] = rssi_dbm
            self._logger.log_event("ack_received", ack_payload)
            self._inflight_payloads.pop(ack_seq, None)

    def _retry_expired(self) -> None:
        for seq in list(self._gate.expired_sequences()):
            inflight_payload = self._inflight_payloads.get(seq)
            if inflight_payload is None:
                continue
            if not self._gate.can_send():
                continue
            toa_ms = estimate_toa_ms(self._runspec.phy, len(inflight_payload.payload))
            attempt = self._gate.record_send(seq, toa_ms)
            packet = Packet(payload=inflight_payload.payload, seq=seq)
            self._radio.send(packet.to_bytes(max_payload_bytes=self._max_payload_bytes))
            self._logger.log_event(
                "tx_sent",
                {
                    "window_id": inflight_payload.window_id,
                    "seq": seq,
                    "payload_bytes": len(inflight_payload.payload),
                    "toa_ms_est": toa_ms,
                    "guard_ms": self._runspec.tx.guard_ms,
                    "attempt": attempt,
                },
            )
        for inflight in list(self._gate.expired_failures()):
            window = self._inflight_payloads.get(inflight.seq)
            payload: Dict[str, object] = {
                "seq": inflight.seq,
                "reason": "max_retries_exceeded",
                "attempts": inflight.attempts,
            }
            if window is not None:
                payload["window_id"] = window.window_id
            self._logger.log_event("tx_failed", payload)
            self._inflight_payloads.pop(inflight.seq, None)

    def _send_pending(self) -> None:
        if not self._pending:
            return
        if not self._gate.can_send():
            return
        window = self._pending.popleft()
        seq = self._seq
        self._seq = (self._seq + 1) % 256
        toa_ms = estimate_toa_ms(self._runspec.phy, len(window.payload))
        attempt = self._gate.record_send(seq, toa_ms)
        packet = Packet(payload=window.payload, seq=seq)
        self._radio.send(packet.to_bytes(max_payload_bytes=self._max_payload_bytes))
        self._inflight_payloads[seq] = window
        self._windows_sent += 1
        self._logger.log_event(
            "tx_sent",
            {
                "window_id": window.window_id,
                "seq": seq,
                "payload_bytes": len(window.payload),
                "toa_ms_est": toa_ms,
                "guard_ms": self._runspec.tx.guard_ms,
                "attempt": attempt,
            },
        )

    def process_once(self) -> None:
        if self._stop:
            return
        self._queue_window()
        self._handle_incoming()
        self._retry_expired()
        self._send_pending()

    def run(self, step_ms: int = 5) -> None:
        while not self._stop and not self.is_done():
            self.process_once()
            self._clock.sleep_ms(step_ms)

    def metrics(self) -> dict:
        return self._gate.metrics()


