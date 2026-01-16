# Runbook: UART Ops and Sensor Capture

This runbook defines the operational steps for field data collection and UART
link bring-up using the current LoRaLink-MLLC runtime. It avoids vendor-specific
drivers and uses JSONL/CSV sensor feeds.

## 0) Scope and prerequisites
- Two E22-900T22S (SX1262) modules, antennas connected.
- UART access on both hosts.
- Sensor producer that emits JSON lines or CSV logs.
- Confirm packet format is fixed: `LEN|SEQ|PAYLOAD`.
- Confirm max payload is 238 bytes (see `docs/radio_constraints_e22.md`).

## 1) Hardware checklist
Record the following before any run:
- Module IDs (TX/RX physical labels).
- UART ports and baud (TX and RX).
- Antenna type, gain, and orientation.
- Distance and environment notes (line of sight, obstacles).
- Power source and voltage stability.
Record the final UART settings in `configs/examples/uart_record.yaml`.

## 2) E22 configuration checklist (external to this repo)
The runtime does not configure the module. Set these externally and record them:
- Address and network ID (if used in your P2P mode).
- Channel or frequency selection.
- UART baud and parity.
- Air data rate and modulation profile.
- CRC and header mode.
- LDRO setting (explicit on/off/auto).

If these fields are not consistent across TX/RX, packets will fail silently.
Document the final settings in your run notes.

Record template (example):
```yaml
e22_config:
  addr: 0x0000
  netid: 0x00
  channel: 0x32
  uart_baud: 9600
  uart_parity: 8N1
  air_data_rate: 2.4k
  crc_on: false
  header_mode: explicit
  preamble: 8
  ldro: on
  tx_power_dbm: 22
  module_payload_length_bytes: 7
```

## 2.1 AUX-less timing assumption
This repo assumes AUX is not available. TX pacing must use ToA estimation:
- `tx_wait_ms = toa_ms_est + guard_ms`
- ToA estimation details: `docs/toa_estimation.md`

## 2.2 Waveshare SX1262 LoRa HAT interface limits
- The HAT exposes UART TX/RX, Busy, and Reset only; SPI and DIO1 are not available.
- Raspberry Pi can only access the AT UART interface; LibDriver register access is not usable.
- Air Speed presets 0..7 are firmware-fixed PHY bundles. Record the preset index and firmware
  version in `configs/examples/uart_record.yaml`.
- Air Speed preset values are documented in `docs/E22-900T22S_User_Manual_Deconstructed.md`
  (REG0 bits 2..0). Map to PHY using `docs/phy_profiles_adr_code.md`.
- Do not wait for DIO1 TX_DONE IRQ; use UART ACKs and ToA-based guards.

## 2.3 RSSI byte output (optional, recommended for field logs)
Some E22 firmwares can append a 1-byte RSSI value after each received UART message (REG3 bit 7).
If you enable this, you must run the runtime with `--uart-rssi-byte` or framing will desync.

Read current config:
```bash
python scripts/e22_tool.py read --port COM3 --rate 9600
```

Enable RSSI byte output (and ambient noise bit, optional) and persist it:
```bash
python scripts/e22_tool.py set --port COM3 --rate 9600 --save --rssi-byte true --ambient-noise true
```

Optional: query ambient noise and last-packet RSSI (dBm):
```bash
python scripts/e22_tool.py rssi --port COM3 --rate 9600
python scripts/e22_tool.py rssi --port COM3 --rate 9600 --json
```
Notes:
- Ambient noise reporting requires the `--ambient-noise true` bit in REG1 on some firmwares.
- `last_packet_dbm` reflects the most recent received packet (if any).

Runtime usage (RX example):
```bash
python -m loralink_mllc.cli rx \
  --runspec configs/examples/rx_raw.yaml \
  --manifest configs/examples/artifacts_sensor12_packed.json \
  --radio uart \
  --uart-port COM4 \
  --uart-baud 9600 \
  --uart-rssi-byte
```
When present, RSSI is logged as `rssi_dbm` (computed as `rssi_byte - 256`).

## 3) UART bring-up
1) Verify the OS sees each UART port.
2) Run RX first and keep it running.
3) Run TX and confirm `rx_ok` events appear on RX.

