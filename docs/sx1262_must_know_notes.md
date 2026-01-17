# SX1262 (SX1261/2) Datasheet Notes — Must‑Know Items for E22‑900T22S (SX1262 Core) LoRa Experiments

**Source**: Semtech *SX1261/2 Data Sheet* (Rev. 1.2, June 2019).  
**Scope**: Items you must understand to correctly set LoRa parameters, estimate airtime without AUX/ToA telemetry, interpret link metrics (RSSI/SNR), and avoid datasheet‑documented pitfalls.  
**Context**: Your project uses **E22‑900T22S (SX1262 core)** modules controlled via **UART** (module firmware abstracts the SX1262 SPI commands), but the *meaning* and *coupling* of LoRa PHY parameters remains the same.

---

## 0) What this note is (and is not)

- This is **not** a generic LoRa tutorial. It is a **datasheet‑driven “what you must know” extraction**.
- It focuses on:
  - **LoRa symbol/time relationships** and **Time‑on‑Air (ToA)** equations (critical because your HAT module lacks AUX → you estimate ToA externally).
  - **Packet format + header modes** (explicit/implicit) and what must match TX/RX.
  - **Core modulation knobs** (SF/BW/CR/LDRO) and the operational consequences implied by the datasheet.
  - **CAD** (channel activity detection) semantics and timing.
  - **Packet status metrics** (RSSI/SNR) conversion rules.
  - **Command‑level concepts** (even if UART‑hidden) to understand what the radio is *actually* doing.
  - **Known limitations** explicitly listed by the datasheet and their workarounds.

---

## 1) LoRa PHY essentials the datasheet explicitly defines

### 1.1 Spreading Factor (SF) and chips/symbol
The datasheet defines a **range of SF = 5…12**, provides the **chips/symbol = 2^SF**, and gives typical demodulator SNR values per SF (table).  
**Operational meaning**: higher SF increases sensitivity/link budget but increases time‑on‑air.

### 1.2 LoRa symbol rate relationship
The datasheet defines the LoRa symbol rate (equivalently 1/Tsym) as:

- **Symbol rate**:  
  \[
  R_s = \frac{BW}{2^{SF}}
  \]
  where **BW** is the programmed LoRa bandwidth and **SF** is the spreading factor.

From this, the **symbol time** is:
\[
T_{sym}=\frac{2^{SF}}{BW}
\]

> Use this directly for ToA estimation and for judging when LDRO becomes relevant (see 1.4).

### 1.3 Bandwidth options (LoRa mode)
The datasheet lists LoRa signal bandwidth settings (DSB) commonly used in LoRa mode:
- 7.81, 10.42, 15.63, 20.83, 31.25, 41.67, 62.5, 125, 250, 500 kHz  
It also notes that for RF frequencies below 400 MHz, supported BW may scale.

### 1.4 Coding Rate (CR) overhead (FEC)
The datasheet provides CR settings and overhead ratios:

| CR setting | Coding rate | Overhead ratio |
|---:|---:|---:|
| 1 | 4/5 | 1.25 |
| 2 | 4/6 | 1.5 |
| 3 | 4/7 | 1.75 |
| 4 | 4/8 | 2 |

**Operational meaning** (datasheet phrasing): higher coding rate improves noise immunity at the cost of longer time‑on‑air. In normal conditions, **4/5** is “best trade‑off”; stronger interference may justify higher CR.

### 1.5 Low Data Rate Optimization (LDRO)
The datasheet states LDRO can be enabled for low data rates (high SF or low BW) and long payloads (airtime can last several seconds).  
It recommends LDRO when **LoRa symbol time is ≥ 16.38 ms**.

**Effect in the datasheet ToA equation**: when LDRO is active (for “all other SF”), the denominator term changes from **4·SF** to **4·(SF−2)** (see Section 3).

---

## 2) Packet engine & packet formats you must align in your experiments

