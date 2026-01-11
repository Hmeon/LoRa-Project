from loralink_mllc.runtime.scheduler import FakeClock, TxGate


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


