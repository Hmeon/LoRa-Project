# Protocol Packet Format

## Application-level frame
`LEN (1B) | SEQ (1B) | PAYLOAD (LEN bytes)`

**Field rules:**
- `LEN` is the payload length in bytes (0..255 by spec).
- `SEQ` is 1 byte and wraps 0..255. Uniqueness is enforced by `run_id + seq`.
- `PAYLOAD` is raw bytes (either RAW window packing or LATENT payload).

**E22 UART constraint (P2P mode):** TX packet length is limited to 240 bytes. With a 2-byte app header, `LEN <= 238` and `(2 + LEN) <= 240`.

## ACK frame
- ACK payload is **exactly 1 byte**: `ACK_SEQ` (echoed uplink `SEQ`).
- ACK frame uses the same outer format with `LEN=1`.
- ACK frame `SEQ` is independent; metrics must key on `ACK_SEQ`.

## Mode selection
- No mode byte is added to the packet.
- Mode (RAW/LATENT) is run-level and carried in RunSpec/logs, not in the packet.

## Notes
- This format is the application-level payload over E22 UART P2P, not LoRaWAN MAC payload framing.
