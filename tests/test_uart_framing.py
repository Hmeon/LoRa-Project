from loralink_mllc.radio.uart_framing import UartFrameParser


def test_uart_frame_parser_no_rssi() -> None:
    parser = UartFrameParser(max_payload_bytes=238, rssi_byte_enabled=False)
    frame = bytes([3, 7]) + b"abc"
    parser.feed(frame)
    parsed = parser.pop()
    assert parsed is not None
    assert parsed.frame == frame
    assert parsed.rssi_dbm is None
    assert parser.pop() is None


def test_uart_frame_parser_with_rssi() -> None:
    parser = UartFrameParser(max_payload_bytes=238, rssi_byte_enabled=True)
    frame = bytes([2, 1]) + b"hi"
    rssi_byte = 156  # -100 dBm via (byte - 256)
    parser.feed(frame + bytes([rssi_byte]))
    parsed = parser.pop()
    assert parsed is not None
    assert parsed.frame == frame
    assert parsed.rssi_dbm == -100


def test_uart_frame_parser_resync_on_invalid_len() -> None:
    parser = UartFrameParser(max_payload_bytes=10, rssi_byte_enabled=False)
    garbage = bytes([255, 254, 253])
    frame = bytes([1, 9]) + b"x"
    parser.feed(garbage + frame)
    parsed = parser.pop()
    assert parsed is not None
    assert parsed.frame == frame


def test_uart_frame_parser_rssi_mode_consumes_trailing_byte() -> None:
    parser = UartFrameParser(max_payload_bytes=238, rssi_byte_enabled=True)
    f1 = bytes([1, 1]) + b"a"
    f2 = bytes([1, 2]) + b"b"
    parser.feed(f1 + bytes([200]) + f2 + bytes([180]))
    p1 = parser.pop()
    p2 = parser.pop()
    assert p1 is not None and p2 is not None
    assert p1.frame == f1
    assert p2.frame == f2
    assert p1.rssi_dbm == -56
    assert p2.rssi_dbm == -76

