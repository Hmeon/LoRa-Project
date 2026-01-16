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
    bw = phy.bw_hz
    if bw <= 0:
        raise ValueError("bw_hz must be > 0")
    cr_idx = _cr_index(phy.cr)
    de = 1 if (sf >= 11 and bw == 125000) else 0
    ih = 0 if phy.explicit_header else 1
    crc = 1 if phy.crc_on else 0

    tsym = (2 ** sf) / bw
    tpreamble = (phy.preamble + 4.25) * tsym
    payload_symb_nb = 8 + max(
        math.ceil(
            (
                8 * payload_len_bytes
                - 4 * sf
                + 28
                + 16 * crc
                - 20 * ih
            )
            / (4 * (sf - 2 * de))
        )
        * (cr_idx + 4),
        0,
    )
    toa_s = tpreamble + payload_symb_nb * tsym
    return toa_s * 1000.0


