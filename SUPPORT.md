# Support

This repository is a **research/field-experiment runtime**. Support is best-effort.

## Where to ask
- **Bug reports / reproducibility issues**: GitHub Issues
- **Questions / discussion**: GitHub Issues (use the "question" label if available)
- **Security vulnerabilities**: follow `SECURITY.md` (do not open a public issue)

## Before opening an issue
Please include enough context to make the report reproducible:
- Goal: what you were trying to do (Phase 0/1/2/3/4, mock vs UART)
- Environment: OS, Python version, install command used (`pip install -e .[...]`)
- Hardware (if UART): module model, UART ports/baud, firmware version, Air Speed preset, CRC/header/LDRO settings
- Artifacts: RunSpec used, artifacts manifest, and any filled record templates (redact private IDs)
- Logs: `out/runtime/<run_id>_tx.jsonl`, `out/runtime/<run_id>_rx.jsonl` (or a minimal excerpt)
- Exact command lines and the full error output

## Common quick checks (UART)
- TX/RX must match **address/channel/baud/air speed** and other settings recorded in `configs/examples/uart_record.yaml`.
- If E22 **RSSI byte output** (REG3 bit 7) is enabled, run TX/RX with `--uart-rssi-byte` or framing will desync.

## What not to post
- Real device addresses/IDs, credentials, private datasets, or any sensitive field logs.

