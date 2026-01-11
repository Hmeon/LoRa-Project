# Reproducibility

Each run must be reproducible from:
- **RunSpec** (run configuration)
- **Artifacts Manifest** (codec artifacts and normalization parameters)
- **Logs** (JSONL events for TX/RX)

## Required artifacts
- RunSpec file used for TX and RX
- Artifacts manifest (codec id/version, norm hash, payload schema hash)
- Logs for TX, RX, and controller

## Minimal checklist
- UART enabled and configured on both devices
- E22 modules configured with the same channel/address rules
- ADR-CODE profile selected and recorded
- Packet format matches `LEN|SEQ|PAYLOAD`
- AUX availability verified; ToA estimation configured if AUX is not available
- RunSpec and artifacts manifest stored alongside logs

## Notes
- TX and RX must verify the same artifacts manifest before a run.
- If any parameter changes, create a new run_id and new artifacts manifest entry.
