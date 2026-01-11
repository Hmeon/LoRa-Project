from __future__ import annotations

import heapq
import random
from dataclasses import dataclass
from typing import List, Optional

from loralink_mllc.radio.base import IRadio
from loralink_mllc.runtime.scheduler import Clock, RealClock


@dataclass(order=True)
class _Delivery:
    deliver_at_ms: int
    frame: bytes


class _LossModel:
    def __init__(self, loss_rate: float, seed: int, drop_pattern: List[bool] | None) -> None:
        self._rng = random.Random(seed)
        self._loss_rate = loss_rate
        self._drop_pattern = drop_pattern
        self._counter = 0

    def should_drop(self) -> bool:
        if self._drop_pattern:
            drop = self._drop_pattern[self._counter % len(self._drop_pattern)]
            self._counter += 1
            return drop
        return self._rng.random() < self._loss_rate


class MockLink:
    def __init__(
        self,
        loss_rate: float = 0.0,
        latency_ms: int = 0,
        seed: int = 0,
        drop_pattern: List[bool] | None = None,
        clock: Clock | None = None,
        loss_rate_ab: float | None = None,
        loss_rate_ba: float | None = None,
        drop_pattern_ab: List[bool] | None = None,
        drop_pattern_ba: List[bool] | None = None,
    ) -> None:
        self._clock = clock or RealClock()
        self._loss_ab = _LossModel(
            loss_rate if loss_rate_ab is None else loss_rate_ab,
            seed,
            drop_pattern if drop_pattern_ab is None else drop_pattern_ab,
        )
        self._loss_ba = _LossModel(
            loss_rate if loss_rate_ba is None else loss_rate_ba,
            seed + 1,
            drop_pattern if drop_pattern_ba is None else drop_pattern_ba,
        )
        self._latency_ms = latency_ms
        self._queues = {"a": [], "b": []}
        self.a = MockRadio(self, "a")
        self.b = MockRadio(self, "b")

    def _send(self, sender: str, frame: bytes) -> None:
        loss = self._loss_ab if sender == "a" else self._loss_ba
        if loss.should_drop():
            return
        peer = "b" if sender == "a" else "a"
        deliver_at = self._clock.now_ms() + self._latency_ms
        heapq.heappush(self._queues[peer], _Delivery(deliver_at, frame))

    def _recv(self, receiver: str, timeout_ms: int) -> bytes | None:
        deadline = self._clock.now_ms() + max(0, timeout_ms)
        while True:
            if self._queues[receiver] and self._queues[receiver][0].deliver_at_ms <= self._clock.now_ms():
                delivery = heapq.heappop(self._queues[receiver])
                return delivery.frame
            if timeout_ms <= 0:
                return None
            now = self._clock.now_ms()
            if now >= deadline:
                return None
            self._clock.sleep_ms(min(1, deadline - now))


class MockRadio(IRadio):
    def __init__(self, link: MockLink, label: str) -> None:
        self._link = link
        self._label = label

    def send(self, frame: bytes) -> None:
        self._link._send(self._label, frame)

    def recv(self, timeout_ms: int) -> bytes | None:
        return self._link._recv(self._label, timeout_ms)

    def close(self) -> None:
        return None


def create_mock_link(
    loss_rate: float = 0.0,
    latency_ms: int = 0,
    seed: int = 0,
    drop_pattern: List[bool] | None = None,
    clock: Clock | None = None,
    loss_rate_ab: float | None = None,
    loss_rate_ba: float | None = None,
    drop_pattern_ab: List[bool] | None = None,
    drop_pattern_ba: List[bool] | None = None,
) -> MockLink:
    return MockLink(
        loss_rate=loss_rate,
        latency_ms=latency_ms,
        seed=seed,
        drop_pattern=drop_pattern,
        clock=clock,
        loss_rate_ab=loss_rate_ab,
        loss_rate_ba=loss_rate_ba,
        drop_pattern_ab=drop_pattern_ab,
        drop_pattern_ba=drop_pattern_ba,
    )


