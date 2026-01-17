from loralink_mllc.radio.mock import create_mock_link
from loralink_mllc.runtime.scheduler import FakeClock


def test_mock_link_timeout_path_and_close() -> None:
    clock = FakeClock()
    link = create_mock_link(clock=clock, latency_ms=0)
    assert link.a.recv(timeout_ms=5) is None
    assert link.a.close() is None

