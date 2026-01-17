# Patch Notes

This document summarizes the cumulative changes applied to the current LoRaLink-MLLC
codebase. It is not a changelog for ChirpChirp-main.

## Scope
- Target repo: Project-LoRa (current project).
- Reference repo: ChirpChirp-main is the predecessor project; this repo aims to complete
  and prepare it for deployment (pipeline TBD).
- Status: scaffold matured into a runnable mock + UART-minimal runtime with BAM inference.

## Latest update
- Added a binary RAW on-air payload baseline: `sensor12_packed` (30 bytes/step; gps float32 + IMU/rpy int16 fixed-point) and updated the RAW RunSpecs/docs to use `configs/examples/artifacts_sensor12_packed.json` (no JSON on-air).
- Removed MAC/network-layer scope/TODO references; the project targets E22 AT UART P2P only.
- Added timestamped sensor sampling support (`sample_with_ts`) so `dataset_raw.jsonl` uses sensor `ts_ms` (and uses last-sample time for `W>1`), and extended TX/RX logs + metrics with latency/host-cost fields (`codec_encode_ms`, `age_ms`, `queue_ms`, `e2e_ms`, `frame_bytes`).
- Added optional BAM inference recurrent refinement (`encode_cycles`, `decode_cycles`) with a delta safety check (`delta < 0.5`) when enabled.
- Aligned the BAM transmission function with the bounded regime (cubic + clip to `[-1, 1]`) and treated `delta=0` as linear/no-op.
- Extended the Phase 2 trainer with streaming shuffle, early stopping, auto-scale for int8/int16 packing, and a `train_report.json` summary.
- Added `scripts/phase2_sweep_bam.py` to sweep BAM variants and compare to mean/PCA baselines with a Pareto frontier report.
- Fixed Phase 2 trainer default `--scale` behavior: `int8` now defaults to `127` (previously incorrectly used `32767` which saturates int8 packing).
- Added an `int8` BAM codec roundtrip unit test and documented recommended `scale` defaults in the BAM artifacts/training docs.
- Added a BAM ML implementation review doc (`docs/bam_ml_review.md`) summarizing paper-alignment gaps and a reproducible sanity-check workflow.
- Added an explicit "remaining steps" checklist to drive the repo toward 100% coverage of the updated design goals.
- Fixed `scripts/e22_tool.py` RSSI JSON output and cleaned the printed config formatting.
- Documented `scripts/e22_tool.py rssi` usage in the UART runbook.
- Added plotting support for Phase 3/4 reports: optional `viz` dependency (`matplotlib`) and `scripts/plot_phase_results.py` to produce CSV/PNG summaries.
- Fixed metrics `acked_count` to count ACK events (safe across SEQ wrap) and added window-level delivery fields (`unique_windows_sent`, `delivered_windows`, `delivery_ratio`).
- Unified example RunSpec `run_id` values so TX/RX share the same `run_id` per condition (RAW/LATENT/BAM), matching the reproducibility contract.
- Added reproducibility helpers: `scripts/validate_run.py` (log/artifact/dataset sanity checks) and `scripts/package_run.py` (archive folder/zip with hashes + metrics).
- Added an in-repo Phase 2 BAM trainer (`scripts/phase2_train_bam.py`) that exports runtime-ready artifacts and supports a deterministic train/holdout split (`--train-ratio`, `--split-seed`).
- Added BAM dataset evaluation tooling (`scripts/eval_bam_dataset.py`) with matching split options (`--subset train|holdout|all`) for reproducible MAE/MSE reporting.
- Added Phase 3/4 runbooks and helpers: `docs/phase3_on_air_validation.md`, `docs/phase4_energy_evaluation.md`, `scripts/phase3_report.py`, `scripts/phase4_energy_report.py`, plus record templates (`configs/examples/phase3_record.yaml`, `configs/examples/phase4_record.yaml`).
- Extended metrics reporting to summarize RTT/RSSI when present (`ack_rtt_ms`, `rssi_dbm`) and added `window_id` to TX events to support joining ACKed windows back to `dataset_raw.jsonl`.
- Added a unit test to pin BAM `norm.json` hash verification behavior (`tests/test_artifacts_manifest.py`).
- Added optional UART RSSI-byte support for E22: `--uart-rssi-byte` keeps framing aligned when REG3 bit 7 is enabled, and logs `rssi_dbm` on `rx_ok`/`ack_received`.
- Added `scripts/e22_tool.py` to read/modify E22 00H..06H settings (including RSSI byte output) and documented it in the UART runbook and constraints docs.
- Excluded the reference `ChirpChirp-main/` (and `out/`) from `ruff` and cleaned lint issues so `ruff check .` stays meaningful and green.
- Recorded the field Air Speed preset range as 0-2 for current hardware runs.
- Aligned goal statements (README/design doc) around payload reduction via BAM/FEBAM; deferred delay/loss prediction/adaptation to future work.
- Added `CONTRIBUTING.md` and `SECURITY.md` and linked them from the README.
- Added and started filling a full review checklist to keep goal alignment explicit (`docs/review_checklist.md`).
- Updated the project execution plan to reflect the current RAW baseline (`sensor12_packed`) and on-air binary policy (`docs/project_execution_plan.md`).
- Added a sensor ingestion module (`loralink_mllc/sensing/*`) with JSONL/CSV samplers and
  dataset window logging for BAM training.
