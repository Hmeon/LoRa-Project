import pytest

from loralink_mllc.protocol.framing import make_ack_packet
from loralink_mllc.protocol.packet import Packet


def test_make_ack_packet_ok() -> None:
    pkt = make_ack_packet(ack_seq=7, seq=9)
    assert pkt == Packet(payload=b"\x07", seq=9)


@pytest.mark.parametrize("ack_seq", [-1, 256])
def test_make_ack_packet_invalid_ack_seq(ack_seq: int) -> None:
    with pytest.raises(ValueError, match="ack_seq must be 0..255"):
        make_ack_packet(ack_seq=ack_seq, seq=0)


@pytest.mark.parametrize("seq", [-1, 256])
def test_make_ack_packet_invalid_seq(seq: int) -> None:
    with pytest.raises(ValueError, match="seq must be 0..255"):
        make_ack_packet(ack_seq=0, seq=seq)

