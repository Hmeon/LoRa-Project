# Metrics Definition

This project measures both **link behavior** and **information preservation**. All computations should be reproducible from logs.

## Link metrics
- **PDR (Packet Delivery Ratio)**
  - `PDR = rx_ok / tx_sent` for data frames
- **ETX (Expected Transmission Count)**
  - `ETX = total_tx_attempts / acked_packets`
  - ACK payload is exactly 1 byte `ACK_SEQ` (echoed uplink `SEQ`)

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
- All metrics must reference the same `run_id` and `phy_profile_id`.
- Report both absolute values and relative deltas against baseline.
