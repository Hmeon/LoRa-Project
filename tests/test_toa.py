import math

import pytest

from loralink_mllc.config.runspec import PhySpec
from loralink_mllc.runtime.toa import estimate_ack_timeout_ms, estimate_toa_ms


def test_toa_monotonic_payload() -> None:
    phy = PhySpec(
        sf=7,
        bw_hz=125000,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
    )
    small = estimate_toa_ms(phy, 5)
    large = estimate_toa_ms(phy, 20)
    assert large > small


def test_toa_monotonic_sf() -> None:
    phy_low = PhySpec(
        sf=7,
        bw_hz=125000,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
    )
    phy_high = PhySpec(
        sf=10,
        bw_hz=125000,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
    )
    assert estimate_toa_ms(phy_high, 10) > estimate_toa_ms(phy_low, 10)


def test_toa_monotonic_bw() -> None:
    phy_narrow = PhySpec(
        sf=7,
        bw_hz=125000,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
    )
    phy_wide = PhySpec(
        sf=7,
        bw_hz=500000,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
    )
    assert estimate_toa_ms(phy_wide, 10) < estimate_toa_ms(phy_narrow, 10)


def test_toa_invalid_inputs_raise() -> None:
    phy = PhySpec(
        sf=7,
        bw_hz=125000,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
    )
    with pytest.raises(ValueError, match="payload_len_bytes must be 0..255"):
        estimate_toa_ms(phy, -1)
    with pytest.raises(ValueError, match="payload_len_bytes must be 0..255"):
        estimate_toa_ms(phy, 256)

    bad_bw = PhySpec(
        sf=7,
        bw_hz=0,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
    )
    with pytest.raises(ValueError, match="bw_hz must be > 0"):
        estimate_toa_ms(bad_bw, 0)

    bad_cr = PhySpec(
        sf=7,
        bw_hz=125000,
        cr=9,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
    )
    with pytest.raises(ValueError, match="cr must be 1..4"):
        estimate_toa_ms(bad_cr, 0)

    # Also allow CR as 1..4 index (internal representation).
    phy_idx = PhySpec(
        sf=7,
        bw_hz=125000,
        cr=1,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
    )
    assert estimate_toa_ms(phy_idx, 0) > 0


def test_toa_sf5_sf6_formula_branch() -> None:
    phy = PhySpec(
        sf=5,
        bw_hz=125000,
        cr=5,
        preamble=8,
        crc_on=False,
        explicit_header=False,
        tx_power_dbm=14,
    )
    assert estimate_toa_ms(phy, 0) == pytest.approx(5.696, rel=1e-3)


def test_toa_ldro_auto_and_override() -> None:
    phy_auto_on = PhySpec(
        sf=12,
        bw_hz=250000,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
        ldro=None,
    )
    phy_forced_on = PhySpec(
        sf=12,
        bw_hz=250000,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
        ldro=True,
    )
    phy_forced_off = PhySpec(
        sf=12,
        bw_hz=250000,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
        ldro=False,
    )
    toa_auto = estimate_toa_ms(phy_auto_on, 100)
    toa_on = estimate_toa_ms(phy_forced_on, 100)
    toa_off = estimate_toa_ms(phy_forced_off, 100)
    assert toa_auto == toa_on
    assert toa_on > toa_off

    phy_auto_off = PhySpec(
        sf=10,
        bw_hz=250000,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
        ldro=None,
    )
    phy_forced_on2 = PhySpec(
        sf=10,
        bw_hz=250000,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
        ldro=True,
    )
    phy_forced_off2 = PhySpec(
        sf=10,
        bw_hz=250000,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
        ldro=False,
    )
    toa_auto2 = estimate_toa_ms(phy_auto_off, 100)
    toa_on2 = estimate_toa_ms(phy_forced_on2, 100)
    toa_off2 = estimate_toa_ms(phy_forced_off2, 100)
    assert toa_auto2 == toa_off2
    assert toa_on2 > toa_off2


def test_toa_rejects_sf_out_of_range() -> None:
    phy = PhySpec(
        sf=4,
        bw_hz=125000,
        cr=5,
        preamble=8,
        crc_on=False,
        explicit_header=True,
        tx_power_dbm=14,
    )
    with pytest.raises(ValueError, match="sf must be 5..12"):
        estimate_toa_ms(phy, 0)


def test_estimate_ack_timeout_ms() -> None:
    phy = PhySpec(
        sf=7,
        bw_hz=125000,
        cr=5,
        preamble=8,
        crc_on=True,
        explicit_header=True,
        tx_power_dbm=14,
    )
    data_toa = estimate_toa_ms(phy, 10)
    ack_toa = estimate_toa_ms(phy, 3)
    assert estimate_ack_timeout_ms(phy, data_frame_bytes=10, margin_ms=40) == int(
        math.ceil(data_toa + ack_toa + 40)
    )
    with pytest.raises(ValueError, match="margin_ms must be"):
        estimate_ack_timeout_ms(phy, data_frame_bytes=10, margin_ms=-1)


