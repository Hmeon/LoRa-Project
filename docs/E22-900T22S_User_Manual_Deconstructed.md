# E22-900T22S (SX1262) User Manual — Deconstructed (Markdown)

> Source: **E22-900T22S User Manual** (Chengdu Ebyte Electronic Technology Co., Ltd., rev. 1.30, 2018-10-23).  
> This Markdown reorganizes the PDF into an engineering-friendly format (pinning, modes, registers, and practical design notes).

---

## Table of Contents

1. [Overview](#1-overview)  
2. [Specifications & Parameters](#2-specifications--parameters)  
3. [Mechanical Size & Pin Definition](#3-mechanical-size--pin-definition)  
4. [MCU Connection Notes](#4-mcu-connection-notes)  
5. [Functional Behavior](#5-functional-behavior)  
6. [Operating Modes (M0/M1)](#6-operating-modes-m0m1)  
7. [Register Read/Write Control](#7-register-readwrite-control)  
8. [Register Map (00h–08h, 80h–86h)](#8-register-map-00h08h-80h86h)  
9. [Factory Defaults](#9-factory-defaults)  
10. [Repeater Networking Mode](#10-repeater-networking-mode)  
11. [PC Configuration Notes](#11-pc-configuration-notes)  
12. [Hardware Design Guidelines](#12-hardware-design-guidelines)  
13. [FAQ / Troubleshooting](#13-faq--troubleshooting)  
14. [Production Guidance (Reflow)](#14-production-guidance-reflow)  
15. [E22 Series Reference](#15-e22-series-reference)  
16. [Antenna Recommendations](#16-antenna-recommendations)  
17. [Revision History & Vendor Info](#17-revision-history--vendor-info)

---

## 1. Overview

### 1.1 Introduction

**E22-900T22S** is a UART wireless serial module based on **Semtech SX1262** (LoRa) operating in **850.125–930.125 MHz** (default **900.125 MHz**).  
It uses **LoRa spread spectrum** to achieve long-range links with strong anti-interference characteristics and supports TTL-level UART, compatible with 3.3V and 5V IO voltage domains (with cautions).  

Key points from the manual:
- **Software FEC** improves reliability in burst interference by correcting corrupted packets (otherwise packets would be discarded).
- **Data encryption** reduces meaningful interception over-air.
- Multiple IO interfaces reserved for custom integrations.
- Supports **packet length setting** and both real-time / packetized data handling.

### 1.2 Features (high level)

- Range tested up to **7 km** (open area conditions).
- Max TX power **160 mW** (≈22 dBm), software adjustable.
- Works in global license-free ISM 868/915 MHz bands (module covers 850.125–930.125 MHz).
- Air data rate **0.3 kbps – 62.5 kbps**.
- Industrial temperature **-40°C to +85°C**.
- Optional antenna interfaces: **IPEX** or stamp-hole.
- Lower power consumption vs. SX1276 (manual claims improvements).

### 1.3 Applications

Typical applications called out:
- Home security / remote keyless entry
- Smart home & industrial sensors
- Wireless alarm systems
- Building automation
- Industrial remote control
- Health care products
- AMI metering
- Automotive applications

### 1.4 Functional Concepts

- **LoRa spread spectrum**: long range, low spectral density.
- **High confidentiality / anti-interference**: strong co-channel suppression, good multipath resistance.
- **LBT (Listen Before Talk)**: checks channel noise before TX; if noise exceeds threshold, delays TX.
- **RSSI reporting**:
  - Packet RSSI serial output (link quality / network tuning / ranging)
  - Ambient noise RSSI serial output (manual LBT / diagnostics)
- **Wireless configuration**: configure/read parameters over-air via command packets.
- **Networking / multi-level repeater**: suitable for ultra-long distance and multiple networks in same area.
- **Ultra-low power / WOR (Wake-On-Radio)**:
  - WOR monitoring with configurable response delay up to 4000 ms
  - average current in WOR mode mentioned ~2 µA (concept description)
- **Fixed-point transmission**: send to a specific address+channel (useful for networking/repeater).
- **Broadcast / monitor**: address set to 0xFFFF or 0x0000 enables broadcast/monitor behavior.
- **FEC**, **Deep sleep**, **Watchdog**, **Parameter saving**.

---

## 2. Specifications & Parameters

### 2.1 Absolute Limit Parameters

| Parameter | Min | Max | Remark |
|---|---:|---:|---|
| Power supply (V) | 0 | 5.5 | Voltage over 5.5 V may permanently damage module |
| Blocking power (dBm) | — | 10 | Burn chance slim when used short distance |
| Operating temperature (°C) | -40 | 85 | — |

### 2.2 Operating Parameters

| Parameter | Min | Typ | Max | Remark |
|---|---:|---:|---:|---|
| Operating voltage (V) | 2.3 | 5.0 | 5.5 | ≥5.0 V ensures best output power |
| Communication level (V) | — | 3.3 | — | 5V TTL may risk burning |
| Operating temperature (°C) | -40 | — | 85 | Industrial design |
| Operating frequency (MHz) | 850.125 | — | 930.125 | ISM band coverage |
| TX current (mA) | — | 133 | — | Instant consumption |
| RX current (mA) | — | 11 | — | — |
| Sleep current (µA) | — | 469 | — | “Software shut down” |
| Max TX power (dBm) | 21.5 | 22.0 | 22.5 | 160 mW class |
| RX sensitivity (dBm) | -146 | -147 | -148 | at air data rate 2.4 kbps |
| Air data rate | 0.3k | 2.4k | 62.5k | configurable |

### 2.3 Additional Key Parameters

| Item | Value | Notes |
|---|---|---|
| Reference range | 7000 m | clear/open, 5 dBi antenna, 2.5 m height, 2.4 kbps |
| TX length per packet | 240 bytes | configurable: 32/64/128/240 |
| Buffer | 1000 bytes | internal UART buffer |
| Modulation | LoRa | — |
| Interface | UART @ 3.3V | TTL UART |
| Package | SMD | — |
| Connector pitch | 1.27 mm | — |
| Module size | 16 × 26 mm | — |
| Antenna | IPEX / stamp hole | 50 Ω |

---

## 3. Mechanical Size & Pin Definition

### 3.1 Mechanical

- Module size: **16.0 × 26.0 mm**
- Pad count: **22**
- Antenna: IPEX footprint shown on the module drawing (optional variant)

*(The PDF contains detailed dimension drawings; this Markdown preserves functional aspects rather than reproducing mechanical drawings.)*

### 3.2 Pin Table (22 pads)

> Note: M0/M1 have weak pull-ups; “not suspended” if unused → can be tied to GND per manual.

| No. | Name | Dir | Function |
|---:|---|---|---|
| 1 | GND | — | Ground |
| 2 | GND | — | Ground |
| 3 | GND | — | Ground |
| 4 | GND | — | Ground |
| 5 | M0 | In (weak PU) | Works with M1 to select operating mode (if unused, can tie to GND) |
| 6 | M1 | In (weak PU) | Works with M0 to select operating mode (if unused, can tie to GND) |
| 7 | RXD | In | UART RX (connect to MCU/PC TXD). Input can be open-drain or pull-up |
| 8 | TXD | Out | UART TX (connect to MCU/PC RXD). Output can be open-drain or push-pull |
| 9 | AUX | Out | Status indication & MCU wake. Low during self-check init; configurable push-pull (suspend allowed) |
| 10 | VCC | Pwr | Power supply **2.3–5.2 V DC** (note overall limit up to 5.5 V) |
| 11 | GND | — | Ground |
| 12 | NC | — | No connect |
| 13 | GND | — | Ground |
| 14 | NC | — | No connect |
| 15 | NC | — | No connect |
| 16 | NC | — | No connect |
| 17 | NC | — | No connect |
| 18 | NC | — | No connect |
| 19 | GND | — | Ground |
| 20 | GND | — | Ground |
| 21 | ANT | — | Antenna |
| 22 | GND | — | Ground |

---

## 4. MCU Connection Notes

The manual highlights:
1. UART is **TTL level**.
2. If MCU runs at **5V**, may need **4–10 kΩ pull-up** resistor for **TXD & AUX** pins (for some MCU families).  

**Practical note**: Even though the module is described as compatible with 3.3V and 5V IO domains, the manual explicitly warns that **5V TTL may be at risk of burning down**. Design conservatively: prefer **3.3V UART** or level-shifting.

---

## 5. Functional Behavior

### 5.1 Fixed Transmission (Addressed / “Fixed-point”)

Fixed-point transmission allows the sender to specify:
- **Destination ADDH, ADDL**
- **Destination Channel**
- Then payload bytes follow.

Example concept (from manual):
- If module B has address `0x0001` and channel `0x80`
- Sender module A sends payload `AA BB CC`
- The air packet’s UART input format is:

```
00 01 80 AA BB CC
```

Only module B receives `AA BB CC` (others ignore).

### 5.2 Broadcasting Transmission

Broadcast is achieved by setting the sender’s target address to **0xFFFF** or **0x0000** (manual lists both) and sending on a channel. All modules on that channel receive the data.

### 5.3 Broadcasting Address / 5.4 Monitor Address

- Address set to **0xFFFF** or **0x0000** can act as broadcast/monitor address:
  - Broadcast: transmitter sends and all modules on channel receive.
  - Monitor: receiver listens to all traffic on channel.

### 5.5 Reset / Power-on Behavior

On power-up:
- **AUX goes low immediately**, module performs self-check init and sets mode based on parameters.
- AUX stays low during this process.
- After completion, **AUX goes high** and module begins operation per M0/M1 mode.
- Recommendation: wait for **AUX rising edge** as start of normal work.

### 5.6 AUX Behavior (Busy / Buffer / Wake signaling)

AUX indicates:
- self-check initialization status
- UART/RF buffering state

#### 5.6.1 UART output indication
- AUX can be used to **wake external MCU** slightly in advance before TXD output.

#### 5.6.2 Wireless transmitting indication (1000-byte buffer)
- **Buffer empty / AUX=1**: internal 1000B buffer has been written to RFIC; user may input <1000 bytes continuously without overflow.
- **Buffer not empty / AUX=0**: buffer not fully written to RFIC; sending more data may cause overtime/wait conditions.

Important nuance from manual:
- AUX=1 does **not necessarily** mean the last over-air packet is fully transmitted; last packet may still be in transmission.

#### 5.6.3 Configuration procedure
- Happens when power-on reset or exiting sleep mode.

#### 5.6.4 AUX notes
- Low output has priority: if any “busy” condition applies, AUX low.
- When AUX low: module busy; mode checking not possible.
- Mode switch completes within 1 ms after AUX goes high, but recommended to allow **2 ms high** for stable effect.
- Switching from sleep/reset triggers parameter reconfiguration; AUX low during this time.

---

## 6. Operating Modes (M0/M1)

Four modes selected by M1/M0:

| Mode | M1 | M0 | Name | Description |
|---:|---:|---:|---|---|
| 0 | 0 | 0 | Normal | UART ↔ RF transparent transmission; supports over-air configuration via special command |
| 1 | 0 | 1 | WOR | Can define transmitter/receiver; supports wake-up over air |
| 2 | 1 | 0 | Configuration | Register access via UART; RF TX/RX off |
| 3 | 1 | 1 | Deep sleep | Sleep mode |

### 6.1 Mode switching notes

- Mode switching is determined by M1/M0 GPIO levels (MCU controlled).
- After changing M1/M0:
  - If module idle: ~1 ms to start new mode.
  - If pending TX/RX activities: switching delayed until completion.
- General recommendation: check AUX state and switch **after ~2 ms when AUX high**.
- “Fast switching” behavior described:
  - If switching to sleep while data pending, module can finish TX then enter sleep automatically within ~1 ms (MCU can sleep earlier).
  - Similar pattern can apply to other switches: module enters new mode after processing current events; user can sleep and use AUX interrupt.

### 6.2 Normal mode (Mode 0)

- **TX**: user writes data to UART; module transmits wirelessly.
- **RX**: module receives wireless data and outputs via TXD UART.

### 6.3 WOR mode (Mode 1)

- TX party: module adds preamble automatically.
- RX party: receives similarly to Mode 0, but with WOR monitoring behavior (configured in REG3).

### 6.4 Configuration mode (Mode 2)

- RF TX: off  
- RF RX: off  
- Configure: access registers via UART.

> Manual states **only 9600, 8N1** is supported when issuing configuration commands.

### 6.5 Deep sleep (Mode 3)

- Cannot transmit/receive RF.
- When leaving sleep to other modes: module reconfigures parameters; AUX low during configuration, then high. Suggest testing the “rising edge busy time” (T_BUSY).

---

## 7. Register Read/Write Control

> Commands are used in **Configuration Mode (Mode 2: M1=1, M0=0)**.  
> Manual notes: **Only 9600, 8N1** is supported while issuing these commands.

### 7.1 Command formats

| No. | Command | Format | Response | Notes |
|---:|---|---|---|---|
| 1 | Set register | `C0 + startAddr + length + parameters` | `C1 + startAddr + length + parameters` | saved to non-volatile |
| 2 | Read register | `C1 + startAddr + length` | `C1 + startAddr + length + parameters` | — |
| 3 | Set temporary register | `C2 + startAddr + length + parameters` | `C1 + startAddr + length + parameters` | not permanent |
| 5 | Wireless configuration | `CF CF + normal command` | `CF CF + normal response` | configure over-air |
| 6 | Wrong format | — | `FF FF FF` | error response |

Examples (from manual):
- Set channel to 0x09: `C0 05 01 09` → `C1 05 01 09`
- Read channel: `C1 05 01` → `C1 05 01 09`
- Configure address/network/uart/airrate: `C0 00 04 12 34 00 61` → `C1 00 04 12 34 00 61`
- Over-air equivalent: `CF CF C0 05 01 09` → `CF CF C1 05 01 09`

---

## 8. Register Map (00h–08h, 80h–86h)

### 8.1 00h / 01h — Address High/Low (ADDH/ADDL)

- **ADDH (00h)**: high byte of module address (default 0)
- **ADDL (01h)**: low byte of module address (default 0)
- If address is **0xFFFF**, it can be used as **broadcast/monitor address** (disables address filtering).

### 8.2 02h — NETID

- Network ID (default 0)
- Used to distinguish networks; communicating nodes must share same NETID.

### 8.3 03h — REG0 (UART baud, parity, air data rate)

Bit fields:

- Bits **7..5**: UART baud rate  
  - 000: 1200  
  - 001: 2400  
  - 010: 4800  
  - 011: 9600 (default)  
  - 100: 19200  
  - 101: 38400  
  - 110: 57600  
  - 111: 115200  

- Bits **4..3**: parity  
  - 00: 8N1 (default)  
  - 01: 8O1  
  - 10: 8E1  
  - 11: 8N1 (equal to 00)  

- Bits **2..0**: air data rate  
  - 000: 0.3k  
  - 001: 1.2k  
  - 010: 2.4k (default)  
  - 011: 4.8k  
  - 100: 9.6k  
  - 101: 19.2k  
  - 110: 38.4k  
  - 111: 62.5k  

Notes:
- UART baud/parity can differ between two communicating modules; however, for large packets continuous transfer, same baud recommended to avoid blocking/loss.
- Air data rate must match on both ends; higher air rate reduces distance.

### 8.4 04h — REG1 (sub-packet, ambient RSSI, TX power)

- Bits **7..6**: sub-packet length  
  - 00: 240 bytes (default)  
  - 01: 128 bytes  
  - 10: 64 bytes  
  - 11: 32 bytes  

  Behavior:
  - If data < sub-packet length, receiver UART output is continuous.
  - If data > sub-packet length, receiver UART outputs as sub-packets.

- Bit **5**: RSSI ambient noise enable  
  - 1: enable  
  - 0: disable (default)  

  When enabled, supports reading RSSI registers via a special command in transmitting/WOR transmitting mode:
  - Register 0x00: current ambient noise RSSI
  - Register 0x01: RSSI when last packet received
  - Noise conversion: `dBm = -RSSI / 2` (as stated in manual)

  Command format (per manual remark):  
  `C0 C1 C2 C3 + startAddr + readLength` → returns `C1 + startAddr + readLength + value`

- Bits **1..0**: transmitting power  
  - 00: 22 dBm (default)  
  - 01: 17 dBm  
  - 10: 13 dBm  
  - 11: 10 dBm  

  Note: Power/current is non-linear; efficiency highest at max power; current doesn’t scale linearly down.

### 8.5 05h — REG2 (Channel)

- 0–80 → total 81 channels
- Frequency formula:

```
Frequency (MHz) = 850.125 + CH * 1
```

### 8.6 06h — REG3 (RSSI packet output, fixed-point, repeater reply, LBT, WOR control)

Bit fields:

- Bit **7**: Enable RSSI (packet RSSI appended to UART output)
  - 1: enable
  - 0: disable (default)
  - When enabled, module outputs an RSSI strength byte after received wireless data via TXD.

- Bit **6**: Fixed point transmission
  - 1: fixed point mode
  - 0: transparent (default)
  - In fixed-point mode, first three UART bytes are interpreted as: **ADDH + ADDL + Channel** target.

- Bit **5**: Enable reply (repeater function)
  - 1: enable repeater/forward once if target address isn’t itself
  - 0: disable
  - Manual recommends using with fixed-point mode to prevent return-back loops (ensure target address differs from source).

- Bit **4**: LBT enable (monitor before transmission)
  - 1: enable
  - 0: disable (default)
  - May reduce collisions/interference but can introduce delay.

- Bit **3**: WOR transceiver control (Mode 1 only)
  - 1: WOR transmitter (RX/TX on; adds wake-up code before TX; RX on)
  - 0: WOR receiver (default): cannot transmit; monitors periodically to save power
  - After WOR receiver gets data and outputs via UART, waits **1000 ms** before re-entering WOR; user can send reply during this window (first byte must be within 1000 ms, each byte refreshes the 1000 ms timer).

- Bits **2..0**: WOR cycle
  - 000: 500 ms
  - 001: 1000 ms
  - 010: 1500 ms
  - 011: 2000 ms (default)
  - 100: 2500 ms
  - 101: 3000 ms
  - 110: 3500 ms
  - 111: 4000 ms

  Period formula: `T = (1 + WOR) * 500 ms` (min 500 ms, max 4000 ms).  
  Note: Both TX and RX must be the same WOR cycle (manual emphasizes “very important”). Longer cycle reduces average power but increases data latency.

### 8.7 07h / 08h — Encryption key (CRYPT_H / CRYPT_L)

- Write-only. Read returns 0.
- Default 0.
- Two bytes are used as a factor for internal encryption/obfuscation of over-air signal.

### 8.8 80h–86h — Product information (PID)

- Read-only 7 bytes.

---

## 9. Factory Defaults

Manual states “Factory default parameters: **62 00 00 00 00 00**”.

Defaults:
- Model: E22-900T22S
- Frequency: **900.125 MHz**
- Address: **0x0000**
- Channel: **0x32**
- Air data rate: **2.4 kbps**
- UART: **9600**, **8N1**
- Power: **22 dBm**

---

## 10. Repeater Networking Mode

Key points:
1. Configure repeater mode, then switch to **Normal mode** to start repeater operation.
2. In repeater mode, **ADDH/ADDL are no longer used as module address**; instead they form a pairing with NETID to forward between two networks.
3. Repeater mode **cannot** do normal TX/RX like a node, and **cannot** perform low-power operation.
4. Repeater forwarding rules:
   - Can forward in both directions between two NETIDs.
   - In repeater mode, ADDH/ADDL act as **NETID forwarding pairing flag**.

Conceptual example described:
- Node1 NETID=08, Node2 NETID=33.
- Primary repeater has ADDH/ADDL = 08,33, so traffic from NETID 08 can be forwarded to NETID 33.
- Secondary repeater might chain: ADDH/ADDL = 33,05 to forward to NETID 05.

---

## 11. PC Configuration Notes

Manual notes that PC configuration UI uses **decimal** inputs:
- Network address: 0–65535
- Frequency channel: 0–80
- Network ID: 0–255
- Key: 0–65535

Repeater configuration caveat:
- Because PC UI uses decimal, when setting “module address” for repeater you may need to:
  - convert desired hex pairing (NETIDs) into a 16-bit value (ADDH/ADDL),
  - then input its decimal representation.

Example from manual:
- Transmitter NETID = 02, receiver NETID = 10  
- Repeater “module address” = 0x020A (hex) = **522** (decimal)  
  → set repeater module address to 522 in PC UI.

---

## 12. Hardware Design Guidelines

Manual recommendations (layout/power/EMI/antenna):

### 12.1 Power

- Prefer **DC stabilized** supply with minimal ripple; ensure reliable grounding.
- Avoid reverse polarity; can permanently damage module.
- Keep voltage within recommended range; exceeding maximum can permanently damage.
- Avoid frequent supply fluctuations.
- Reserve **>30% margin** in power design for long-term stability.

### 12.2 Layout / EMI

- Keep module away from supply/transformers/high-frequency wiring and strong EMI sources.
- Avoid routing:
  - high-frequency digital traces
  - high-frequency analog traces
  - power traces
  under the module.
- If routing must pass beneath:
  - assume module on Top layer; flood copper on Top under module and ground it well,
  - route beneath on Bottom layer close to the module’s digital section.
- Random routing on other layers beneath module can degrade spurious emissions and RX sensitivity.
- If strong EMI sources are nearby, increase distance; consider shielding/isolation if needed.

### 12.3 IO level cautions

- If using a 5V-level communication line, manual states a **1k–5.1k series resistor must be connected** (still not recommended; damage risk remains).
- Stay away from physical-layer sources like 2.4 GHz TTL protocol (example: USB 3.0) due to potential interference.

### 12.4 Antenna placement

- Antenna placement strongly affects performance:
  - ensure antenna is exposed, ideally vertical.
  - if module inside enclosure, use quality extension cable to bring antenna outside.
  - do not place antenna inside metal case; range will be greatly weakened.

---

## 13. FAQ / Troubleshooting

### 13.1 Range is too short

Possible causes:
- Obstacles between nodes.
- Temperature/humidity/co-channel interference increasing loss.
- Testing near ground (ground absorbs/reflects RF).
- Sea water absorption near ocean.
- Antenna near metal or inside metal case.
- Incorrect power setting, too high air data rate (higher rate → shorter distance).
- Supply voltage below ~2.5 V reduces TX power.
- Poor antenna quality / matching.

### 13.2 Module is easy to damage

Manual notes:
- Check supply range and stability (note the FAQ section contains a voltage range statement that differs from the earlier spec table—follow the stricter limits and the absolute max 5.5 V from the electrical spec).
- Ensure anti-static precautions; RF devices can be ESD-sensitive.
- Keep humidity within limits.
- Avoid extreme temperatures.

### 13.3 BER (Bit Error Rate) is high

- Co-channel interference: change channel/frequency or move away from interference sources.
- Poor power supply causing “messy code”: ensure reliable supply.
- Poor/too-long extension line or feeder.

---

## 14. Production Guidance (Reflow)

### 14.1 Reflow soldering temperature profile (table)

| Feature | Sn-Pb Assembly | Pb-Free Assembly |
|---|---:|---:|
| Solder paste | Sn63/Pb37 | Sn96.5/Ag3/Cu0.5 |
| Tsmin (preheat min) | 100°C | 150°C |
| Tsmax (preheat max) | 150°C | 200°C |
| Preheat time (Tsmin→Tsmax) | 60–120 s | 60–120 s |
| Ramp-up rate (Tsmax→Tp) | 3°C/s max | 3°C/s max |
| TL (liquidous) | 183°C | 217°C |
| tL (above TL) | 60–90 s | 30–90 s |
| Tp (peak) | 220–235°C | 230–250°C |
| Ramp-down rate (Tp→Tsmax) | 6°C/s max | 6°C/s max |
| Time 25°C→peak | max 6 min | max 8 min |

### 14.2 Reflow curve

The manual includes a reference reflow curve diagram (preheat → ramp-up → peak → ramp-down).

---

## 15. E22 Series Reference

| Model | Core IC | Frequency | Tx Power (dBm) | Distance (km) | Package | Size (mm) | Interface |
|---|---|---|---:|---:|---|---|---|
| E22-900T22S | SX1262 | 868/915M | 22 | 7 | SMD | 16×26 | UART |
| E22-230T22S | SX1262 | 230M | 22 | 7 | SMD | 16×26 | UART |
| E22-400T22S | SX1268 | 430/470M | 22 | 7 | SMD | 16×26 | UART |
| E22-400M30S | SX1268 | 433/470M | 30 | 12 | SMD | 24×38.5 | SPI |
| E22-900M30S | SX1262 | 868/915M | 30 | 12 | SMD | 24×38.5 | SPI |
| E22-900M22S | SX1262 | 868/915M | 22 | 6.5 | SMD | 14×20 | SPI |
| E22-400M22S | SX1268 | 433/470M | 22 | 6.5 | SMD | 14×20 | SPI |
| E22-230T30S | SX1262 | 230M | 30 | 10 | SMD | 40.5×25 | UART |
| E22-400T30S | SX1268 | 430/470M | 30 | 10 | SMD | 40.5×25 | UART |
| E22-900T30S | SX1262 | 868/915M | 30 | 10 | SMD | 40.5×25 | UART |

---

## 16. Antenna Recommendations

The manual lists example antennas:

| Model | Type | Frequency | Interface | Gain (dBi) | Height | Cable | Feature |
|---|---|---|---|---:|---|---|---|
| TX868-XP-100 | Sucker antenna | 868M | SMA-J | 3.5 | 29 cm | 100 cm | High gain |
| TX868-JK-20 | Rubber antenna | 868M | SMA-J | 3 | 200 mm | — | Flexible, omni |
| TX868-JZ-5 | Rubber antenna | 868M | SMA-J | 2 | 50 mm | — | Short straight, omni |
| TX915-XP-100 | Sucker antenna | 915M | SMA-J | 3.5 | 25 cm | 100 cm | High gain |
| TX915-JK-20 | Rubber antenna | 915M | SMA-J | 3 | 210 mm | — | Flexible, omni |
| TX915-JK-11 | Rubber antenna | 915M | SMA-J | 2.5 | 110 mm | — | Flexible, omni |
| TX915-JZ-5 | Rubber antenna | 915M | SMA-J | 2 | 50 mm | — | Short straight, omni |

> Note: Your module variant may expose IPEX or stamp-hole. Use a proper 50 Ω RF path and matching connector/pigtail.

---

## 17. Revision History & Vendor Info

### Revision History (from manual)

- 1.00 — 2018-01-08 — Initial version
- 1.10 — 2018-04-16 — Content updated
- 1.20 — 2018-05-24 — Content updated
- 1.21 — 2018-07-20 — Model name revised
- 1.30 — 2018-10-23 — Model No. split

### Vendor / Support

- Technical support: support@cdebyte.com  
- Website: www.ebyte.com  
- Contact: info@cdebyte.com  

---

## Appendix A — “Do not miss” checklist (implementation)

- **Wait for AUX rising edge** after power-up before assuming module is ready.
- **Prefer 3.3V UART**; treat 5V TTL as risk unless level shifting is used.
- Keep channel consistent: `f = 850.125 + CH MHz`.
- For WOR: **TX/RX must match WOR cycle**.
- For addressed networks: ensure **NETID matches** among nodes.
- For repeaters: remember **ADDH/ADDL repurposed** as NETID pairing.
- For long range: lower air data rate, good antenna placement, stable supply, and EMI-aware PCB routing.