- Extended TX CLI to accept real sensor feeds (`--sampler`, `--sensor-path`, `--dataset-out`).
- Added a serial JSONL capture helper (`scripts/capture_serial_jsonl.py`).
- Published the UART + sensing runbook (`docs/runbook_uart_sensing.md`) and sensing schema
  (`docs/sensing_pipeline.md`) with example sensor files in `configs/examples/`.
- Added tests covering sensor parsing and dataset logging.
- Fixed sensor units across docs and dataset outputs (gyro in deg/s, attitude in degrees).
- Added an explicit UART preflight checklist including CRC/header/LDRO recording and
  AUX-less ToA pacing assumptions (`docs/runbook_uart_sensing.md`,
  `docs/radio_constraints_e22.md`, `docs/toa_estimation.md`).
- Added a Phase 0 field C50 runbook and a C50 record template
  (`docs/phase0_c50_field.md`, `configs/examples/c50_record.yaml`).
- Rewrote `README.ko.md` and `docs/project_execution_plan.md` to fix encoding issues and
  align the Korean docs with the current plan.
- Added UART and Phase 1 record templates plus a Phase 1 dataset collection runbook
  (`configs/examples/uart_record.yaml`, `configs/examples/phase1_record.yaml`,
  `docs/phase1_dataset_collection.md`).
- Added a high-level completion dissection for final field measurement readiness
  (this document).
- Added Phase 2 BAM training runbook, record template, and baseline trainer entrypoint
  (`docs/phase2_bam_training.md`, `configs/examples/phase2_record.yaml`,
  `scripts/phase2_train_bam.py`).
- Recorded field PHY parameters (SF12/125k/CR4/5, 300 bps) and antenna gain (10 dBi)
  in UART/C50 record templates; updated runbook notes to require antenna gain and
  PHY settings in C50 records.
- Logged preliminary NLOS field sweep results (2.0-2.6 km) for RAW payload sizes
  32/16/8 bytes with PDR approx 0.10/0.32/0.35; ADR-CODE range set to 000-010.
- Pinned UART config details (ports, 9600 baud, N/1/none, preamble 8, header explicit,
  CRC off, LDRO on, module payload length 7 bytes) in record templates and runbook,
  and updated ADR-CODE profiles for 000-010 to reflect these settings.
- Updated example RunSpecs to match CRC off for field runs (`configs/examples/tx_*.yaml`,
  `configs/examples/rx_*.yaml`).
- Pinned UART parameters (ports/baud/parity/flow control) and CRC/header/LDRO settings
  in `docs/01_design_doc_experiment_plan.md`.
- Recorded E22 address/netid/channel (0x0000/0x00/0x32) and RSSI range (-104 to -101 dBm)
  in the field record templates.
- Set `tx_power_dbm` to 22 across example configs and UART templates to match field runs.

## Completion dissection (final field measurement readiness)
This section defines the high-level path to a complete, field-ready project. It is a
gate-by-gate breakdown with explicit inputs, actions, and pass criteria. Nothing here
asserts completion; it is a checklist for the final build-up.

