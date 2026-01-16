# Reproducibility

Each run must be reproducible from:
- **RunSpec** (run configuration)
- **Artifacts Manifest** (codec artifacts and normalization parameters)
- **Logs** (JSONL events for TX/RX)

## Required artifacts
- RunSpec file used for TX and RX
- Artifacts manifest (codec id/version, norm hash, payload schema hash)
- Logs for TX and RX
- BAM manifest (`bam_manifest.json`) and `layer_*.npz` when `codec.id = bam`
- Dataset raw windows (`dataset_raw.jsonl`) when training BAM
- UART settings record (`configs/examples/uart_record.yaml`)
- C50 record (`configs/examples/c50_record.yaml`)
- Phase 1 record (`configs/examples/phase1_record.yaml`)
- Phase 2 record (`configs/examples/phase2_record.yaml`)
- Phase 3 record (`configs/examples/phase3_record.yaml`)
- Phase 4 energy record (`configs/examples/phase4_record.yaml`)

## Minimal checklist
- UART enabled and configured on both devices
- E22 modules configured with the same channel/address rules
- ADR-CODE profile selected and recorded
- Packet format matches `LEN|SEQ|PAYLOAD`
- AUX availability verified; ToA estimation configured if AUX is not available
- CRC/header/LDRO settings recorded for both ends
- RunSpec and artifacts manifest stored alongside logs

## Notes
- TX and RX must verify the same artifacts manifest before a run.
- If any parameter changes, create a new run_id and new artifacts manifest entry.
- Sensor data format and order are defined in `docs/sensing_pipeline.md`.
  Units are fixed to deg/deg/s and recorded in dataset outputs.

## Helper scripts (optional)
- Validate logs + artifacts + dataset join:
  `python scripts/validate_run.py --log out/runtime/<run_id>_tx.jsonl --log out/runtime/<run_id>_rx.jsonl --dataset out/dataset_raw.jsonl`
- Package a run for archiving (hashes + metrics + optional zip):
  `python scripts/package_run.py --log out/runtime/<run_id>_tx.jsonl --log out/runtime/<run_id>_rx.jsonl --dataset out/dataset_raw.jsonl --out-dir out/archive --zip`
