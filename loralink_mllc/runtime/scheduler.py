from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Iterable, Protocol


class Clock(Protocol):
    def now_ms(self) -> int:
        ...

    def sleep_ms(self, ms: int) -> None:
        ...


class RealClock:
    def now_ms(self) -> int:
        return int(time.monotonic() * 1000)

    def sleep_ms(self, ms: int) -> None:
        time.sleep(ms / 1000.0)


class FakeClock:
    def __init__(self, start_ms: int = 0) -> None:
        self._now = start_ms

    def now_ms(self) -> int:
        return self._now

    def sleep_ms(self, ms: int) -> None:
        self._now += max(0, int(ms))


@dataclass
class Inflight:
    seq: int
    first_tx_ms: int
    last_tx_ms: int
    attempts: int
    toa_ms_est: float


class TxGate:
    def __init__(
        self,
        clock: Clock,
        guard_ms: int,
        ack_timeout_ms: int,
        max_retries: int,
        max_inflight: int = 1,
    ) -> None:
        self._clock = clock
        self._guard_ms = guard_ms
        self._ack_timeout_ms = ack_timeout_ms
        self._max_retries = max_retries
        self._max_inflight = max_inflight
        self._last_tx_start_ms: int | None = None
        self._last_toa_ms: float = 0.0
        self._inflight: Dict[int, Inflight] = {}
        self.sent_count = 0
        self.acked_count = 0
        self.retries_total = 0
        self.total_toa_ms = 0.0

    def can_send(self) -> bool:
        if len(self._inflight) >= self._max_inflight:
            return False
        if self._last_tx_start_ms is None:
            return True
        now = self._clock.now_ms()
        return now >= int(self._last_tx_start_ms + self._last_toa_ms + self._guard_ms)

    def record_send(self, seq: int, toa_ms_est: float) -> int:
        now = self._clock.now_ms()
        if seq in self._inflight:
            inflight = self._inflight[seq]
            inflight.last_tx_ms = now
            inflight.attempts += 1
            inflight.toa_ms_est = toa_ms_est
            self.retries_total += 1
            attempt = inflight.attempts
        else:
            self._inflight[seq] = Inflight(
                seq=seq,
                first_tx_ms=now,
                last_tx_ms=now,
                attempts=1,
                toa_ms_est=toa_ms_est,
            )
            attempt = 1
        self.sent_count += 1
        self.total_toa_ms += toa_ms_est
        self._last_tx_start_ms = now
        self._last_toa_ms = toa_ms_est
        return attempt

    def mark_acked(self, ack_seq: int) -> Inflight | None:
        inflight = self._inflight.pop(ack_seq, None)
        if inflight is None:
            return None
        self.acked_count += 1
        return inflight

    def expired_sequences(self) -> Iterable[int]:
        now = self._clock.now_ms()
        for seq, inflight in list(self._inflight.items()):
            if inflight.attempts > self._max_retries:
                continue
            if now - inflight.last_tx_ms >= self._ack_timeout_ms:
                yield seq

    def expired_failures(self) -> Iterable[Inflight]:
        now = self._clock.now_ms()
        for seq, inflight in list(self._inflight.items()):
            if inflight.attempts <= self._max_retries:
                continue
            if now - inflight.last_tx_ms >= self._ack_timeout_ms:
                yield self._inflight.pop(seq)

    def metrics(self) -> dict:
        pdr = self.acked_count / self.sent_count if self.sent_count else 0.0
        etx = self.sent_count / max(self.acked_count, 1)
        return {
            "sent_count": self.sent_count,
            "acked_count": self.acked_count,
            "retries_total": self.retries_total,
            "pdr": pdr,
            "etx": etx,
            "total_toa_ms": self.total_toa_ms,
        }

    def inflight(self) -> Dict[int, Inflight]:
        return dict(self._inflight)