### Gate A: UART and module settings pinned
- Inputs: real module settings, UART ports, wiring, antenna setup.
- Actions:
  - Fill `configs/examples/uart_record.yaml` with final values.
  - Confirm CRC, header mode, preamble, LDRO, channel, address, netid, baud.
  - Verify AUX is not used; ToA estimation + guard_ms is the pacing rule.
- Pass criteria:
  - RX sees clean `rx_ok` at short range.
  - No persistent `rx_parse_fail` events at short range.
  - TX sees `ack_received` when ACK is enabled.

### Gate B: Sensor pipeline readiness
- Inputs: JSONL or CSV sensor feed.
- Actions:
  - Validate the 12D order and units in `docs/sensing_pipeline.md`.
  - Confirm `dataset_raw.jsonl` windows are length `12 * W`.
  - Confirm timestamps are monotonic or explicitly recorded as-is.
- Pass criteria:
  - No missing fields in the sensor feed.
  - Dataset records contain `order` and `units` and match the RunSpec.

### Gate C: Phase 0 C50 discovery (field)
- Inputs: fixed `adr_code`, fixed `payload_bytes`, stable environment notes.
- Actions:
  - Run RAW-only and vary distance/obstacles to hit PDR ~ 0.50.
  - Record results in `configs/examples/c50_record.yaml`.
  - Use `docs/phase0_c50_field.md` for the field procedure.
- Pass criteria:
  - PDR in the 0.45 to 0.55 band for repeated runs.
  - C50 record includes environment notes and module settings.

### Gate D: Phase 1 dataset capture at C50
- Inputs: C50 record, pinned UART settings, sensor feed.
- Actions:
  - Run TX and RX at C50 and log `dataset_raw.jsonl` on TX.
  - Compute metrics and fill `configs/examples/phase1_record.yaml`.
  - Use `docs/phase1_dataset_collection.md` for the procedure.
- Pass criteria:
  - `dataset_raw.jsonl` present and sized to the target window count.
  - TX and RX logs exist with consistent `run_id`.
  - Metrics report exists for the run.

### Gate E: Phase 2 BAM artifacts ready
- Inputs: dataset, preprocessing rules, chosen BAM architecture.
- Actions:
  - Train offline and export `layer_*.npz`, `norm.json`, `bam_manifest.json`.
  - Update artifacts manifest and payload schema hash.
  - Validate codec inference with the artifacts.
- Pass criteria:
  - Inference succeeds for encode and decode with correct shapes.
  - Manifest fields match the RunSpec and payload size constraints.

### Gate F: Phase 3 on-air validation
- Inputs: C50 conditions, RAW baseline, BAM latent variants.
- Actions:
  - Run multiple payload sizes (vary latent_dim or packing).
  - Compute PDR/ETX and reconstruction MAE/MSE.
- Pass criteria:
  - Report includes baseline vs latent deltas.
  - Smaller payloads show measurable link impact (positive or negative).

### Gate G: Phase 4 energy evaluation
- Inputs: energy measurement method and equipment.
- Actions:
  - Measure baseline and compressed runs under identical conditions.
  - Report energy per delivered window and average power.
- Pass criteria:
  - Energy methodology is recorded and reproducible.
  - Results are tied to `run_id` and C50 conditions.

### Gate H: Final release package
- Inputs: all records, logs, artifacts, and metrics.
- Actions:
  - Archive run artifacts and logs with consistent naming.
  - Update README results section with real plots and links.
  - Freeze configs and record final C50 and UART settings.
- Pass criteria:
  - All docs link correctly and reflect the final field setup.
- Results are traceable to logs and artifacts.

## Next steps (detailed mission list)
This is a step-by-step mission list to reach a complete field-ready release.

### Step 1: UART and module settings fixed
- Fill `configs/examples/uart_record.yaml` with final settings.
- Confirm CRC, header mode, preamble, LDRO, channel, address, netid, baud.
- Verify `rx_ok` stability and lack of persistent `rx_parse_fail`.

### Step 2: Sensor pipeline readiness
- Validate the 12D order and units in `docs/sensing_pipeline.md`.
- Confirm `dataset_raw.jsonl` windows match `12 * W`.
- Ensure all sensor fields are present and timestamps are consistent.

