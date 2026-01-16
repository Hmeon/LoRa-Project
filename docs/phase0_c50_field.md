# Phase 0 (Field): C50 Search Runbook

This guide defines how to find a field condition where PDR is approximately 50 percent.
It must be run in RAW mode with fixed adr_code and payload_bytes.

## Goal
Find a repeatable condition where `PDR ~= 0.50` using:
- RAW mode
- fixed `adr_code`
- fixed `payload_bytes`

If PDR is too high, increase distance, add obstacles, or increase payload_bytes.
If PDR is too low, reduce distance, reduce obstacles, or reduce payload_bytes.

## Prerequisites
- UART module configuration recorded (channel/address/baud/CRC/header/LDRO).
- UART settings file exists: `configs/examples/uart_record.yaml`.
- AUX is not used; ToA is estimated with guard time.
- TX/RX RunSpec files are ready (`configs/examples/tx_raw.yaml`, `configs/examples/rx_raw.yaml`).
- `max_windows` set to a sufficiently large count for stable PDR (edit RunSpec).
- C50 record template is available (`configs/examples/c50_record.yaml`).
 - If using the Waveshare SX1262 LoRa HAT, record the AT Air Speed preset index; SF/BW/CR
   are derived from the vendor table and not set directly.

## Procedure
1) Fix parameters:
   - adr_code (PHY profile)
   - payload_bytes
   - environment (distance, obstacles)
   - antenna gain

2) Start RX (UART):
```bash
python -m loralink_mllc.cli rx \
  --runspec configs/examples/rx_raw.yaml \
  --manifest configs/examples/artifacts.json \
  --radio uart \
  --uart-port COM4 \
  --uart-baud 9600
```

3) Start TX (UART, RAW):
```bash
python -m loralink_mllc.cli tx \
  --runspec configs/examples/tx_raw.yaml \
  --manifest configs/examples/artifacts.json \
  --sampler dummy \
  --radio uart \
  --uart-port COM3 \
  --uart-baud 9600
```

4) Compute PDR from logs:
```bash
python -m loralink_mllc.cli metrics \
  --log out/runtime/<run_id>_tx.jsonl \
  --log out/runtime/<run_id>_rx.jsonl \
  --out out/phase0/metrics_<run_id>.json
```

5) If PDR is outside the 0.45-0.55 band, adjust only one variable at a time:
   - distance (primary knob)
   - obstacles (secondary knob)
   - payload_bytes (only if distance/obstacles cannot be changed)
   - adr_code (only if required by link budget)

6) When PDR ~= 0.50, record the C50 condition in a copy of
   `configs/examples/c50_record.yaml`. Keep the filled file alongside logs.

## C50 record template
Use the template file: `configs/examples/c50_record.yaml`

Minimum required fields:
- run_id
- adr_code
- payload_bytes
- environment notes (distance, obstacles)
- antenna gain
- air data rate / PHY settings (SF/BW/CR)
- module settings (channel/address/baud/CRC/header/LDRO)
- RunSpec paths
If you add real device addresses, keep the filled record out of version control.

## Output
- `out/runtime/<run_id>_tx.jsonl`
- `out/runtime/<run_id>_rx.jsonl`
- `out/phase0/metrics_<run_id>.json`
- `configs/examples/c50_record.yaml` (or a copy filled with real values)
