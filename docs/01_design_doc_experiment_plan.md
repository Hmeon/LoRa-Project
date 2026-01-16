# Experiment Design Sheet (UART + E22-900T22S / SX1262) - Payload Reduction via ML Lossy Compression (Multi-layer BAM)
**Purpose:** This document is a single source of truth for **packet format, UART control assumptions, LoRa PHY profiles (ADR-CODE table), logging schema, and phase-based experiments** for the project:
> **"Improve LoRa communication in interference/loss environments by reducing payload size while preserving information using ML lossy compression (multi-layer BAM)."**

This repo is the completion/deployment target for the earlier `ChirpChirp-main/` project.

**Final goal (updated):** Use ML to predict and compensate for delay and packet loss on
field LPWA LoRa/LoRaWAN networks (E22-900T22S / SX1262), measure latency, packet loss,
and signal strength, demonstrate PDR improvement and latency reduction, and deliver
a reproducible MVP prototype. The current phases focus on payload reduction, logging,
and codec validation; predictive/compensation modeling and LoRaWAN support are not
implemented in this repo yet.

**TODO (implementation gaps):**
- Define LoRaWAN scope (class/region/frequency) and implement runtime support.
- Define latency metrics (ACK RTT vs E2E) and measurement workflow.
- Add RSSI/SNR capture path for AT UART modules.
- Implement ML-based delay/loss prediction and recovery/optimization logic.
- Confirm Air Speed preset to PHY mapping with vendor documentation; current mapping uses ADR-CODE table.

**Key constraints to respect (non-negotiable):**
1. **UART-based** control/data path between Raspberry Pi and E22-900T22S.
2. **E22-900T22S is a HAT module without AUX pin**, so **true TxDone / Time-on-Air (ToA) cannot be measured directly**.
3. Therefore, **ToA is estimated** using a **LoRa calculator** (or equivalent formula) and must be recorded as an **approximation**.
4. The **application-layer packet format is fixed**: `LEN(1B) + SEQ(1B) + PAYLOAD(variable)`.
5. **E22 UART P2P TX packet length limit is 240 bytes**. With a 2-byte app header, `LEN <= 238` and `(2 + LEN) <= 240`.

---

## 1) Project Targets (KPI)
The project is designed to enable field deployment by improving reliability and efficiency through payload reduction.

- **PDR:** +30% or more (relative to baseline)
- **ETX:** -20% or more (relative to baseline)
- **Power:** -20% or more (relative to baseline)

> NOTE: KPI computation method is defined in Section 9.

---

## 2) Hardware and Node Roles
### 2.1 Devices
- **Compute/Control:** Raspberry Pi (TX node + RX node)
- **LoRa Modules:** E22-900T22S (SX1262 core) x2
- **Status Indicators:** Breadboard + LEDs (optional)

### 2.2 Node Responsibilities
- **TX node**
  - Acquire 12D multi-sensor time-series
  - Build pattern windows `X(t)` (Section 4)
  - Apply preprocessing/normalization (Section 5)
  - After training: **BAM compress -> latent vector z -> packetize -> UART -> E22 -> LoRa TX**
  - Always store ground truth `x_true` locally for later evaluation (even if RF drop occurs)

- **RX node**
  - UART receive from E22
  - Validate packet (CRC/SEQ)
  - After training: **BAM decode -> reconstruct `x_hat`**
  - Log link metrics (RSSI/SNR if available), RX success/failure, and reconstruction metrics (MAE/MSE)

---

## 3) UART Control Path (Design Requirements)
The LoRa module is controlled/used via UART.

### 3.1 UART parameters (MUST be fixed for reproducibility)
- `serial port device`: TX `/dev/ttyAMA2`, RX `/dev/ttyAMA0`
- `baud rate`: 9600
- `parity / stop bits / flow control`: N / 1 / none
- `TBD: module mode switching pins/sequence` (if applicable on this HAT)
- `TBD: max UART payload per write` (buffering constraints)

> The implementation must **not assume AUX-based timing**. Any "TX complete" decision must be derived from:
- module response over UART (if available), OR
- conservative wait time = `ToA_est + guard`, where `ToA_est` is calculated from PHY profile + payload size.

### 3.2 Waveshare SX1262 LoRa HAT constraints (field hardware)
- The HAT uses an onboard MCU (ESP32-C3) and only exposes UART TX/RX, Busy, and Reset on the header.
  Direct SPI register access and DIO1 IRQ are not available.
