# Phase 4 (Field): Energy / Power Evaluation

This runbook defines the Phase 4 workflow: measure power consumption for baseline vs
compressed runs under the same C50 conditions, then compute energy per delivered window.

## Goal
For each condition (baseline + variants), record:
- average power over a fixed duration, or
- total energy over a fixed duration

Then compute:
- energy per delivered window
- energy per TX attempt (optional)

## Prerequisites
- Phase 3 runs completed (logs + metrics reports exist)
- A repeatable measurement setup (equipment + sampling method recorded)

## Procedure
1) For each `run_id`, measure average power over the same duration.
2) Record the measurement in a copy of `configs/examples/phase4_record.yaml`.

## Post-run analysis
Use the helper script to merge power measurements with a metrics report:
```bash
python scripts/phase4_energy_report.py \
  --metrics out/phase3/report_<run_id>.json \
  --energy configs/examples/phase4_record.yaml \
  --out out/phase4/energy_report.json
```

Notes:
- This script does not perform power sampling; it only computes derived values from
  your recorded `avg_power_w` and `duration_s`.
- Delivered windows use `rx_ok_count` when present, otherwise `acked_count` as a proxy.

## Plotting (optional)
If you have a Phase 3 aggregated report (multiple `run_id` keys), you can plot energy too:
```bash
python -m pip install -e .[viz]
python scripts/plot_phase_results.py \
  --phase3 out/phase3/report_all.json \
  --phase4 out/phase4/energy_report.json \
  --out-dir out/plots \
  --plots
```
