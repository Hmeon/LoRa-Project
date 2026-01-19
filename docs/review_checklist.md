# Full Review Checklist (Goal Alignment)

Purpose: verify that the repository aligns with the updated final goal and that this
repo is the completion/deployment target for `ChirpChirp-main/`.

## 1) Goal and scope alignment
- [x] Confirm updated goal statements in `README.md` and
  `docs/01_design_doc_experiment_plan.md`.
- [ ] Identify components tied only to payload-reduction experiments (Phase 0/1).
- [ ] Decide which legacy components remain in the MVP and which are removed or archived.

## 2) Hardware constraints
- [x] Confirm AT UART-only constraints for Waveshare SX1262 LoRa HAT.
- [x] Confirm Air Speed preset range used in field runs (0..2) and record in
  `configs/examples/uart_record.yaml`.
- [x] Verify that DIO1/IRQ assumptions are not present in the runtime.

## 3) Protocol and PHY
- [x] Validate `LEN|SEQ|PAYLOAD` framing and `max_payload_bytes` enforcement.
- [x] Ensure Air Speed preset mapping is consistent across
  `docs/phy_profiles_adr_code.md` and `configs/examples/phy_profiles.yaml`.

## 4) Data pipeline
- [x] Confirm sensor schema order/units in `docs/sensing_pipeline.md`.
- [x] Verify `dataset_raw.jsonl` meets training and evaluation needs.
- [ ] Define additional telemetry needed for ML prediction/optimization.

## 5) Metrics and logs
- [x] Confirm PDR/ETX calculation rules in `docs/metrics_definition.md`.
- [ ] Define latency metrics (ACK RTT vs E2E) and required log fields.
- [ ] Decide how RSSI/SNR is captured (RSSI byte output is implemented; SNR is TBD).

## 6) ML components
- [x] Clarify the role of BAM inference vs new prediction/optimization models.
- [ ] Define training artifacts and versioning for new ML components.

## 7) Packaging and release
- [ ] Define deployment target and release process (package/image/binary).
- [x] Confirm licensing, security, and contribution docs (License/Contributing/Security/CoC/Support present).

## 8) Repo hygiene
- [x] Review `ChirpChirp-main/` usage: keep as reference, archive, or extract.
- [ ] Remove or relocate obsolete scripts/configs.
- [ ] Update tests to cover the current MVP scope.