- Raspberry Pi can only use AT UART commands; LibDriver-style register control is not possible.
- Air Speed presets 0..7 are fixed PHY bundles inside the AT firmware.
  Record the preset index (and firmware version) in the UART record.
- Because SF/BW/CR cannot be set directly on this hardware, any PHY values used for ToA
  must be derived from the vendor's Air Speed table. If the mapping is unknown, mark it as TODO.

---

## 4) Sensor Data Definition (12D) and Pattern Window Unit
### 4.1 Raw features per time step (12D)
- GPS: latitude, longitude, altitude (3)
- Accelerometer: ax, ay, az (3)
- Gyroscope: gx, gy, gz (3)
- Attitude: roll, pitch, yaw (3)
Fixed vector order (must match RunSpec dims=12):
`[lat, lon, alt, ax, ay, az, gx, gy, gz, roll, pitch, yaw]`
Fixed units:
- lat, lon: degrees
- alt: meters
- accel: m/s^2
- gyro: deg/s
- roll, pitch, yaw: degrees

### 4.2 Pattern definition (MUST be fixed before training)
Because data is time-series, the model input must be defined as a **window pattern**.

- Single step: `x(t) in R^12`
- Window pattern (recommended):
  `X(t) = [x(t-W+1), ..., x(t)] in R^(12*W)`

**Fixed parameters (TBD until confirmed):**
- `sample_hz` = sampling rate (1 / delta_t)
- `W` = window length (number of steps)
- `stride` = window stride (in samples)
- `T_send` = transmit interval (e.g., "1 window per packet")

> All accuracy metrics (MAE/MSE) and matching of `x_true` <-> `x_hat` are defined **per window**.

---

## 5) Preprocessing / Normalization (Fixed Rule)
Because 12D sensors have different physical scales, normalization is mandatory.

### 5.1 Z-score normalization (default fixed)
- Compute mean/std **only from training split**
- Apply the same `(mu, sigma)` on TX and RX
- Save normalization versioned artifact: `norm.json`

**Required artifact fields:**
- `mu[12]`, `sigma[12]`
- version id + dataset version reference

`TBD:` coordinate conversion for GPS (e.g., local tangent plane).
If used, it must be formalized and stored as part of preprocessing spec.

---

## 6) Fixed Application Packet Format
### 6.1 Packet layout (MUST NOT CHANGE)
| Field | Size | Meaning | Must Log |
|---|---:|---|---|
| LEN | 1 byte | Number of bytes in PAYLOAD | YES (`payload_bytes`) |
| SEQ | 1 byte | Sequence number (0..255 wrap) | YES (`seq`) |
| PAYLOAD | variable | Data bytes (mode-dependent) | YES (raw or hash) |

Definition:
- `payload_bytes = LEN`

**E22 UART constraint:** TX packet length <= 240 bytes in P2P UART mode. With a 2-byte app header, `LEN <= 238` and `(2 + LEN) <= 240`.

### 6.2 Payload modes (MUST be explicitly labeled in logs)
- `MODE=RAW`: raw or lightly packed sensor window (baseline)
- `MODE=LATENT`: BAM latent vector `z` (compressed)
- `MODE=ACK`: minimal ACK response (optional, ETX measurement)

**Mode selection:** no mode byte is added to the packet. Mode is run-level metadata and must be logged.
ACK is a response frame type, not a run mode; log it via `ack_received`/`ack_sent` events.

**ACK framing:** ACK payload is exactly 1 byte `ACK_SEQ` (echoed uplink `SEQ`). ACK frames use the same outer format with `LEN=1` and an independent `SEQ`.

---

## 7) LoRa PHY Profiles (Reverse-calculated ADR-CODE Table)
These profiles were **derived by reversing parameters with a LoRa calculator** and are used as the canonical PHY options.

> IMPORTANT: Because AUX is unavailable, ToA is estimated using these PHY profile inputs + payload size.

### 7.1 ADR-CODE mapping (fixed reference table)
| ADR-CODE | Manual Speed | SF/BW/CR | Symbol Time (Tsym) | Real Data Rate |
|---:|---:|---|---:|---:|
| 000 | 0.3 kbps | SF12 / 125 / 4/5 | 32.77 ms | 293 bps |
| 001 | 1.2 kbps | SF10 / 250 / 4/8 | 4.10 ms | 1.2 kbps |
| 010 | 2.4 kbps | SF10 / 500 / 4/8 | 2.05 ms | 2.4 kbps |
| 011 | 4.8 kbps | SF9 / 500 / 4/7 | 1.23 ms | 5.0 kbps |
| 100 | 9.6 kbps | SF5 / 125 / 4/8 | 0.26 ms | 9.7 kbps |
| 101 | 19.2 kbps | SF5 / 250 / 4/8 | 0.13 ms | 19.5 kbps |
| 110 | 38.4 kbps | SF5 / 500 / 4/8 | 0.06 ms | 39 kbps |
| 111 | 62.5 kbps | SF5 / 500 / 4/5 | 0.06 ms | 62.5 kbps |