### Step 3: Phase 0 C50 discovery
- Run RAW mode with fixed `adr_code` and `payload_bytes`.
- Adjust distance/obstacles until PDR is 0.45 to 0.55.
- Record results in `configs/examples/c50_record.yaml`.

### Step 4: Phase 1 dataset capture
- Run TX/RX at C50 and log `dataset_raw.jsonl`.
- Compute metrics and fill `configs/examples/phase1_record.yaml`.
- Keep `run_id` consistent across TX/RX/dataset/metrics.

### Step 5: Preprocessing and normalization lock
- Generate `norm.json` from the training split.
- Version the normalization parameters and document their use.

### Step 6: BAM artifacts ready
- Train offline and export `layer_*.npz`, `bam_manifest.json`, `norm.json`.
- Validate artifact schema per `docs/bam_codec_artifacts.md`.

### Step 7: BAM inference verification
- Validate encode/decode shapes and payload size constraints.
- Ensure `payload_bytes <= max_payload_bytes`.

### Step 8: Phase 3 on-air validation
- Run multiple payload sizes at C50.
- Compute PDR/ETX and MAE/MSE vs baseline.

### Step 9: Phase 4 energy evaluation
- Define a repeatable energy measurement method.
- Record average power and energy per delivered window.

### Step 10: Results packaging
- Archive logs, metrics, datasets, and artifacts by `run_id`.
- Add plots under `docs/assets/` and link in README.

### Step 11: Reproducibility closure
- Update `docs/reproducibility.md` with final run artifacts.
- Freeze configs for the final field setup.

### Step 12: Patch notes update
- Append final field run updates and results to this document.

## Core capabilities delivered
- **Packet format**: fixed `LEN|SEQ|PAYLOAD` framing with strict validation and typed errors.
- **ACK rule**: ACK payload is exactly 1 byte `ACK_SEQ` that echoes the uplink SEQ.
- **RunSpec**: YAML/JSON loader with validation for runtime parameters and payload limits.
- **Runtime**: TX/RX nodes with ToA estimation, retry/ACK logic, and JSONL logging.
- **Mock link**: deterministic mock radio for local testing and Phase 0/1 experiments.
- **UART transport**: minimal raw UART framing for E22 (no module configuration).
- **Metrics**: JSONL parsing, PDR/ETX calculations, and report output.
- **Phase 0/1**: mock C50 sweep and RAW vs LATENT A/B runner.
- **Codecs**: RAW, zlib wrapper, BAM inference with external artifacts.
- **Docs**: design plan, protocol notes, ToA estimation, reproducibility, and paper dissections.

## Notable additions and fixes
- **BAM inference**: `loralink_mllc/codecs/bam.py` implements `layer_npz_v1` inference with:
  - layer chaining and shape validation,
  - optional cubic transmission (`delta`),
  - optional normalization (`norm.json`),
  - packing/unpacking (int8/int16/float16/float32).
- **BAM artifacts contract**: `docs/bam_codec_artifacts.md` defines manifest, model layout,
  packing, and normalization rules.
- **BAM toy model generator**: `scripts/make_bam_identity.py` creates an identity/truncation
  model from a manifest for sanity checks.
- **Example configs**: `configs/examples/tx_bam.yaml`, `configs/examples/rx_bam.yaml`,
  `configs/examples/bam_manifest.json`, `configs/examples/artifacts_bam.json`.
- **Completion plan**: `docs/project_execution_plan.md` decomposes the field-measurement
  path (C50 search -> data collection -> BAM training -> on-air validation -> energy).
- **Patch notes**: this document is maintained to track cumulative changes.
- **Manifest integrity**: payload schema hashing and manifest verification are enforced.
- **Metrics spec alignment**: PDR prefers `rx_ok` when present, otherwise uses `ack_received`.
- **Docs alignment**: ADR-CODE table, ToA inputs, and logging schema updated to match runtime.
  Measurement targets and hardware baseline are now called out in `README.md` and `README.ko.md`.
- **Sensor ingestion pipeline**: JSONL/CSV samplers, dataset logger, and a serial capture script
  were added (`docs/sensing_pipeline.md`, `scripts/capture_serial_jsonl.py`,
  `configs/examples/sensor_sample.jsonl`, `configs/examples/sensor_sample.csv`).
  TX CLI now supports `--sampler`, `--sensor-path`, and `--dataset-out`.