Example RX:
```bash
python -m loralink_mllc.cli rx \
  --runspec configs/examples/rx_raw.yaml \
  --manifest configs/examples/artifacts_sensor12_packed.json \
  --radio uart \
  --uart-port COM4 \
  --uart-baud 9600
```

Example TX:
```bash
python -m loralink_mllc.cli tx \
  --runspec configs/examples/tx_raw.yaml \
  --manifest configs/examples/artifacts_sensor12_packed.json \
  --radio uart \
  --uart-port COM3 \
  --uart-baud 9600
```

If ACKs are expected, verify `ack_received` in TX logs and `ack_sent` in RX logs.

## 4) Sensor capture pipeline
### 4.1 Input schema
The required 12D vector order is fixed:
`[lat, lon, alt, ax, ay, az, gx, gy, gz, roll, pitch, yaw]`

Units are fixed:
- gyro: deg/s
- roll, pitch, yaw: degrees

Use the JSONL/CSV schema defined in `docs/sensing_pipeline.md`.

### 4.2 Serial capture (optional)
If a microcontroller emits newline-delimited JSON:
```bash
python scripts/capture_serial_jsonl.py \
  --port COM5 \
  --baud 115200 \
  --out out/sensor.jsonl
```

### 4.3 TX with sensor feed
```bash
python -m loralink_mllc.cli tx \
  --runspec configs/examples/tx_raw.yaml \
  --manifest configs/examples/artifacts_sensor12_packed.json \
  --sampler jsonl \
  --sensor-path out/sensor.jsonl \
  --dataset-out out/dataset_raw.jsonl \
  --radio uart \
  --uart-port COM3 \
  --uart-baud 9600
```

The `dataset_raw.jsonl` file is required for BAM training and reconstruction
evaluation. Keep it alongside the run logs.

## 5) C50 search (Phase 0)
Goal: find a condition where PDR is approximately 50 percent.
1) Fix ADR-CODE and payload size.
2) Run a sweep and measure PDR.
3) Record the resulting C50 condition and environment notes.
4) Use the field runbook and record template:
   - `docs/phase0_c50_field.md`
   - `configs/examples/c50_record.yaml`

Mock reference (no hardware):
```bash
python -m loralink_mllc.cli phase0 \
  --sweep configs/examples/sweep.json \
  --out out/c50.json
```

## 6) Data collection at C50 (Phase 1)
1) Start RX.
2) Start TX with sensor feed and dataset logging.
3) Confirm logs contain `tx_sent`, `rx_ok`, and `ack_received`.
4) Stop after the target window count is reached.
5) Use the Phase 1 runbook and record template:
   - `docs/phase1_dataset_collection.md`
   - `configs/examples/phase1_record.yaml`

## 7) Post-run validation
- JSONL logs exist for TX and RX.
- `dataset_raw.jsonl` exists and has `window` length = `12 * W`.
- `run_id` matches across all files.
- `max_payload_bytes` is not exceeded.
Optional validator:
```bash
python scripts/validate_run.py \
  --log out/runtime/<run_id>_tx.jsonl \
  --log out/runtime/<run_id>_rx.jsonl \
  --dataset out/dataset_raw.jsonl \
  --out out/validate_<run_id>.json
```

## 8) Common failure modes
- No ACKs: mismatch in address/channel/baud or RX not running.
- rx_parse_fail spikes: UART stream is not clean `LEN|SEQ|PAYLOAD`.
- Missing fields: sensor feed does not include all 12 required values.
- Dimension mismatch: RunSpec `window.dims` not equal to 12.
- GPS fix missing: latitude/longitude stuck at 0 or noise dominated.

## 9) Minimal artifacts to archive
- RunSpec used for TX/RX.
- Artifacts manifest and bam_manifest.json (if BAM used).
- `dataset_raw.jsonl`.
- TX and RX JSONL logs.
- Environment notes (distance, obstacles, weather).
- Phase 3 record (`configs/examples/phase3_record.yaml`) and reports under `out/phase3/` (if Phase 3 run).
- Phase 4 energy record (`configs/examples/phase4_record.yaml`) and reports under `out/phase4/` (if Phase 4 run).

Optional packager:
```bash
python scripts/package_run.py \
  --log out/runtime/<run_id>_tx.jsonl \
  --log out/runtime/<run_id>_rx.jsonl \
  --dataset out/dataset_raw.jsonl \
  --out-dir out/archive \
  --zip
```
