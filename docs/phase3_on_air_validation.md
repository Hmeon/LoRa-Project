# Phase 3 (Field): On-air Validation at C50

This runbook defines how to run Phase 3 at a fixed C50 condition to measure:
- link metrics vs payload size (PDR/ETX, RTT, RSSI when available)
- reconstruction error vs payload size (MAE/MSE) using the Phase 3 helper scripts

## Goal
At a fixed C50 condition, compare:
- baseline (RAW)
- one or more compressed variants (LATENT via BAM packing/latent_dim)

## Prerequisites
- C50 condition recorded: `configs/examples/c50_record.yaml`
- UART settings recorded: `configs/examples/uart_record.yaml`
- Phase 2 artifacts ready: `layer_*.npz`, `norm.json`, `bam_manifest.json`, `artifacts.json`
- RunSpecs pinned (baseline and each variant) with the same window settings (`dims/W/stride/sample_hz`)

If RSSI-byte output is enabled on the module (REG3 bit 7), run with `--uart-rssi-byte`
and enable it via `scripts/e22_tool.py` (see `docs/runbook_uart_sensing.md`).

## Procedure (repeat per condition)
1) Start RX (UART):
```bash
python -m loralink_mllc.cli rx \
  --runspec <rx_runspec.yaml> \
  --manifest <artifacts.json> \
  --radio uart \
  --uart-port COM4 \
  --uart-baud 9600
```

2) Start TX (UART) with dataset logging enabled for analysis:
```bash
python -m loralink_mllc.cli tx \
  --runspec <tx_runspec.yaml> \
  --manifest <artifacts.json> \
  --sampler jsonl \
  --sensor-path out/sensor.jsonl \
  --dataset-out out/dataset_<run_id>.jsonl \
  --radio uart \
  --uart-port COM3 \
  --uart-baud 9600
```

3) Stop after the target window count is reached.

## Post-run analysis
1) Link metrics (from logs only):
```bash
python -m loralink_mllc.cli metrics \
  --log out/runtime/<run_id>_tx.jsonl \
  --log out/runtime/<run_id>_rx.jsonl \
  --out out/phase3/metrics_<run_id>.json
```

2) Link + reconstruction report (joins ACKed `window_id` to the dataset):
```bash
python scripts/phase3_report.py \
  --log out/runtime/<run_id>_tx.jsonl \
  --log out/runtime/<run_id>_rx.jsonl \
  --dataset out/dataset_<run_id>.jsonl \
  --out out/phase3/report_<run_id>.json
```

Optional validator (recommended before reporting):
```bash
python scripts/validate_run.py \
  --log out/runtime/<run_id>_tx.jsonl \
  --log out/runtime/<run_id>_rx.jsonl \
  --dataset out/dataset_<run_id>.jsonl \
  --out out/phase3/validate_<run_id>.json
```

3) Plotting (optional)
If you aggregate multiple runs into one report (multiple `run_id` keys), you can plot:
```bash
python -m pip install -e .[viz]
python scripts/plot_phase_results.py \
  --phase3 out/phase3/report_all.json \
  --out-dir out/plots \
  --plots
```

Notes:
- `scripts/phase3_report.py` computes reconstruction error as a codec roundtrip on the
  delivered (ACKed) windows. Packet loss affects *which* windows are included.
- TX logs include `window_id` on `tx_sent`/`ack_received` to make this join reproducible.

## Record template
Use `configs/examples/phase3_record.yaml` to log:
- baseline and variant run_ids
- artifact paths
- report paths under `out/phase3/`