- **Field runbook**: `docs/runbook_uart_sensing.md` documents UART bring-up and
  sensor capture procedures for real measurements.
- **Phase 0 field record**: `docs/phase0_c50_field.md` and
  `configs/examples/c50_record.yaml` define C50 search and recording.
- **Phase 1 field record**: `docs/phase1_dataset_collection.md` and
  `configs/examples/phase1_record.yaml` define dataset capture at C50.
- **UART record**: `configs/examples/uart_record.yaml` captures module settings used
  during field runs.
- **Phase 2 training**: `docs/phase2_bam_training.md` and
  `configs/examples/phase2_record.yaml` capture offline training artifacts and settings.

## Tests added or updated
- Packet validation and ACK behavior.
- ToA monotonicity checks.
- Scheduler gating with injectable clock.
- JSONL logging schema validation.
- End-to-end mock TX/RX.
- BAM inference roundtrip tests (skipped if numpy is missing).
- Sensor ingestion parsing and dataset logger tests.

## Known limitations
- UART driver is a minimal transport only; module configuration is external.
- BAM training is provided as a baseline script; model quality/tuning is workload-dependent.
- Mock TX and RX are not connected across separate processes without a shared link.
- Power sampling is external; helper scripts only compute derived energy metrics.
- Direct hardware sensor drivers are not included; the runtime uses a dummy sampler by default.
  JSONL/CSV ingestion is available, but capture must be handled externally.

## Pre-field readiness review (2026-01-17)
This is an objective readiness assessment before the first real field test. It does **not** claim
the KPI targets are achieved yet (that requires field data).

### Objective quality gates (codebase)
- `ruff check .`: PASS
- `python -m pytest`: PASS (181 tests)
- `python -m pytest --cov=loralink_mllc`: PASS (TOTAL 100% statement coverage)

### Architecture completeness (qualitative)
- **Data plane**: `TxNode` (sample/window -> codec -> packetize) -> `UartE22Radio` -> LoRa link ->
  `RxNode` (parse -> log -> ACK).
- **Control plane**: RunSpec YAML/JSON + artifacts manifests provide a stable contract between
  runtime, datasets, and offline evaluation.
- **Observability**: JSONL logs are consistent across TX/RX and support reproducible metrics
  computation and post-run validation/packaging.

### Runtime logic readiness (qualitative + risk)
- **No AUX pin assumption** is handled by conservative pacing: ToA estimation + `guard_ms`, with
  optional RSSI byte capture (`--uart-rssi-byte`) and robust ACK timeout behavior.
- **Key remaining risk**: ToA accuracy depends on correct mapping of the hardware AT "Air Speed"
  preset to (SF/BW/CR/LDRO). This must be confirmed and recorded per firmware version before KPI
  claims.

### Measurement readiness for KPI claims (objective)
- **PDR/ETX** are computed from logs (`loralink_mllc.cli metrics`, `scripts/phase3_report.py`).
- **Information preservation** (roundtrip MAE/MSE on delivered windows) is computed from
  `dataset_raw.jsonl` + codec artifacts (`scripts/phase3_report.py`).
- **Energy** is computed from manual power measurements merged with metrics
  (`scripts/phase4_energy_report.py`).
- **Baseline-relative KPI deltas** are computed with thresholds (PDR +30%, ETX -20%, energy -20%)
  via `scripts/kpi_check.py`.

### Recent pre-field patches added (field enablement)
- SX1262 datasheet-aligned ToA estimation and `phy.ldro` support (auto/force).
- `tx.ack_timeout_ms: auto` support with per-frame timeout estimation (data + ACK ToA + margin).
- Live sensor tail mode (`--sensor-follow`) and RX stop controls (`--max-rx-ok`, `--max-seconds`).
- Fixed-size payload baselines for 32/16/8-byte experiments:
  `sensor12_packed_truncate` codec + example RunSpecs/manifests under `configs/examples/`.

### Completion verdict (pre-field)
- **Software pipeline**: ready for real field runs with two E22-900T22S/SX1262 nodes over UART.
- **Scientific validation**: not complete until Phase 3/4 field data is collected and KPI deltas are
  computed vs baseline.

