import pytest

from loralink_mllc.runtime.scheduler import FakeClock, RealClock, TxGate


def test_txgate_toa_guard_gating() -> None:
    clock = FakeClock()
    gate = TxGate(clock=clock, guard_ms=100, ack_timeout_ms=1000, max_retries=0)
    assert gate.can_send()
    gate.record_send(seq=1, toa_ms_est=200)
    assert not gate.can_send()
    clock.sleep_ms(50)
    gate.mark_acked(1)
    assert not gate.can_send()
    clock.sleep_ms(250)
    assert gate.can_send()


def test_txgate_expired_failure() -> None:
    clock = FakeClock()
    gate = TxGate(clock=clock, guard_ms=0, ack_timeout_ms=10, max_retries=0)
    gate.record_send(seq=3, toa_ms_est=1)
    clock.sleep_ms(11)
    failures = list(gate.expired_failures())
    assert len(failures) == 1
    assert failures[0].seq == 3


def test_txgate_expired_failures_skips_before_retries_exceeded() -> None:
    clock = FakeClock()
    gate = TxGate(clock=clock, guard_ms=0, ack_timeout_ms=10, max_retries=2)
    gate.record_send(seq=1, toa_ms_est=1)
    clock.sleep_ms(11)
    assert list(gate.expired_failures()) == []


def test_real_clock_smoke() -> None:
    clock = RealClock()
    t0 = clock.now_ms()
    clock.sleep_ms(0)
    t1 = clock.now_ms()
    assert t1 >= t0


def test_txgate_inflight_limit_and_retry_tracking() -> None:
    clock = FakeClock()
    gate = TxGate(clock=clock, guard_ms=0, ack_timeout_ms=10, max_retries=1, max_inflight=1)
    assert gate.can_send()
    gate.record_send(seq=1, toa_ms_est=1)
    assert not gate.can_send()

    # Retry same seq increments retries_total.
    clock.sleep_ms(11)
    assert list(gate.expired_sequences()) == [1]
    gate.record_send(seq=1, toa_ms_est=2)
    m = gate.metrics()
    assert m["retries_total"] == 1

    # Mark unknown ack does nothing.
    assert gate.mark_acked(99) is None

    # Mark acked seq clears inflight.
    inflight = gate.mark_acked(1)
    assert inflight is not None
    clock.sleep_ms(2)
    assert gate.can_send()


def test_txgate_record_send_rejects_nonpositive_timeout_override() -> None:
    clock = FakeClock()
    gate = TxGate(clock=clock, guard_ms=0, ack_timeout_ms=10, max_retries=0)
    with pytest.raises(ValueError, match="ack_timeout_ms must be > 0"):
        gate.record_send(seq=1, toa_ms_est=1, ack_timeout_ms=0)


