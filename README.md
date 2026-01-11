<div align="center">

# LoRaLink-MLLC
**ML-based Lossy Compression for Robust LoRa (UART, E22-900T22S / SX1262) under Interference and Loss**

![Status](https://img.shields.io/badge/status-active-success)
![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi-blue)
![Radio](https://img.shields.io/badge/radio-SX1262%20(E22--900T22S)-informational)
![Interface](https://img.shields.io/badge/link-UART-yellow)
![Docs](https://img.shields.io/badge/docs-available-brightgreen)

**Core thesis**
Reduce **LoRa payload size** while preserving **information content** via **ML-based lossy compression**, and verify that smaller payloads yield higher **PDR**, lower **ETX**, and lower **power** in lossy/interference regimes.

---

**Quick Links**
[Design Doc](docs/01_design_doc_experiment_plan.md) | [Packet Format](docs/protocol_packet_format.md) | [Radio Constraints](docs/radio_constraints_e22.md) | [ToA Estimation](docs/toa_estimation.md) | [ADR-CODE PHY Profiles](docs/phy_profiles_adr_code.md) | [Metrics Definition](docs/metrics_definition.md) | [Paper Dissections](docs/papers/) | [Korean README](README.ko.md)

</div>

---

## Table of Contents
- [Overview](#overview)
- [Repository Status](#repository-status)
- [Highlights](#highlights)
- [System Constraints (Important)](#system-constraints-important)
- [Hardware and Roles](#hardware-and-roles)
- [Sensor Data Schema](#sensor-data-schema)
- [Packet Format](#packet-format)
- [LoRa PHY Profiles (ADR-CODE)](#lora-phy-profiles-adr-code)
- [AUX-less ToA Estimation Policy](#aux-less-toa-estimation-policy)
- [Compression / Reconstruction Model (BAM-family)](#compression--reconstruction-model-bam-family)
- [Experiment Methodology](#experiment-methodology)
- [Metrics and Target KPIs](#metrics-and-target-kpis)
- [Reproducibility](#reproducibility)
- [Documentation Map](#documentation-map)
- [Project Structure](#project-structure)
- [Roadmap](#roadmap)
- [License](#license)
- [Citation](#citation)
- [Acknowledgements](#acknowledgements)

---

## Overview
This project builds an **IoT-ready LoRa communication pipeline** where **multi-dimensional time-series sensor windows** are **lossily compressed** into a compact latent payload and then **reconstructed** on the receiver. The system is designed to operate in **low-power, high-loss / interference** regimes and to be evaluated with network-level metrics (**PDR/ETX**) and energy metrics (**power/energy**), alongside reconstruction fidelity (**MAE/MSE**).

**What this is (strictly):**
- A **payload reduction** + **information-preserving** transmission architecture over LoRa
- A **measurement-driven** experiment plan centered on the **PDR approx 50% (C50)** regime
- A **BAM-family** ML compression/reconstruction stack (multi-layer extensions to handle multi-pattern complexity)

**What this is not:**
- A new LoRa PHY or MAC redesign
- A security/encryption protocol proposal (you can add this later, but it is not the core thesis here)

---

## Repository Status
This repository contains design docs plus a **Python runtime scaffold** (`loralink_mllc`) with mock radio support and CLI entry points. Hardware UART integration is a placeholder and requires E22 UART configuration and wiring. Sample RunSpec and artifacts manifest files are not included; provide your own under `configs/` or another path.

---

## Highlights
- **UART-based LoRa (E22-900T22S / SX1262 core)** on Raspberry Pi endpoints
- **Fixed packet layout** at the application layer: `LEN(1B) | SEQ(1B) | PAYLOAD(var)`
- **AUX-less ToA limitation handled explicitly:** if AUX is unavailable, ToA is **estimated** and used for guard timing
- **Sensor payload is multi-modal, 12D:** GPS + IMU + Attitude
- **Experiment-first plan:** find **C50**, collect over-the-air (OTA) data there, then train and validate

---

## System Constraints (Important)
> **AUX pin note:** The E22 module supports an AUX pin, but the current HAT/board may not expose it; verify wiring. If AUX is not available, rely on timeouts based on ToA estimation and guard time.

> **Payload drives reliability:** The core hypothesis is that **smaller payload -> shorter airtime -> higher PDR** under loss/interference. Therefore, the compression system must reduce bytes without discarding critical information.

---

## Hardware and Roles
| Component | Model / Spec | Role |
|---|---|---|
| Compute and Control | Raspberry Pi (TX + RX) | Sensor ingest / windowing / compress and reconstruct / UART handling / logging / evaluation |
| LoRa Module | E22-900T22S x2 (SX1262 core) | Long-range, low-power wireless transport via UART |
| Status | Breadboard + LED | Power / TX / RX status indication |

**Deployment shape:** 1 transmitter (TX) + 1 receiver (RX), both Raspberry Pi + E22 module.

---

## Sensor Data Schema
The payload content (before compression) is a **multi-dimensional time-series sensor window**.

**Base fields (12D):**
- **GPS (3):** latitude, longitude, altitude
- **Accelerometer (3):** ax, ay, az
- **Gyroscope (3):** gx, gy, gz
- **Attitude (3):** roll, pitch, yaw

**Windowing (project decision):**
- Define a window length `W` and stride `S`
- Flatten or pack as a `W x 12` vector or structured tensor depending on model implementation
- Maintain a stable normalization policy (document in `docs/metrics_definition.md` and artifacts)

---

## Packet Format
This project distinguishes:
1) **LoRa PHY framing** (preamble/header/CRC handled by radio)
2) **E22 module internal header** (Address/Channel, module-layer)
3) **Application-level payload layout** (this project)

### 1) LoRa PHY (conceptual)
`Preamble + PHY Header + Payload + CRC`

### 2) E22 module control header (conceptual)
`Address + Channel` (module-managed)

### 3) Application-level frame (project-defined)
`LEN (1B) | SEQ (1B) | PAYLOAD (LEN bytes)`

- `LEN`: payload byte length (0..255 by spec)
- `SEQ`: monotonically increasing sequence number (0..255 wrapping)
- `PAYLOAD`: compressed latent representation or RAW window bytes

**E22 UART constraint (P2P mode):** TX packet length <= 240 bytes. With a 2-byte app header, `LEN <= 238` and `(2 + LEN) <= 240`.

**ACK rule:** ACK payload is exactly 1 byte `ACK_SEQ` (echoed uplink `SEQ`). ACK frames use the same outer format with `LEN=1`; the ACK frame `SEQ` may increment independently.

> Full details (including recommended field semantics and logging schema):
> [`docs/protocol_packet_format.md`](docs/protocol_packet_format.md)

---

## LoRa PHY Profiles (ADR-CODE)
Because ToA cannot be measured directly (AUX-less), PHY parameters are treated as **derived/estimated profiles** using LoRa calculator reverse-derivation.

**Parameter table (derived reference):**

| ADR-CODE | Manual Speed | Estimated SF/BW/CR | Symbol Time | Real Data Rate |
|---:|---:|---:|---:|---:|
| 000 | 0.3 kbps | SF12 / 125 / 4/5 | 32.77 ms | 293 bps |
| 001 | 1.2 kbps | SF10 / 250 / 4/8 | 4.10 ms | 1.2 kbps |
| 010 | 2.4 kbps | SF10 / 500 / 4/8 | 2.05 ms | 2.4 kbps |
| 011 | 4.8 kbps | SF9 / 500 / 4/7 | 1.23 ms | 5.0 kbps |
| 100 | 9.6 kbps | SF5 / 125 / 4/8 | 0.26 ms | 9.7 kbps |
| 101 | 19.2 kbps | SF5 / 250 / 4/8 | 0.13 ms | 19.5 kbps |
| 110 | 38.4 kbps | SF5 / 500 / 4/8 | 0.06 ms | 39 kbps |
| 111 | 62.5 kbps | SF5 / 500 / 4/5 | 0.06 ms | 62.5 kbps |

> Full usage rules (how to select profiles, log them, and keep the calculator assumptions consistent):
> [`docs/phy_profiles_adr_code.md`](docs/phy_profiles_adr_code.md)

---

## AUX-less ToA Estimation Policy
**Problem:** The E22 module supports an AUX pin, but the current HAT/board may not expose it. Without AUX, you cannot measure TX completion signal transitions directly.

**Policy (project rule):**
- Use a LoRa calculator to estimate ToA based on:
  - SF / BW / CR
  - payload length (bytes)
  - header/CRC assumptions
- Treat the result as **approximate** and use it consistently:
  - for reporting
  - for profile comparisons
  - for parameter selection
- Do not claim sub-millisecond accuracy from ToA estimates.

> Documented assumptions and calculator configuration:
> [`docs/toa_estimation.md`](docs/toa_estimation.md)

---

## Compression / Reconstruction Model (BAM-family)
This project adopts **BAM-family** lossy compression/reconstruction due to:
- strong restoration capability under corrupted cues (associative recall framing)
- high neuron/resource efficiency under constrained architectures
- multi-pattern weakness in base BAM addressed via **multi-layer** variants (FEBAM / MF-BAM-style structures)

### Core operational principle
- Learn complex sensor patterns and encode them into a **low-dimensional latent** vector
- Transmit latent vector as payload
- Reconstruct original sensor window at the receiver with bounded reconstruction error

### Implementation stance (project-defined)
- **TX path:** `sensor window -> encode(latent) -> packetize -> UART -> LoRa`
- **RX path:** `LoRa -> UART -> latent -> decode(reconstruct) -> logging/metrics`

### Relevant design docs (paper dissections)
- LLN lossy compression + BAM motivation: `docs/papers/02_paper_dissect__bam_lln_lossy_compression.md`
- Kosko BAM fundamentals: `docs/papers/03_paper_dissect__kosko-bam.md`
- FEBAM (feature extracting BAM): `docs/papers/04_paper_dissect__febam.md`
- MF-BAM (multi-feature layers): `docs/papers/05_paper_dissect__mf-bam.md`

> Note: This README intentionally keeps model math minimal. The full why/how lives in the docs above.

---

## Experiment Methodology
The experiment plan is intentionally **measurement-driven** and focuses on a regime where improvements are easiest to attribute and quantify.

### Phase 0 - Find a C50 operating point (PDR approx 50%)
1) Sweep PHY profiles / environmental interference factors
2) Identify the region where baseline PDR stabilizes around approx 50%
3) Lock the environment and configuration (be strict)

### Phase 1 - Collect OTA data at C50
- Send uncompressed or lightly formatted sensor windows (baseline)
- Log:
  - TX sequence numbers, timestamps
  - RX receptions, gaps, RSSI/SNR if available
  - payload sizes
  - energy readings (if instrumented)

### Phase 2 - Train compression model, then validate OTA impact
- Train encoder/decoder on collected sensor windows
- Re-run OTA transmission in the **same C50 conditions**
- Compare:
  - payload bytes reduced
  - PDR, ETX, power
  - reconstruction fidelity (MAE/MSE)

> Full experiment design table (fixed conditions, sweeps, and acceptance rules):
> [`docs/01_design_doc_experiment_plan.md`](docs/01_design_doc_experiment_plan.md)

---

## Metrics and Target KPIs
This project evaluates both **network behavior** and **information preservation**.

### Primary metrics
- **PDR (Packet Delivery Ratio)** - higher is better
- **ETX (Expected Transmission Count)** - lower is better
- **Power / Energy per delivered information unit** - lower is better
- **Reconstruction error (MAE/MSE)** - lower is better

Target KPIs are defined per experiment run and recorded alongside metrics computations.

> Exact definitions, computation rules, and logging schema:
> [`docs/metrics_definition.md`](docs/metrics_definition.md)

---

## Reproducibility
This repository is organized so that a reviewer can reproduce:
1) PHY profile configuration (ADR-CODE)
2) packet format
3) the C50 search procedure
4) data collection + training + OTA validation
5) metric computation

**Repro checklist**
- [ ] Hardware wired and UART enabled on both Raspberry Pis
- [ ] E22 modules configured with the same channel/address rules
- [ ] ADR-CODE profile selected and logged
- [ ] Packet format matches `LEN|SEQ|PAYLOAD`
- [ ] Runs captured with RunSpec, artifacts manifest, and logs
- [ ] Phase 0/1/2 executed in order with fixed conditions
- [ ] PDR/ETX/Power/MAE/MSE computed from logs with documented scripts

> Step-by-step procedure (single source of truth):
> [`docs/reproducibility.md`](docs/reproducibility.md)

---

## Documentation Map
Use README as a **hub**; deep content lives in `docs/`.

### Core docs
- **Design Doc (Experiment Plan):** `docs/01_design_doc_experiment_plan.md`
- **Packet Format:** `docs/protocol_packet_format.md`
- **Radio Constraints (E22 UART):** `docs/radio_constraints_e22.md`
- **ToA Estimation (AUX-less):** `docs/toa_estimation.md`
- **ADR-CODE PHY Profiles:** `docs/phy_profiles_adr_code.md`
- **Metrics Definition:** `docs/metrics_definition.md`
- **Reproducibility:** `docs/reproducibility.md`
- **Paper Dissections:** `docs/papers/`

### Paper dissections (file names)
- `docs/papers/02_paper_dissect__bam_lln_lossy_compression.md`
- `docs/papers/03_paper_dissect__kosko-bam.md`
- `docs/papers/04_paper_dissect__febam.md`
- `docs/papers/05_paper_dissect__mf-bam.md`

---

## Project Structure
```
.
|-- README.md
|-- README.ko.md
|-- docs/
|   |-- 01_design_doc_experiment_plan.md
|   |-- protocol_packet_format.md
|   |-- toa_estimation.md
|   |-- phy_profiles_adr_code.md
|   |-- metrics_definition.md
|   |-- reproducibility.md
|   |-- radio_constraints_e22.md
|   `-- papers/
|       |-- 02_paper_dissect__bam_lln_lossy_compression.md
|       |-- 03_paper_dissect__kosko-bam.md
|       |-- 04_paper_dissect__febam.md
|       `-- 05_paper_dissect__mf-bam.md
|-- configs/
|-- loralink_mllc/
|-- scripts/
|-- src/
|-- tests/
`-- pyproject.toml
```

---

## Roadmap
- [ ] Finalize packet payload schema for latent + minimal metadata
- [ ] Implement logging schema + deterministic metric computation
- [ ] Phase 0: C50 search automation with profile sweep
- [ ] Phase 1: OTA dataset collection at C50
- [ ] Phase 2: Train BAM-family compression model (offline)
- [ ] Phase 3: OTA validation with compressed payload
- [ ] Publish final report: experiment matrix + results + discussion

---

## License
License is not specified yet. Add a `LICENSE` file to define terms.

---

## Citation
Cite the repository URL and a commit hash (or release tag) in your preferred format.

---

## Acknowledgements
This project compression model and design rationale are informed by BAM-family literature (BAM / FEBAM / MF-BAM) and LLN lossy compression framing. See the `docs/papers/` dissections for the project-aligned teardown of those references.

---

<details>
<summary><strong>Troubleshooting (keep README clean; expand only when needed)</strong></summary>

### UART sanity checks
- Confirm UART is enabled and the correct device node is used.
- Verify baud rate and serial framing match the E22 configuration.

### Packet loss vs parsing errors
- Distinguish between:
  - CRC-failed frames (never delivered to application)
  - delivered frames with malformed payload (application-level parsing)
- Always log `SEQ` gaps to separate link loss from application decode failure

### ToA estimation caveat
- ToA is approximate under AUX-less policy.
- Do not interpret ToA-derived numbers as ground truth; use them as consistent approximations.

</details>

---

## LoRaLink-MLLC Runtime Usage (Requires Config Files)
Install dependencies:
```
python -m pip install -e .[dev]
```

Phase 0 (C50 sweep):
```
python -m loralink_mllc.cli phase0 --sweep configs/sweep.json --out out/c50.json
```

Phase 1 (A/B at C50):
```
python -m loralink_mllc.cli phase1 --c50 out/c50.json --raw configs/raw.json --latent configs/latent.json --out out/report.json
```

TX/RX (mock radio by default):
```
python -m loralink_mllc.cli tx --runspec configs/tx.json --manifest configs/artifacts.json
python -m loralink_mllc.cli rx --runspec configs/rx.json --manifest configs/artifacts.json
```

Note: config files are not included in the repo; provide your own RunSpec and artifacts manifest.
