# Sensing Pipeline (Field Data)

This document defines how real sensor data is ingested into the TX runtime.
It intentionally avoids vendor-specific drivers and expects a JSONL/CSV feed.

## Required sensor vector (12D)
Order must be fixed and consistent with RunSpec `window.dims=12`:
```
[lat, lon, alt, ax, ay, az, gx, gy, gz, roll, pitch, yaw]
```

Units are fixed and must be recorded for reproducibility:
- lat, lon: degrees
- alt: meters
- accel: m/s^2
- gyro: deg/s
- roll, pitch, yaw: degrees

If your sensor outputs radians or g, convert to the fixed units before logging.

## On-air payload (binary, not JSON)
This repo does **not** transmit JSON over LoRa. The runtime reads JSONL/CSV, builds a float window,
then encodes it into `Packet.payload` bytes with the selected codec.

Baseline RAW codec: `sensor12_packed` (v1)
- 30 bytes per step (little-endian). A window with `W` steps uses `30 * W` bytes.
- gps: float32 x3 (lat, lon, alt)
- accel: int16 x3 scaled by 1000
- gyro: int16 x3 scaled by 10
- rpy: int16 x3 scaled by 10

## JSONL input schema (preferred)
Each line is a JSON object with required fields.
```
{
  "ts_ms": 1700000000000,
  "lat": 37.123456,
  "lon": 127.123456,
  "alt": 31.2,
  "ax": 0.01,
  "ay": -0.03,
  "az": 9.79,
  "gx": -0.5,
  "gy": 1.2,
  "gz": 0.0,
  "roll": 0.1,
  "pitch": -0.2,
  "yaw": 0.0
}
```
Example file: `configs/examples/sensor_sample.jsonl`

Supported timestamp keys:
- `ts_ms` (milliseconds)
- `ts` (seconds; will be converted)
- `timestamp` (ISO 8601; will be converted)

## Nested JSON compatibility (optional)
If your producer emits nested fields, these are mapped automatically:
- `gps`: `{lat, lon, alt}` or `{lat, lon, altitude}`
- `accel`: `{ax, ay, az}`
- `gyro`: `{gx, gy, gz}`
- `attitude` or `angle`: `{roll, pitch, yaw}`

## CSV input schema
CSV must include these headers:
```
ts_ms,lat,lon,alt,ax,ay,az,gx,gy,gz,roll,pitch,yaw
```
Example file: `configs/examples/sensor_sample.csv`

## Capture from serial (optional)
If a microcontroller emits newline-delimited JSON, capture it to JSONL:
```bash
python scripts/capture_serial_jsonl.py --port COM3 --baud 115200 --out out/sensor.jsonl
```
This script requires `pyserial` and adds `ts_ms` if missing.

## TX runtime usage
Use the JSONL or CSV sampler to drive the TX node:
```bash
python -m loralink_mllc.cli tx \
  --runspec configs/examples/tx_raw.yaml \
  --manifest configs/examples/artifacts_sensor12_packed.json \
  --sampler jsonl \
  --sensor-path out/sensor.jsonl \
  --dataset-out out/dataset_raw.jsonl \
  --radio mock
```

## Dataset output
`--dataset-out` writes the raw window (`x_true`) per window:
```
{
  "ts_ms": 1700000000000,
  "run_id": "example_raw",
  "window_id": 0,
  "order": ["lat", "lon", "alt", "ax", "ay", "az", "gx", "gy", "gz", "roll", "pitch", "yaw"],
  "units": {
    "lat": "deg",
    "lon": "deg",
    "alt": "m",
    "ax": "m/s^2",
    "ay": "m/s^2",
    "az": "m/s^2",
    "gx": "deg/s",
    "gy": "deg/s",
    "gz": "deg/s",
    "roll": "deg",
    "pitch": "deg",
    "yaw": "deg"
  },
  "window": [ ... 12 * W values ... ]
}
```

This dataset is the input for BAM training and reconstruction evaluation.
