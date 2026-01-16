from loralink_mllc.config.runspec import PhySpec
from loralink_mllc.runtime.toa import estimate_toa_ms


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