### 2.1 LoRa packet formats (fixed vs variable length)
The datasheet gives two LoRa packet formats:

- **Fixed‑Length**:  
  `Preamble + Payload CRC`  
  (no variable header)
- **Variable‑Length**:  
  `Preamble + PHY Header + Payload CRC`

In both, the datasheet indicates the payload part is:
- **Payload + Payload CRC** (if CRC enabled)

### 2.2 Explicit header vs implicit header (critical coupling rule)
The datasheet defines **implicit header mode** and states:

- In implicit header mode, the **header is removed** from the packet.
- Therefore, **payload length**, **error coding rate**, and **CRC presence** must be **manually configured identically on both TX and RX sides**.

> In your project: if you choose implicit header to reduce airtime, your TX/RX configuration must be strictly locked and versioned; otherwise, RX decoding fails even if RF reception occurs.

### 2.3 Preamble length guidance
The datasheet notes:
- For **SF5 and SF6**, users are invited to use **12 symbols of preamble** for optimal performance over receiver dynamic range.
- Preamble length should be aligned between transmitter and receiver.
- If receiver does not know the exact preamble length, it can be configured with the **maximum preamble length**.

---

## 3) Time‑on‑Air (ToA): the exact datasheet equations you should implement

This section is **the key** for your HAT module case where AUX is not available and ToA is externally estimated.

### 3.1 Core ToA relation
The datasheet gives:

\[
ToA = \frac{2^{SF}}{BW}\cdot N_{symbol}
\]

with:
- **SF**: spreading factor (5…12)
- **BW**: bandwidth (in kHz)  
- **ToA**: time‑on‑air in ms  
- **N_symbol**: number of symbols

### 3.2 Number of symbols (SF5 and SF6)
For **SF5 and SF6**, the datasheet states:

\[
N_{symbol}=N_{symbol\_preamble}+6.25+8+\left\lceil\frac{\max(8\cdot N_{byte\_payload}+N_{bit\_CRC}-4\cdot SF+N_{symbol\_header},0)}{4\cdot SF}\right\rceil\cdot(CR+4)
\]

### 3.3 Number of symbols (all other SF)
For **SF7…SF12**, the datasheet states:

\[
N_{symbol}=N_{symbol\_preamble}+4.25+8+\left\lceil\frac{\max(8\cdot N_{byte\_payload}+N_{bit\_CRC}-4\cdot SF+8+N_{symbol\_header},0)}{4\cdot SF}\right\rceil\cdot(CR+4)
\]

### 3.4 Number of symbols (SF7…SF12 with LDRO enabled)
For **SF7…SF12 with LDRO activated**, the datasheet states:

\[
N_{symbol}=N_{symbol\_preamble}+4.25+8+\left\lceil\frac{\max(8\cdot N_{byte\_payload}+N_{bit\_CRC}-4\cdot SF+8+N_{symbol\_header},0)}{4\cdot(SF-2)}\right\rceil\cdot(CR+4)
\]

### 3.5 Constants the datasheet defines for the ToA formula
The datasheet defines:
- \(N_{bit\_CRC}=16\) if CRC enabled, else 0
- \(N_{symbol\_header}=20\) with **explicit** header, 0 with **implicit** header
- \(CR \in \{1,2,3,4\}\) mapping to coding rates 4/5, 4/6, 4/7, 4/8

### 3.6 Practical usage in your project (ToA without AUX)
- Use the above equations to compute the **airtime per packet**.
- In your UART E22 module setting, you will typically choose an (SF, BW, CR) tuple indirectly (e.g., via your ADR code / air data rate presets).  
  Even when abstracted, the ToA physics remain: **reduce payload → reduce N_symbol → reduce ToA** → reduce collision probability / channel occupancy (your project hypothesis).

---

## 4) Channel Activity Detection (CAD): what the datasheet actually promises

### 4.1 Why CAD exists (datasheet reasoning)
The datasheet states that spread spectrum makes it difficult to know whether the channel is in use when signals are below the receiver noise floor; RSSI becomes impracticable, therefore **CAD is used to detect presence of other LoRa signals**.

