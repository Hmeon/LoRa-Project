# ADR-CODE PHY Profiles

ADR-CODE profiles provide a stable reference for LoRa PHY settings when AUX timing is unavailable and ToA must be estimated.

## Reference table
| Air Speed preset | ADR-CODE | Air data rate | SF/BW/CR | Symbol Time (Tsym) | Real Data Rate |
|---:|---:|---:|---|---:|---:|
| 0 | 000 | 0.3 kbps | SF12 / 125 / 4/5 | 32.77 ms | 293 bps |
| 1 | 001 | 1.2 kbps | SF10 / 250 / 4/8 | 4.10 ms | 1.2 kbps |
| 2 | 010 | 2.4 kbps | SF10 / 500 / 4/8 | 2.05 ms | 2.4 kbps |
| 3 | 011 | 4.8 kbps | SF9 / 500 / 4/7 | 1.23 ms | 5.0 kbps |
| 4 | 100 | 9.6 kbps | SF5 / 125 / 4/8 | 0.26 ms | 9.7 kbps |
| 5 | 101 | 19.2 kbps | SF5 / 250 / 4/8 | 0.13 ms | 19.5 kbps |
| 6 | 110 | 38.4 kbps | SF5 / 500 / 4/8 | 0.06 ms | 39 kbps |
| 7 | 111 | 62.5 kbps | SF5 / 500 / 4/5 | 0.06 ms | 62.5 kbps |

## Required recorded fields
Each profile entry must record:
- `adr_code`, `sf`, `bw_hz`, `cr`
- `tsym_ms`, `real_datarate_bps`
- `crc_enabled`, `header_mode`, `preamble_symbols`, `ldro`

The above fields must be pinned in run artifacts before ToA estimation is used for scheduling.

Notes:
- Use Hz for `bw_hz` in machine configs (e.g., 125000) even if the table shows kHz.
- `header_mode` (explicit/implicit) maps to RunSpec `explicit_header` (bool).
- `preamble_symbols` maps to RunSpec `preamble`.
- `crc_enabled` maps to RunSpec `crc_on`.
- On Waveshare SX1262 LoRa HAT, SF/BW/CR are not directly configurable; use the AT Air Speed
  preset table to derive these values and record the preset index in the UART record.
- Air Speed preset values map to REG0 bits 2..0 in `docs/E22-900T22S_User_Manual_Deconstructed.md`.

Current field settings (ADR 000-010):
- `crc_enabled`: false
- `header_mode`: explicit
- `preamble_symbols`: 8
- `ldro`: auto (enable when `Tsym >= 16.38 ms`; record per profile if module firmware differs)
