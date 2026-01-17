# ToA Estimation (AUX-less)

When AUX is not available, ToA must be **estimated** from PHY parameters and payload length and used with a guard time for TX pacing. Do not rely on TX-done GPIOs.

## Inputs
- `sf`, `bw_hz`, `cr`, `preamble`
- `payload_bytes` (LEN) and `frame_bytes = 2 + payload_bytes` for this project’s `LEN|SEQ|PAYLOAD` framing
- `crc_on`, `explicit_header`, `ldro`

Mapping notes:
- `crc_on` corresponds to `Nbit_CRC` (16 if enabled else 0).
- `explicit_header` corresponds to `Nsym_header` (20 if explicit else 0).
- `preamble` maps to `Npreamble`.

Hardware note (Waveshare SX1262 LoRa HAT):
- Only AT UART is available; SF/BW/CR are selected indirectly via Air Speed presets (0..7).
  Map the preset index to PHY values using the vendor table and record the preset in run artifacts.
- DIO1 TX_DONE IRQ is not exposed; rely on UART ACKs and ToA estimation for pacing.

## Canonical LoRa formula
- `Tsym = 2^SF / BW`

SX1262 datasheet gives separate symbol-count equations for **SF5/SF6** vs **SF7..SF12**.

### SF5 / SF6
- `payloadSymbNb = 8 + ceil( max(8*PL + Nbit_CRC - 4*SF + Nsym_header, 0) / (4*SF) ) * (CR + 4)`
- `ToA = (Npreamble + 6.25 + payloadSymbNb) * Tsym`

### SF7..SF12 (no LDRO)
- `payloadSymbNb = 8 + ceil( max(8*PL + Nbit_CRC - 4*SF + 8 + Nsym_header, 0) / (4*SF) ) * (CR + 4)`
- `ToA = (Npreamble + 4.25 + payloadSymbNb) * Tsym`

### SF7..SF12 (LDRO enabled)
- Same as above, but denominator uses `4*(SF-2)` instead of `4*SF`.

Where:
- `PL = frame_bytes` (bytes on air for your UART message)
- `Nbit_CRC = 16` if CRC enabled else `0`
- `Nsym_header = 20` if explicit header else `0`
- `DE = 1` if LDRO enabled else `0` (only impacts SF7..SF12 equation)
- `CR` index: 4/5->1, 4/6->2, 4/7->3, 4/8->4

## Usage rule
- Use `tx_wait_ms = toa_ms_est + guard_ms`.
- Set `ack_timeout_ms` conservatively (DATA ToA + ACK ToA + margin) to avoid premature retries; `tx.ack_timeout_ms: auto` lets the runtime estimate it per frame.
- Treat ToA as an approximation and use it consistently for reporting and comparisons.

Implementation note:
- `loralink_mllc.runtime.toa.estimate_toa_ms()` follows SX1262 datasheet guidance:
  - SF5/SF6 use the SF5/SF6-specific equation.
  - LDRO (`DE`) defaults to auto-enable when `Tsym >= 16.38 ms`, but can be forced via RunSpec `phy.ldro`.