### 4.2 What CAD detects on SX1261/2
The datasheet states SX1261/2 CAD is designed to detect the presence of a **LoRa preamble or data symbols** (where prior generations only detected preamble symbols).

### 4.3 CAD duration and timing
The datasheet states:
- CAD scans the band for a **user‑selectable duration defined in number of symbols**.
- Typical CAD detection time is selectable as **1, 2, 4, 8, or 16 symbols** (for a given SF/BW).
- After scanning the chosen number of symbols, the radio remains around **half a symbol in Rx** to post‑process.

> For your experiments: CAD is a *mechanism* to gate transmission attempts based on activity; if you do not use CAD, you still need to interpret PDR vs airtime under contention.

---

## 5) Link quality observability: how to interpret RSSI/SNR from SX1262

Even if your UART module exposes metrics differently, the SX1262 datasheet defines how the chip internally reports packet status.

### 5.1 GetPacketStatus conversions (datasheet)
The datasheet describes that **GetPacketStatus()** returns (among others) **RssiPkt**, **SnrPkt**, **SignalRssiPkt** and defines conversions:

- **RssiPkt (dBm)** = \(-\frac{RssiPkt}{2}\)
- **SnrPkt (dB)** = \(\frac{SnrPkt}{4}\)
- **SignalRssiPkt (dBm)** = \(-\frac{SignalRssiPkt}{2}\)

### 5.2 Instantaneous RSSI (datasheet)
Similarly, **GetRssiInst()** returns a value converted as:
- **RssiInst (dBm)** = \(-\frac{RssiInst}{2}\)

### 5.3 Important note for your “TX power from RSSI?” question
A receive RSSI value (e.g., **−101…−104 dBm**) **does not uniquely determine TX output power**.  
To relate them, you would need the path loss (distance/environment), antenna gains, and system losses:
\[
P_{RX} = P_{TX} + G_{TX} + G_{RX} - L_{path} - L_{misc}
\]
Therefore, **tx_power_dbm is a configuration parameter**, not inferable from RSSI alone.

---

## 6) LoRa parameter knobs at the command/driver layer (UART‑hidden but conceptually required)

Your E22 module firmware hides the SX1262 SPI commands; however, understanding the driver‑level structure helps you:
- Ensure your UART presets are consistent
- Know which parameters must match on both nodes
- Debug (e.g., when PDR collapses because one side is in implicit header or IQ inversion differs)

### 6.1 Packet type and configuration order (datasheet concept)
The datasheet indicates LoRa/FSK configuration is driven by a sequence of “Set…” commands; a key concept is that **packet type is set explicitly** (LoRa vs FSK) and the subsequent parameter sets apply to that packet type.

### 6.2 Modulation parameters (LoRa)
The datasheet defines LoRa modulation parameters as:
- **SF** (5…12)
- **BW** (bandwidth enum → kHz list)
- **CR** (4/5…4/8)
- **LDRO** (0/1)

### 6.3 Packet parameters (LoRa)
The datasheet defines LoRa packet parameters as:
- **PreambleLength**
- **HeaderType**: explicit vs implicit
- **PayloadLength**
- **CRCType**: on/off
- **InvertIQ**: standard vs inverted

> These must be consistent with the packet format and receiver expectations (Sections 2–3).

### 6.4 RF frequency setting concept
The datasheet defines the RF frequency register representation using:
- PLL step: \(FreqStep = \frac{XtalFreq}{2^{25}}\)  
and the RF frequency is set via a scaled integer value.

> For your UART module: you likely set “frequency band/channel” at module level; the underlying SX1262 uses this representation.

### 6.5 TX power control concept
The datasheet defines TX output power control via:
- **PA configuration** (PA selection and tuning)
- **TX parameters** (power level in dBm + ramp time)

