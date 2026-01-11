# ADR-CODE PHY Profiles

ADR-CODE profiles provide a stable reference for LoRa PHY settings when AUX timing is unavailable and ToA must be estimated.

## Reference table
| ADR-CODE | Manual Speed | SF/BW/CR | Symbol Time (Tsym) | Real Data Rate |
|---:|---:|---|---:|---:|
| 000 | 0.3 kbps | SF12 / 125 / 4/5 | 32.77 ms | 293 bps |
| 001 | 1.2 kbps | SF10 / 250 / 4/8 | 4.10 ms | 1.2 kbps |
| 010 | 2.4 kbps | SF10 / 500 / 4/8 | 2.05 ms | 2.4 kbps |
| 011 | 4.8 kbps | SF9 / 500 / 4/7 | 1.23 ms | 5.0 kbps |
| 100 | 9.6 kbps | SF5 / 125 / 4/8 | 0.26 ms | 9.7 kbps |
| 101 | 19.2 kbps | SF5 / 250 / 4/8 | 0.13 ms | 19.5 kbps |
| 110 | 38.4 kbps | SF5 / 500 / 4/8 | 0.06 ms | 39 kbps |
| 111 | 62.5 kbps | SF5 / 500 / 4/5 | 0.06 ms | 62.5 kbps |

## Required recorded fields
Each profile entry must record:
- `adr_code`, `sf`, `bw_khz`, `cr`
- `tsym_ms`, `real_datarate_bps`
- `crc_enabled`, `header_mode`, `preamble_symbols`, `ldro`

The above fields must be pinned in run artifacts before ToA estimation is used for scheduling.