### 7.2 PHY profile record format (must exist in repo)
Create a versioned config (human + machine readable):
- `phy_profiles.json` or `phy_profiles.yaml`

Each profile entry MUST store:
- `adr_code` (e.g., "000")
- `sf`, `bw_hz`, `cr` (e.g., "4/5")
- `tsym_ms` (from table)
- `real_datarate_bps` (from table)
- `crc_enabled` (TBD; see 7.3)
- `header_mode` (explicit/implicit, TBD)
- `preamble_symbols` (TBD)
- `ldro` (DE / low data rate optimization, TBD)

Mapping notes:
- Use Hz in machine configs (e.g., 125000) even if the table shows kHz.
- `crc_enabled` maps to RunSpec `crc_on`.
- `header_mode` (explicit/implicit) maps to RunSpec `explicit_header`.
- `preamble_symbols` maps to RunSpec `preamble`.
- Air Speed preset values (0..7) and air data rates are documented in
  `docs/E22-900T22S_User_Manual_Deconstructed.md` (REG0 bits 2..0). On AT-only hardware,
  use the preset index to select a row in `configs/examples/phy_profiles.yaml`.

### 7.3 CRC/Header settings (pinned for current field runs)
- crc_enabled: false
- header_mode: explicit
- preamble_symbols: 8
- ldro: on

No ToA estimates are considered valid unless these are pinned.

---

## 8) ToA Estimation Policy (Because AUX is not available)
### 8.1 Why estimation is required
- No AUX means you cannot timestamp TxDone precisely.
- For energy/time analyses and conservative scheduling, you must estimate ToA from PHY + payload length.

### 8.2 Required ToA estimation inputs
Per packet:
- `adr_code` -> `(sf, bw_hz, cr, tsym_ms)`
- `payload_bytes` (LEN)
Global/fixed:
- `crc_enabled`, `header_mode`, `ldro`, `preamble_symbols` (see 7.2 mapping notes)

### 8.3 Output field
- `toa_ms_est`: estimated ToA in ms (approximate; must be labeled as such)

### 8.4 Canonical formula (aligned with typical LoRa calculators)
- `Tsym = 2^SF / BW`
- `Tpreamble = (Npreamble + 4.25) * Tsym`
- `payloadSymbNb = 8 + max( ceil( (8*PL - 4*SF + 28 + 16*CRC - 20*IH) / (4*(SF - 2*DE)) ) * (CR + 4), 0 )`
- `ToA = Tpreamble + payloadSymbNb * Tsym`

Where:
- `PL = payload_bytes`
- `CRC = 1` if enabled else `0`
- `IH = 1` if implicit header else `0`
- `DE = 1` if LDRO enabled else `0`
- `CR` index: 4/5->1, 4/6->2, 4/7->3, 4/8->4

### 8.5 Practical scheduling guard time
Because estimation is imperfect and UART/module buffering may add delay:
- `tx_wait_ms = toa_ms_est + guard_ms`
- `TBD: guard_ms` (choose after initial module characterization)

---

## 9) Metrics Definitions (Fixed)
### 9.1 PDR
- `PDR = (# successfully received DATA packets) / (# sent DATA packets)`
- Success is determined by RX log with valid SEQ and integrity checks.
If only TX logs are available and ACK is enabled, use `ack_received` as a proxy for RX success.

### 9.2 ETX (requires ACK mode to be unambiguous)
If ACK is enabled:
- `ETX = (total DATA transmission attempts) / (DATA packets confirmed by ACK)`

ACK minimal policy:
- ACK payload contains `ACK_SEQ(1B)` referencing the DATA `SEQ`.

Required retransmission controls (must be fixed):
- `R_max` = maximum retries
- `T_ack` = ACK timeout
- `TBD: ACK channel selection` (recommended: separate channel or explicit mode flag)

