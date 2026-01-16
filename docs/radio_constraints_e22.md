# E22 UART Radio Constraints (E22-xxxT22S)

## UART packet length limit
- E22 P2P UART TX packet length is limited to **240 bytes** (module constraint).
- Application header is 2 bytes (`LEN` + `SEQ`), so the maximum payload is **238 bytes**.
- Requirement: `(2 + LEN) <= 240` which implies `LEN <= 238`.

This limit applies to E22 P2P UART usage.

## AUX pin and timing
- The E22 module supports an AUX pin, but the HAT/board may not expose it; verify wiring.
- If AUX is not available, rely on ToA estimation plus a guard time for TX pacing.

## Waveshare SX1262 LoRa HAT interface limits
- The HAT uses an onboard MCU (ESP32-C3) with the SX1262 connected over internal SPI only.
  The external header exposes UART TX/RX, Busy, and Reset, but not SPI or DIO1.
- Raspberry Pi access is limited to the AT UART interface; register-level control
  (LibDriver-style examples) cannot be used on this hardware.
- The AT firmware exposes Air Speed presets 0..7 that bundle SF/BW/CR/preamble in a fixed table.
  Record the preset index and firmware version; map to PHY values using the vendor table.
- Air Speed preset values (0..7) and air data rates are listed in
  `docs/E22-900T22S_User_Manual_Deconstructed.md` (REG0 bits 2..0).
- TX_DONE IRQ (DIO1) is not available; do not wait for DIO1 interrupts. Use UART ACKs and
  ToA-based guards for pacing instead.
- Direct SF/BW/CR control is not available on this HAT.

## Module-layer header
- E22 UART P2P frames include module-managed fields (address/channel) that are not part of the application payload.
- Application-level framing is still `LEN | SEQ | PAYLOAD`.

## External configuration record (required)
Because this repo does not configure the module, record the final settings:
- address, netid, channel
- UART baud and parity
- air data rate / profile
- CRC on/off, header mode, preamble
- LDRO on/off/auto
Use `configs/examples/uart_record.yaml` as the record template.

## UART driver assumptions (repo runtime)
- `loralink_mllc/radio/uart_e22.py` reads and writes raw application frames only.
- Default assumption: the UART stream delivers `LEN | SEQ | PAYLOAD` without extra bytes.
- If **RSSI byte output** is enabled on the module (REG3 bit 7), the module appends **1 extra byte**
  after every received message. In that case run TX/RX with `--uart-rssi-byte` so framing stays aligned.
  The runtime converts the RSSI byte to dBm using `rssi_dbm = rssi_byte - 256` and logs it when present.
- Module configuration (address/channel/PHY) must be handled externally.
