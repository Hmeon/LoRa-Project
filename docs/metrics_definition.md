# Metrics Definition

This project measures both **link behavior** and **information preservation**. All computations should be reproducible from logs.

## Link metrics
- **PDR (Packet Delivery Ratio)**
  - If TX and RX logs are both available: `PDR = rx_ok / tx_sent`
  - If only TX logs are available and ACK is enabled: `PDR = ack_received / tx_sent` (proxy)
- **ETX (Expected Transmission Count)**
  - `ETX = total_tx_attempts / acked_packets`
  - ACK payload is exactly 1 byte `ACK_SEQ` (echoed uplink `SEQ`)

Notes:
- In this repo's metrics output, `acked_count` is the number of `ack_received` events (not unique
  `ack_seq` values) so it remains correct even when 1-byte `SEQ` wraps.
- `unique_windows_sent`, `delivered_windows`, and `delivery_ratio` are window-level fields derived
  from `window_id` in TX logs.

## Latency and signal metrics (TBD)
- **Latency**
  - `rtt_ms` is logged on `ack_received` and can be used as a proxy for ACK round-trip time.
  - `queue_ms` and `e2e_ms` may be logged on `ack_received`:
    - `queue_ms`: window-ready -> first TX send delay (local, monotonic)
    - `e2e_ms`: window-ready -> ACK received (local, monotonic; includes retransmissions)
  - Cross-device end-to-end latency (TX->RX application) still requires synchronized clocks and a defined start/end event (TODO).
- **RSSI/SNR**
  - If the module is configured to append an RSSI byte after each received UART frame (REG3 bit 7),
    run TX/RX with `--uart-rssi-byte`. The runtime logs `rssi_dbm` (computed as `rssi_byte - 256`)
    on `rx_ok` and `ack_received` when available.
  - SNR capture is not implemented (TODO).

## Energy metrics
Choose at least one and record the measurement method:
- Average power over fixed duration
- Energy per successfully delivered window
- Energy per packet attempt

## Reconstruction metrics
- **MAE** per window and per sensor group (GPS/Acc/Gyro/RPY)
- **MSE** per window and per sensor group
- Aggregation rules must be recorded in the metrics report

## Reporting rules
- All metrics must reference the same `run_id` and `phy_id`.
- Report both absolute values and relative deltas against baseline.

## Tooling note
`python -m loralink_mllc.cli metrics` outputs summary stats when fields are present:
- `ack_rtt_ms` from `ack_received.rtt_ms`
- `queue_ms` from `ack_received.queue_ms`
- `e2e_ms` from `ack_received.e2e_ms`
- `rssi_dbm` from `rx_ok.rssi_dbm` and/or `ack_received.rssi_dbm`
- `codec_encode_ms` from `tx_sent.codec_encode_ms` (host CPU cost proxy)
- `tx_age_ms` from `tx_sent.age_ms` and `frame_bytes` from `tx_sent.frame_bytes`
