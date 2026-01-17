from __future__ import annotations

import math

from loralink_mllc.config.runspec import PhySpec


def _cr_index(cr: int) -> int:
    if cr in (1, 2, 3, 4):
        return cr
    if 5 <= cr <= 8:
        return cr - 4
    raise ValueError("cr must be 1..4 (index) or 5..8 (denominator)")


def estimate_toa_ms(phy: PhySpec, payload_len_bytes: int) -> float:
    if payload_len_bytes < 0 or payload_len_bytes > 255:
        raise ValueError("payload_len_bytes must be 0..255")
    sf = phy.sf
    if sf < 5 or sf > 12:
        raise ValueError("sf must be 5..12 for LoRa mode")
    bw = phy.bw_hz
    if bw <= 0:
        raise ValueError("bw_hz must be > 0")
    cr_idx = _cr_index(phy.cr)

    tsym = (2 ** sf) / bw
    crc_bits = 16 if phy.crc_on else 0
    header_symbols = 20 if phy.explicit_header else 0

    if sf in (5, 6):
        de = 0
        preamble_extra = 6.25
        numerator = 8 * payload_len_bytes + crc_bits - 4 * sf + header_symbols
        denom = 4 * sf
    else:
        if phy.ldro is None:
            de = 1 if tsym >= 0.01638 else 0
        else:
            de = 1 if phy.ldro else 0
        preamble_extra = 4.25
        numerator = 8 * payload_len_bytes + crc_bits - 4 * sf + 8 + header_symbols
        denom = 4 * (sf - 2 * de)

    payload_symbols = 8 + math.ceil(max(numerator, 0) / denom) * (cr_idx + 4)
    total_symbols = phy.preamble + preamble_extra + payload_symbols
    toa_s = total_symbols * tsym
    return toa_s * 1000.0


def estimate_ack_timeout_ms(
    phy: PhySpec,
    data_frame_bytes: int,
    *,
    ack_frame_bytes: int = 3,
    margin_ms: int = 40,
) -> int:
    """
    Conservative ACK timeout estimate for UART-transparent LoRa:
    DATA ToA + ACK ToA + margin.
    """
    if margin_ms < 0:
        raise ValueError("margin_ms must be >= 0")
    data_toa_ms = estimate_toa_ms(phy, data_frame_bytes)
    ack_toa_ms = estimate_toa_ms(phy, ack_frame_bytes)
    return int(math.ceil(data_toa_ms + ack_toa_ms + margin_ms))


