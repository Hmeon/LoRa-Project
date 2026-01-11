from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List, Protocol, Sequence

from loralink_mllc.codecs import ICodec
from loralink_mllc.config.runspec import RunSpec
from loralink_mllc.protocol.packet import Packet, PacketError
from loralink_mllc.runtime.logging import JsonlLogger
from loralink_mllc.runtime.scheduler import Clock, RealClock, TxGate
from loralink_mllc.runtime.toa import estimate_toa_ms
from loralink_mllc.radio.base import IRadio


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
    def __init__(self, dims: int, W: int) -> None:
        self._dims = dims
        self._W = W
        self._buffer: Deque[Sequence[float]] = deque(maxlen=W)

    def feed(self, sample: Sequence[float]) -> List[float] | None:
        if len(sample) != self._dims:
            raise ValueError("sample dims do not match window dims")
        self._buffer.append(list(sample))
        if len(self._buffer) < self._W:
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
        for value, mu, sigma in zip(window, self.mean, self.std):
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


class TxNode:
    def __init__(
        self,
        runspec: RunSpec,
        radio: IRadio,
        codec: ICodec,
        logger: JsonlLogger,
        sampler: Sampler,
        clock: Clock | None = None,
    ) -> None:
        self._runspec = runspec
        self._radio = radio
        self._codec = codec
        self._logger = logger
        self._sampler = sampler
        self._clock = clock or RealClock()
        self._gate = TxGate(
            clock=self._clock,
            guard_ms=runspec.tx.guard_ms,
            ack_timeout_ms=runspec.tx.ack_timeout_ms,
            max_retries=runspec.tx.max_retries,
            max_inflight=runspec.tx.max_inflight,
        )
        self._seq = 0
        self._pending: Deque[bytes] = deque()
        self._inflight_payloads: Dict[int, bytes] = {}
        self._builder = WindowBuilder(runspec.window.dims, runspec.window.W)
        self._pre = Preprocessor()
        self._windows_generated = 0
        self._windows_sent = 0
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def is_done(self) -> bool:
        max_windows = self._runspec.tx.max_windows
        if max_windows is None:
            return False
        return (
            self._windows_sent >= max_windows
            and not self._pending
            and not self._gate.inflight()
        )

    def _queue_window(self) -> None:
        max_windows = self._runspec.tx.max_windows
        if max_windows is not None and self._windows_generated >= max_windows:
            return
        sample = self._sampler.sample()
        window = self._builder.feed(sample)
        if window is None:
            return
        processed = self._pre.apply(window)
        payload = self._codec.encode(processed)
        self._pending.append(payload)
        self._windows_generated += 1

    def _handle_incoming(self) -> None:
        while True:
            frame = self._radio.recv(timeout_ms=0)
            if frame is None:
                return
            try:
                packet = Packet.from_bytes(frame)
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
            self._logger.log_event("ack_received", {"ack_seq": ack_seq, "rtt_ms": rtt_ms})
            self._inflight_payloads.pop(ack_seq, None)

    def _retry_expired(self) -> None:
        for seq in list(self._gate.expired_sequences()):
            inflight_payload = self._inflight_payloads.get(seq)
            if inflight_payload is None:
                continue
            if not self._gate.can_send():
                continue
            toa_ms = estimate_toa_ms(self._runspec.phy, len(inflight_payload))
            attempt = self._gate.record_send(seq, toa_ms)
            packet = Packet(payload=inflight_payload, seq=seq)
            self._radio.send(packet.to_bytes())
            self._logger.log_event(
                "tx_sent",
                {
                    "seq": seq,
                    "payload_len": len(inflight_payload),
                    "toa_ms_est": toa_ms,
                    "attempt": attempt,
                },
            )
        for inflight in list(self._gate.expired_failures()):
            self._logger.log_event(
                "tx_failed",
                {
                    "seq": inflight.seq,
                    "reason": "max_retries_exceeded",
                    "attempts": inflight.attempts,
                },
            )
            self._inflight_payloads.pop(inflight.seq, None)

    def _send_pending(self) -> None:
        if not self._pending:
            return
        if not self._gate.can_send():
            return
        payload = self._pending.popleft()
        seq = self._seq
        self._seq = (self._seq + 1) % 256
        toa_ms = estimate_toa_ms(self._runspec.phy, len(payload))
        attempt = self._gate.record_send(seq, toa_ms)
        packet = Packet(payload=payload, seq=seq)
        self._radio.send(packet.to_bytes())
        self._inflight_payloads[seq] = payload
        self._windows_sent += 1
        self._logger.log_event(
            "tx_sent",
            {"seq": seq, "payload_len": len(payload), "toa_ms_est": toa_ms, "attempt": attempt},
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


