# Experiment Design Sheet (UART + E22-900T22S / SX1262) — Payload Reduction via ML Lossy Compression (Multi-layer BAM)
**Purpose:** This document is a single source of truth for **packet format, UART control assumptions, LoRa PHY profiles (ADR-CODE table), logging schema, and phase-based experiments** for the project:
> **“Improve LoRa communication in interference/loss environments by reducing payload size while preserving information using ML lossy compression (multi-layer BAM).”**

**Key constraints to respect (non-negotiable):**
1. **UART-based** control/data path between Raspberry Pi and E22-900T22S.
2. **E22-900T22S is a HAT module without AUX pin**, so **true TxDone / Time-on-Air(ToA) cannot be measured directly**.
3. Therefore, **ToA is estimated** using a **LoRa calculator** (or equivalent formula) and must be recorded as an **approximation**.
4. The **application-layer packet format is fixed**: `LEN(1B) + SEQ(1B) + PAYLOAD(variable)`.

---

## 1) Project Targets (KPI)
The project is designed to enable field deployment by improving reliability and efficiency through payload reduction.

- **PDR:** +30% or more (relative to baseline)
- **ETX:** −20% or more (relative to baseline)
- **Power:** −20% or more (relative to baseline)

> NOTE: KPI computation method is defined in Section 9.

---

## 2) Hardware & Node Roles
### 2.1 Devices
- **Compute/Control:** Raspberry Pi (TX node + RX node)
- **LoRa Modules:** E22-900T22S (SX1262 Core) × 2
- **Status Indicators:** Breadboard + LEDs (optional)

### 2.2 Node Responsibilities
- **TX node**
  - Acquire 12D multi-sensor time-series
  - Build pattern windows `X(t)` (Section 4)
  - Apply preprocessing/normalization (Section 5)
  - After training: **BAM compress → latent vector z → packetize → UART → E22 → LoRa TX**
  - Always store ground truth `x_true` locally for later evaluation (even if RF drop occurs)

- **RX node**
  - UART receive from E22
  - Validate packet (CRC/SEQ)
  - After training: **BAM decode → reconstruct `x_hat`**
  - Log link metrics (RSSI/SNR if available), rx success/failure, and reconstruction metrics (MAE/MSE)

---

## 3) UART Control Path (Design Requirements)
The LoRa module is controlled/used via UART.

### 3.1 UART parameters (MUST be fixed for reproducibility)
- `TBD: serial port device` (e.g., `/dev/serial0`, `/dev/ttyS0`, `/dev/ttyAMA0`, etc.)
- `TBD: baud rate`
- `TBD: parity / stop bits / flow control`
- `TBD: module mode switching pins/sequence` (if applicable on this HAT)
- `TBD: max UART payload per write` (buffering constraints)

> The implementation must **not assume AUX-based timing**. Any “TX complete” decision must be derived from:
- module response over UART (if available), OR
- conservative wait time = `ToA_est + guard`, where `ToA_est` is calculated from PHY profile + payload size.

---

## 4) Sensor Data Definition (12D) & Pattern Window Unit
### 4.1 Raw features per time step (12D)
- GPS: latitude, longitude, altitude (3)
- Accelerometer: ax, ay, az (3)
- Gyroscope: gx, gy, gz (3)
- Attitude: roll, pitch, yaw (3)

### 4.2 Pattern definition (MUST be fixed before training)
Because data is time-series, the model input must be defined as a **window pattern**.

- Single step: `x(t) ∈ R^12`
- Window pattern (recommended):  
  `X(t) = [x(t-W+1), ..., x(t)] ∈ R^(12*W)`

**Fixed parameters (TBD until confirmed):**
- `Δt` = sampling interval
- `W` = window length (number of steps)
- `T_send` = transmit interval (e.g., “1 window per packet”)

> All accuracy metrics (MAE/MSE) and matching of `x_true` ↔ `x_hat` are defined **per window**.

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

### 6.2 Payload modes (MUST be explicitly labeled in logs)
- `MODE=RAW`: raw or lightly packed sensor window (baseline)
- `MODE=LATENT`: BAM latent vector `z` (compressed)
- `MODE=ACK`: minimal ACK response (optional, ETX measurement)

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
- `sf`, `bw_khz`, `cr` (e.g., "4/5")
- `tsym_ms` (from table)
- `real_datarate_bps` (from table)
- `crc_enabled` (TBD; see 7.3)
- `header_mode` (explicit/implicit, TBD)
- `preamble_symbols` (TBD)
- `ldro` (DE / low data rate optimization, TBD)