### 9.3 Power / Energy
- Must define whether power includes Raspberry Pi or only the LoRa module.
- Required outputs (choose at least one):
  - average power over fixed duration
  - energy per successfully delivered window
  - energy per packet attempt
- `TBD: measurement equipment + sampling rate + integration window`

### 9.4 Reconstruction accuracy (information preservation)
Compute per window:
- `MAE(x_true, x_hat)`, `MSE(x_true, x_hat)`
Additionally compute per sensor group (minimum):
- GPS(3), Acc(3), Gyro(3), RPY(3)

Aggregation rule must be pinned:
- `TBD: aggregate method` (e.g., average over dims, average over windows)

---

## 10) Logging Schema (Minimum Required Fields)
All logs are JSONL with one event per line.

### 10.1 Common fields (all events)
- `ts_ms`
- `run_id`
- `role` (tx or rx)
- `mode` (RAW or LATENT)
- `event`
- `phy_id`

### 10.2 TX events
- `tx_sent`: `seq`, `payload_bytes`, `toa_ms_est`, `guard_ms`, `attempt`
- `ack_received`: `ack_seq`, `rtt_ms` (optional: `window_id`)
- `tx_failed`: `seq`, `reason`, `attempts`
Optional: `window_id`, `adr_code`, `uart_write_len`, `tx_power_dbm`, `channel`, `address`.
Note: the runtime logs `window_id` on TX events when `--dataset-out` is used so post-run
analysis can join delivered windows to `dataset_raw.jsonl`.

### 10.3 RX events
- `rx_ok`: `seq`, `payload_bytes`
- `rx_parse_fail`: `reason`
- `ack_sent`: `ack_seq`
Optional (TBD): `window_id`, `adr_code`, `crc_ok`, `rssi_dbm`, `snr`.
Note: `rssi_dbm` can be logged when the module appends an RSSI byte (REG3 bit 7) and the runtime is run with `--uart-rssi-byte`.

### 10.4 Reconstruction events (LATENT)
- `recon_done`: `seq`, `mae`, `mse`
- `recon_failed`: `seq`, `reason`
- `recon_not_implemented`: `seq`, `reason`

### 10.5 Run start
- `run_start` embeds the RunSpec and `artifacts_manifest`.

### 10.6 Artifacts manifest
- `codec_id`, `codec_version`, `payload_schema_hash`, `norm_params_hash`, `git_commit`, `created_at`

---

## 11) Phase-based Experiment Plan (Design Sheet)
The project follows a strict order:

1) Find **C50** (approx 50% PDR region)
2) Collect dataset at C50
3) Train model offline
4) Validate on-air with payload reduction
5) Evaluate energy impact

### Phase 0 - Find C50 (approx 50% PDR operating region)
**Goal:** establish a reproducible "loss environment" reference condition.

| ID | Goal | Fixed | Variables | Procedure | Outputs | Stop Rule |
|---|---|---|---|---|---|---|
| P0-1 | Find C50 for baseline PHY | `adr_code` fixed (project range: 000-010), `payload_bytes` fixed, `T_send` fixed | distance / obstacle / antenna orientation / tx_power (if available) | transmit N packets and log RX success | PDR, RSSI/SNR dist, burst loss stats | stable PDR 45-55% across repeated runs |

**C50 definition MUST include:**
- `adr_code`, `payload_bytes`, and physical setup notes (distance/obstacles)

> If `adr_code` changes, C50 may change. Treat C50 as `C50(adr_code, payload_bytes)` unless proven otherwise.

### Phase 1 - Dataset Collection at C50
**Goal:** capture ground truth windows + RF receive outcomes.

| ID | Goal | Fixed | Variables | Procedure | Outputs | Stop Rule |
|---|---|---|---|---|---|---|
| P1-1 | Collect training dataset | C50 fixed, `W/delta_t` fixed, preprocessing fixed | collection duration / window count | TX stores `x_true` for every window; sends packets; RX logs what was received | `dataset_raw` + `tx_log` + `rx_log` | target #windows reached |

### Phase 2 - Train BAM Offline (Artifacts Must be Versioned)
**Goal:** produce deployable model with explicit config.

| ID | Goal | Fixed | Design Axes | Procedure | Outputs | Stop Rule |
|---|---|---|---|---|---|---|
| P2-1 | Train multi-layer BAM | split rule fixed, preprocessing fixed | `W`, latent dim `k`, layer counts/neurons | train/evaluate | `layer_*.npz` + `bam_manifest.json` + `norm.json` | candidate set completed |

