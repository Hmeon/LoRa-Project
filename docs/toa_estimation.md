# ToA Estimation (AUX-less)

When AUX is not available, ToA must be **estimated** from PHY parameters and payload length and used with a guard time for TX pacing.

## Inputs
- `sf`, `bw_hz`, `cr`
- `payload_bytes` (LEN)
- `crc_enabled`, `header_mode`, `ldro`, `preamble_symbols`

## Canonical LoRa formula
- `Tsym = 2^SF / BW`
- `Tpreamble = (Npreamble + 4.25) * Tsym`
- `payloadSymbNb = 8 + max( ceil( (8*PL - 4*SF + 28 + 16*CRC - 20*IH) / (4*(SF - 2*DE)) ) * (CR + 4), 0 )`
- `ToA = Tpreamble + payloadSymbNb * Tsym`

Where:
- `PL = payload_bytes`
- `CRC = 1` if enabled else `0`
- `IH = 1` if implicit header else `0`
- `DE = 1` if LDRO enabled else `0`
- `CR` index: 4/5->1, 4/6->2, 4/7->3, 4/8->4

## Usage rule
- Use `tx_wait_ms = toa_ms_est + guard_ms`.
- Treat ToA as an approximation and use it consistently for reporting and comparisons.