### 7.3 CRC/Header assumptions (must be verified, not guessed)
- A PHY diagram indicates payload CRC exists, so **CRC is likely enabled**, but the actual E22 setting MUST be confirmed.
  - `TBD: crc_enabled (true/false)`
  - `TBD: header_mode (explicit/implicit)`
  - `TBD: preamble_symbols`
  - `TBD: LDRO`

No ToA estimates are considered valid unless these are pinned.

---

## 8) ToA Estimation Policy (Because AUX is not available)
### 8.1 Why estimation is required
- No AUX means you cannot timestamp TxDone precisely.
- For energy/time analyses and conservative scheduling, you must estimate ToA from PHY + payload length.

### 8.2 Required ToA estimation inputs
Per packet:
- `adr_code` → `(sf, bw, cr, tsym_ms)`
- `payload_bytes` (LEN)
Global/fixed:
- `crc_enabled`, `header_mode`, `ldro`, `preamble_symbols`

### 8.3 Output field
- `toa_ms_est`: estimated ToA in ms (approximate; must be labeled as such)

### 8.4 Canonical formula (aligned with typical LoRa calculators)
- `Tsym = 2^SF / BW`
- `Tpreamble = (Npreamble + 4.25) * Tsym`
- `payloadSymbNb = 8 + max( ceil( (8*PL - 4*SF + 28 + 16*CRC - 20*IH) / (4*(SF - 2*DE)) ) * (CR + 4), 0 )`
- `ToA = Tpreamble + payloadSymbNb * Tsym`

Where:
- `PL = payload_bytes`
- `CRC` = 1 if enabled else 0
- `IH` = 1 if implicit header else 0
- `DE` = 1 if LDRO enabled else 0
- `CR` index: 4/5→1, 4/6→2, 4/7→3, 4/8→4

### 8.5 Practical scheduling guard time
Because estimation is imperfect and UART/module buffering may add delay:
- `tx_wait_ms = toa_ms_est + guard_ms`
- `TBD: guard_ms` (choose after initial module characterization)

---

## 9) Metrics Definitions (Fixed)
### 9.1 PDR
- `PDR = (# successfully received DATA packets) / (# sent DATA packets)`
- Success is determined by RX log with valid SEQ and integrity checks.

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
All logs must be machine-parsable and keyed by `seq` + `window_id`.

### 10.1 TX log (DATA)
- `ts_tx`
- `seq`
- `payload_bytes`
- `mode` (RAW/LATENT)
- `window_id` (reference to stored ground truth)
- `adr_code` + `phy_profile_id`
- `try_idx` (0..R_max)
- `toa_ms_est` (optional during collection; mandatory during analysis)
- `uart_write_len` (optional but helpful)
- `tx_power_dbm` (TBD if controllable)
- `channel` / `address` (module config identifiers, TBD)

### 10.2 RX log (DATA)
- `ts_rx`
- `seq`
- `payload_bytes`
- `mode`
- `adr_code` + `phy_profile_id`
- `crc_ok` (or integrity ok)
- `rssi`, `snr` (if available from module)
- `window_id` (matched to seq)
- `reconstruction_ref` (pointer to `x_hat`)

### 10.3 ACK log (if enabled)
- `ts_ack_rx` (TX side)
- `ack_seq`
- `ack_received` (bool)
- `ack_rtt_ms`
- `etx_counter`

### 10.4 Artifacts
- `dataset_version`
- `preprocessing_version` (norm + optional GPS transform)
- `model_version` (BAM config + weights)
- `phy_profiles_version`
- `experiment_run_id`

---

## 11) Phase-based Experiment Plan (Design Sheet)
The project follows a strict order:

1) Find **C50** (≈50% PDR region)  
2) Collect dataset at C50  
3) Train model offline  
4) Validate on-air with payload reduction  
5) Evaluate energy impact

### Phase 0 — Find C50 (≈50% PDR operating region)
**Goal:** establish a reproducible “loss environment” reference condition.

| ID | Goal | Fixed | Variables | Procedure | Outputs | Stop Rule |
|---|---|---|---|---|---|---|
| P0-1 | Find C50 for baseline PHY | `adr_code` fixed (start with 000 unless specified), `payload_bytes` fixed, `T_send` fixed | distance / obstacle / antenna orientation / tx_power (if available) | transmit N packets and log RX success | PDR, RSSI/SNR dist, burst loss stats | stable PDR 45–55% across repeated runs |