### Planned patches (if issues appear during field validation)
**P0 (recommended before the first KPI run)**
1) Freeze the AT Air Speed preset mapping for the target firmware; update and lock:
   - `configs/examples/uart_record.yaml` (firmware + preset index)
   - `configs/examples/phy_profiles.yaml` and `docs/phy_profiles_adr_code.md` (derived SF/BW/CR/LDRO)
2) Improve multi-run aggregation ergonomics:
   - Extend `scripts/phase3_report.py` to accept multiple `--dataset` paths (or add a concat helper),
     so `report_all.json` can be generated from per-run dataset files without manual merging.
3) Freeze the evaluation matrix for claims (baseline + variants) and record it in templates:
   - baseline: RAW 32/16/8 (naive truncation) + at least one BAM latent size target
   - variants: BAM packing/latent_dim grid for the same C50 condition

**P1 (deployment hygiene)**
4) Add GitHub Actions CI gate (ruff + pytest + coverage threshold) for release readiness.
5) Replace placeholder docs: `LICENSE_TODO.md`, `CITATION.cff` TODO fields, and link final reports.

**P2 (optional, hardware automation / future work)**
6) Optional GPIO-assisted mode switching and config capture (M0/M1/RESET) to reduce manual steps.
7) Implement SNR capture if the target AT firmware exposes it; otherwise document it as unavailable.

## Remaining steps (to reach 100% coverage)
This section tracks **what is still missing** to fully match the updated final goal in
`docs/01_design_doc_experiment_plan.md`. Field execution steps are listed earlier in this document
(Step 1..12); the checklist below focuses on **design/implementation closure**.

### A) Scope + metrics closure
- [x] Add local latency fields (`queue_ms`, `e2e_ms`) and metrics reporting.
- [ ] Define cross-device E2E latency (clock sync plan + start/end events) and implement logging + reporting.
- [x] Implement RSSI capture via optional trailing RSSI byte (`--uart-rssi-byte`).
- [ ] Implement SNR capture (if supported by the target firmware) or document it as unavailable.

### B) Missing runtime capability (final-goal features)
- [ ] Implement ML-based delay/loss prediction and compensation/optimization logic (what it controls: retries, pacing, PHY, redundancy, payload sizing).
- [ ] Confirm vendor Air Speed preset ↔ SF/BW/CR mapping; update `configs/examples/phy_profiles.yaml` and lock the module firmware version in run records.
- [ ] Characterize UART constraints (mode switching pins/sequence, max UART payload per write) and implement safe chunked writes / config helpers if needed.

### C) Experiment constants (lock for reproducibility)
- [ ] Freeze `window.W`, `window.stride`, `window.sample_hz`, and TX send interval; update RunSpecs + record templates accordingly.
- [ ] Decide GPS preprocessing (raw lat/lon vs local tangent plane) and store it as part of preprocessing spec + payload schema hash.
- [ ] Choose `guard_ms` based on measured ToA margin for the target module/PHY.
- [ ] Decide ACK channel selection (same channel vs separate) and document/implement consistently.

### D) Docs + release hygiene
- [ ] Run Phase 3/4 on hardware and populate records (`configs/examples/phase3_record.yaml`, `configs/examples/phase4_record.yaml`) and plots under `docs/assets/`.
- [ ] Fill `README.ko.md` results section and link final reports/plots from README(s).
- [ ] Replace repository placeholders: `LICENSE_TODO.md`, `CITATION.cff` TODO fields, and optional Contributing/Security docs.

## File inventory highlights
- Runtime: `loralink_mllc/runtime/tx_node.py`, `loralink_mllc/runtime/rx_node.py`
- Protocol: `loralink_mllc/protocol/packet.py`
- BAM inference: `loralink_mllc/codecs/bam.py`, `loralink_mllc/codecs/bam_artifacts.py`
- UART transport: `loralink_mllc/radio/uart_e22.py`
- Experiments: `loralink_mllc/experiments/phase0_c50.py`, `loralink_mllc/experiments/phase1_ab.py`
- Docs hub: `README.md`, `README.ko.md`, `docs/01_design_doc_experiment_plan.md`
