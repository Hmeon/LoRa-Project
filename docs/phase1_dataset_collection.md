# Phase 1 (Field): C50 Dataset Collection

This runbook defines the Phase 1 data capture at a fixed C50 condition.
It assumes Phase 0 has produced a C50 record and UART settings are fixed.

## Goal
- Collect `dataset_raw.jsonl` on TX with one window per packet.
- Log TX and RX JSONL events with consistent `run_id`.
- Record the run in `configs/examples/phase1_record.yaml`.

## Prerequisites
- C50 condition recorded: `configs/examples/c50_record.yaml`
- UART settings recorded: `configs/examples/uart_record.yaml`
- RunSpec files pinned for RAW or LATENT mode.
- Sensor feed available (JSONL or CSV).
- AUX not used; ToA is estimated with guard time.
 - If using the Waveshare SX1262 LoRa HAT, record the AT Air Speed preset index; SF/BW/CR
   are derived from the vendor table and not set directly.

## Procedure
1) Start RX (UART):
```bash
python -m loralink_mllc.cli rx \
  --runspec configs/examples/rx_raw.yaml \
  --manifest configs/examples/artifacts_sensor12_packed.json \
  --radio uart \
  --uart-port COM4 \
  --uart-baud 9600
```

2) Start TX with dataset logging:
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

3) Stop after the target window count is reached.

4) Compute metrics from logs:
```bash
python -m loralink_mllc.cli metrics \
  --log out/runtime/<run_id>_tx.jsonl \
  --log out/runtime/<run_id>_rx.jsonl \
  --out out/phase1/metrics_<run_id>.json
```

5) Fill `configs/examples/phase1_record.yaml` with the run details.

## Output checklist
- `out/dataset_raw.jsonl`
- `out/runtime/<run_id>_tx.jsonl`
- `out/runtime/<run_id>_rx.jsonl`
- `out/phase1/metrics_<run_id>.json`
- Filled `configs/examples/phase1_record.yaml`

## Notes
- Keep `run_id` consistent across TX, RX, dataset, and metrics.
- If ACKs are enabled, verify `ack_received` on TX and `ack_sent` on RX.
- If sensor values are in radians or g, convert to the fixed units before capture.