**C50 definition MUST include:**  
- `adr_code`, `payload_bytes`, and physical setup notes (distance/obstacles)

> If `adr_code` changes, C50 may change. Treat C50 as `C50(adr_code, payload_bytes)` unless proven otherwise.

### Phase 1 — Dataset Collection at C50
**Goal:** capture ground truth windows + RF receive outcomes.

| ID | Goal | Fixed | Variables | Procedure | Outputs | Stop Rule |
|---|---|---|---|---|---|---|
| P1-1 | Collect training dataset | C50 fixed, `W/Δt` fixed, preprocessing fixed | collection duration / window count | TX stores `x_true` for every window; sends packets; RX logs what was received | `dataset_raw` + `tx_log` + `rx_log` | target #windows reached |

### Phase 2 — Train BAM Offline (Artifacts Must be Versioned)
**Goal:** produce deployable model with explicit config.

| ID | Goal | Fixed | Design Axes | Procedure | Outputs | Stop Rule |
|---|---|---|---|---|---|---|
| P2-1 | Train multi-layer BAM | split rule fixed, preprocessing fixed | `W`, latent dim `k`, layer counts/neurons | train/evaluate | `model.bin` + `model_config.json` + `norm.json` | candidate set completed |

Mapping rule:
- `k` determines **compressed payload size** (after quantization/packing policy).

`TBD:` numeric representation for latent vector over-the-air:
- float32/float16/int8/int16 packing policy directly impacts `payload_bytes`.

### Phase 3 — On-air Validation (Payload Reduction)
**Goal:** prove that smaller payload improves link metrics while preserving information.

#### P3-1: Link metrics vs payload size (primary)
| ID | Goal | Fixed | Variables | Procedure | Outputs |
|---|---|---|---|---|---|
| P3-1 | PDR/ETX vs payload_bytes | C50 fixed, `adr_code` fixed, `T_send` fixed | `payload_bytes` (via different `k`/packing) | run each condition for same N windows | PDR, ETX (if ACK), RSSI/SNR, ToA_est |

#### P3-2: Reconstruction accuracy vs payload size
| ID | Goal | Fixed | Variables | Procedure | Outputs |
|---|---|---|---|---|---|
| P3-2 | MAE/MSE vs payload_bytes | same as P3-1 | optionally vary `W` separately | TX stores `x_true`, RX reconstructs `x_hat` | MAE/MSE overall + per group |

### Phase 4 — Energy/Power Evaluation
**Goal:** confirm power reduction aligned with fewer retransmissions and shorter ToA.

| ID | Goal | Fixed | Variables | Procedure | Outputs |
|---|---|---|---|---|---|
| P4-1 | Power vs payload_bytes | C50 fixed, `adr_code` fixed, measurement method fixed | `payload_bytes` | same runtime per condition | avg power, energy per delivered window, CPU load (optional) |

---

## 12) Baseline Definition (Must be pinned)
Baseline must be explicitly defined to compute KPI improvements.

- Baseline mode: `MODE=RAW`
- Baseline payload structure: `TBD` (how RAW window is packed)
- Baseline PHY: choose one ADR-CODE and keep constant (recommended: `000` for robust link unless protocol requires otherwise)

Improvement formulas:
- `PDR_gain(%) = (PDR_new - PDR_base) / PDR_base * 100`
- `ETX_reduction(%) = (ETX_base - ETX_new) / ETX_base * 100`
- `Power_reduction(%) = (P_base - P_new) / P_base * 100`

---

## 13) Pre-run Checklist (Must Complete Before Any “Official” Run)
### UART / Module
- [ ] Confirm UART port + baud + framing
- [ ] Confirm how to set **ADR-CODE profile** on E22 (mapping to module config)
- [ ] Confirm whether CRC is enabled and header mode (explicit/implicit)
- [ ] Confirm preamble symbols, LDRO behavior

### Data
- [ ] Confirm `Δt`, `W`, `T_send`
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
- `tx_log.csv`, `rx_log.csv`, `ack_log.csv` (if ACK enabled)
- `models/<model_version>/{model.bin, model_config.json, norm.json}`
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
- `C50`: reproducible condition with PDR ≈ 50% (must include adr_code + payload_bytes)

---
END
