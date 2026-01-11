# E22 UART Radio Constraints (E22-xxxT22S)

## UART packet length limit
- E22 P2P UART TX packet length is limited to **240 bytes** (module constraint).
- Application header is 2 bytes (`LEN` + `SEQ`), so the maximum payload is **238 bytes**.
- Requirement: `(2 + LEN) <= 240` which implies `LEN <= 238`.

This limit applies to E22 P2P UART usage, not LoRaWAN MAC payload limits.

## AUX pin and timing
- The E22 module supports an AUX pin, but the HAT/board may not expose it; verify wiring.
- If AUX is not available, rely on ToA estimation plus a guard time for TX pacing.

## Module-layer header
- E22 UART P2P frames include module-managed fields (address/channel) that are not part of the application payload.
- Application-level framing is still `LEN | SEQ | PAYLOAD`.