Mapping rule:
- `k` determines **compressed payload size** (after quantization/packing policy).

Numeric representation for latent vector over-the-air:
- Packing must be one of `float32`, `float16`, `int8`, `int16`.
- The chosen packing and scale must be recorded in `bam_manifest.json` and drive `payload_bytes`.

### Phase 3 - On-air Validation (Payload Reduction)
**Goal:** prove that smaller payload improves link metrics while preserving information.

#### P3-1: Link metrics vs payload size (primary)
| ID | Goal | Fixed | Variables | Procedure | Outputs |
|---|---|---|---|---|---|
| P3-1 | PDR/ETX vs payload_bytes | C50 fixed, `adr_code` fixed, `T_send` fixed | `payload_bytes` (via different `k`/packing) | run each condition for same N windows | PDR, ETX (if ACK), RSSI/SNR, ToA_est |

#### P3-2: Reconstruction accuracy vs payload size
| ID | Goal | Fixed | Variables | Procedure | Outputs |
|---|---|---|---|---|---|
| P3-2 | MAE/MSE vs payload_bytes | same as P3-1 | optionally vary `W` separately | TX stores `x_true`, RX reconstructs `x_hat` | MAE/MSE overall + per group |

### Phase 4 - Energy/Power Evaluation
**Goal:** confirm power reduction aligned with fewer retransmissions and shorter ToA.

| ID | Goal | Fixed | Variables | Procedure | Outputs |
|---|---|---|---|---|---|
| P4-1 | Power vs payload_bytes | C50 fixed, `adr_code` fixed, measurement method fixed | `payload_bytes` | same runtime per condition | avg power, energy per delivered window, CPU load (optional) |

---

## 12) Baseline Definition (Must be pinned)
Baseline must be explicitly defined to compute KPI improvements.

- Baseline mode: `MODE=RAW`
- Baseline payload structure: `sensor12_packed` v1 (30 bytes/step; gps float32 + IMU/rpy int16 fixed-point).
- Baseline PHY: choose one ADR-CODE and keep constant (recommended: `000` for robust link unless protocol requires otherwise)

Improvement formulas:
- `PDR_gain(%) = (PDR_new - PDR_base) / PDR_base * 100`
- `ETX_reduction(%) = (ETX_base - ETX_new) / ETX_base * 100`
- `Power_reduction(%) = (P_base - P_new) / P_base * 100`

---

## 13) Pre-run Checklist (Must Complete Before Any "Official" Run)
### UART / Module
- [ ] Confirm UART port + baud + framing
- [ ] Confirm how to set **ADR-CODE profile** on E22 (mapping to module config)
- [ ] Confirm whether CRC is enabled and header mode (explicit/implicit)
- [ ] Confirm preamble symbols, LDRO behavior

### Data
- [ ] Confirm `delta_t`, `W`, `T_send`
- [ ] Confirm preprocessing and save `norm.json`

### Experiments
- [ ] Confirm retransmission policy (`R_max`, `T_ack`) if ETX is required
- [ ] Confirm C50 search protocol (N packets, repeated runs)
- [ ] Confirm baseline payload packing format

### Measurement
- [ ] Confirm RSSI/SNR availability and extraction method (if supported)
- [ ] Confirm power measurement hardware/software and sampling

---

## 14) Deliverables (Minimum Reproducibility Package)
- `phy_profiles.(json|yaml)` (includes ADR-CODE table fields + CRC/header/preamble/LDRO decisions)
- `experiment_design.md` (this file)
- `dataset_raw/` (TX ground truth + timestamps)
- `tx_log.jsonl`, `rx_log.jsonl` (ACK events recorded in TX log)
- `models/<model_version>/{layer_*.npz, norm.json}`
- `models/<model_version>/bam_manifest.json` (BAM codec manifest; see docs/bam_codec_artifacts.md)
- `analysis_report.md` (PDR/ETX/Power/MAE/MSE + ToA_est caveat)

---

## 15) Definitions (Fixed Terms)
- `x_true`: ground truth window stored at TX
- `z`: compressed latent vector produced by BAM
- `x_hat`: reconstructed window at RX
- `payload_bytes`: `LEN` field (application payload size)
- `k`: latent dimension before packing; packing determines payload_bytes
- `adr_code`: PHY profile selector from Section 7
- `ToA_est`: estimated Time-on-Air (approximation; AUX not available)
- `C50`: reproducible condition with PDR approx 50% (must include adr_code + payload_bytes)

---
END