Your UART module typically exposes this as **a small discrete set of dBm steps** (e.g., 22/17/13/10 dBm), while the chip’s interface is more granular.

---

## 7) Datasheet “Known Limitations” you must account for

The SX1261/2 datasheet includes an explicit “Known Limitations” section; items that commonly matter for real deployments include:

### 7.1 Implicit header mode with Rx timeout
The datasheet documents a limitation when using **implicit header mode with Rx timeout**; the described workaround is to avoid that combination in the impacted case (follow the datasheet’s limitation note).

### 7.2 TX ramp‑up clipping / PA trimming
The datasheet documents a limitation related to TX ramp behavior and gives a trimming register workaround (datasheet lists register address and value adjustment guidance).

### 7.3 QoS degradation at 500 kHz BW
The datasheet documents that QoS can be degraded at **500 kHz bandwidth** and provides a workaround / operational recommendation in the limitation note.

> For your project: if you use BW=500 kHz presets (high speed), treat datasheet limitations as constraints; validate with PDR sweeps rather than assuming behavior matches BW=125/250.

---

## 8) What must be “locked” and versioned in your PDR‑50% data collection phase

When you perform:
1) **Search the ~50% PDR operating point**
2) **Collect TX/RX data at that point**
3) **Train/test compression model**

you must treat the following as **fixed experimental controls** (because they fundamentally define airtime, decoding, and link budget):

### 8.1 Radio PHY controls (must match TX/RX)
- Frequency / channel plan
- SF, BW, CR
- Preamble length
- Header mode (explicit/implicit)
- CRC on/off
- IQ inversion (standard vs inverted)

### 8.2 TX controls
- TX power setting (dBm)
- Ramp time (if exposed)
- Packet interval / duty cycle
- Payload size (raw vs compressed)

### 8.3 RX controls
- Rx windowing / timeout policy (continuous vs timed)
- Any CRC filtering / frame rejection policy

### 8.4 Metrics to log per packet
- Sequence number (SEQ)
- Payload byte length
- Timestamp TX/RX
- Packet status metrics (RSSI/SNR) *as available*
- Drop reason classification (timeout, CRC fail, header mismatch, etc.)

---

## 9) Minimal “must‑implement” formulas for your tooling

Because you cannot measure ToA directly via AUX on your HAT module:

- Implement datasheet ToA equations (Section 3) as a **utility** that:
  - Takes (SF, BW[kHz], CR, CRC_on, header_mode, preamble_len, payload_bytes)
  - Outputs **ToA (ms)** and **N_symbol**

This allows you to:
- Quantitatively justify “payload reduction → airtime reduction”
- Normalize PDR/ETX results by channel occupancy
- Build consistent experiment tables across ADR codes (SF/BW/CR presets)

---

## 10) Appendix: quick cross‑reference (datasheet sections)

- **6.1.1** LoRa modulation parameter basics (SF/BW/CR)  
- **6.1.1.4** LDRO guidance (symbol time threshold)  
- **6.1.3.2** Implicit header mode definition (TX/RX must match)  
- **6.1.4** LoRa Time‑on‑Air (ToA) equations  
- **6.1.5** LoRa CAD (what it detects + timing)  
- **14.x** Command interface / packet engine commands (for SPI implementations)  
- **15** Known limitations + workarounds

---

## 11) Action items for your current setup (E22 UART, no AUX)

1. Decide whether you will use **explicit header** (safer for exploration) or **implicit header** (slightly lower ToA, but must lock payload length/CR/CRC).  
2. Implement **datasheet ToA** utility and use it in your PDR‑sweep experiment planner.  
3. Confirm which of the following your E22 firmware exposes and how it maps:
   - SF/BW/CR preset (ADR code / air data rate table)
   - CRC on/off, fixed/variable packet
   - Preamble length
   - TX power dBm
4. When you publish results, include:
   - The exact (SF/BW/CR/LDRO, preamble, header mode, CRC, power) tuple for each ADR code.

