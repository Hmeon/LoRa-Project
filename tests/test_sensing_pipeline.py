import json
from pathlib import Path

import pytest

from loralink_mllc.sensing.dataset import DatasetLogger
from loralink_mllc.sensing.sampler import CsvSensorSampler, JsonlSensorSampler
from loralink_mllc.sensing.schema import (
    SENSOR_ORDER,
    SENSOR_UNITS,
    SensorSample,
    SensorSampleError,
)


def test_sensor_sample_from_flat_dict() -> None:
    data = {
        "ts_ms": 1700000000000,
        "lat": 1.0,
        "lon": 2.0,
        "alt": 3.0,
        "ax": 4.0,
        "ay": 5.0,
        "az": 6.0,
        "gx": 7.0,
        "gy": 8.0,
        "gz": 9.0,
        "roll": 10.0,
        "pitch": 11.0,
        "yaw": 12.0,
    }
    sample = SensorSample.from_dict(data)
    assert sample.vector() == list(range(1, 13))


def test_sensor_sample_from_nested_dict() -> None:
    data = {
        "ts": 1.0,
        "gps": {"lat": 1.0, "lon": 2.0, "altitude": 3.0},
        "accel": {"ax": 4.0, "ay": 5.0, "az": 6.0},
        "gyro": {"gx": 7.0, "gy": 8.0, "gz": 9.0},
        "angle": {"roll": 10.0, "pitch": 11.0, "yaw": 12.0},
    }
    sample = SensorSample.from_dict(data)
    assert sample.vector() == list(range(1, 13))


def test_sensor_sample_missing_fields() -> None:
    with pytest.raises(SensorSampleError):
        SensorSample.from_dict({"ts_ms": 1})


def test_jsonl_sensor_sampler(tmp_path: Path) -> None:
    path = tmp_path / "sensor.jsonl"
    lines = [
        {
            "ts_ms": 1,
            "lat": 1,
            "lon": 2,
            "alt": 3,
            "ax": 4,
            "ay": 5,
            "az": 6,
            "gx": 7,
            "gy": 8,
            "gz": 9,
            "roll": 10,
            "pitch": 11,
            "yaw": 12,
        },
        {
            "ts_ms": 2,
            "lat": 1,
            "lon": 2,
            "alt": 3,
            "ax": 4,
            "ay": 5,
            "az": 6,
            "gx": 7,
            "gy": 8,
            "gz": 9,
            "roll": 10,
            "pitch": 11,
            "yaw": 12,
        },
    ]
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    sampler = JsonlSensorSampler(path, order=SENSOR_ORDER, expected_dims=12)
    assert sampler.sample() == list(range(1, 13))
    assert sampler.sample() == list(range(1, 13))
    with pytest.raises(StopIteration):
        sampler.sample()


def test_csv_sensor_sampler(tmp_path: Path) -> None:
    path = tmp_path / "sensor.csv"
    path.write_text(
        "ts_ms,lat,lon,alt,ax,ay,az,gx,gy,gz,roll,pitch,yaw\n"
        "1,1,2,3,4,5,6,7,8,9,10,11,12\n",
        encoding="utf-8",
    )
    sampler = CsvSensorSampler(path, order=SENSOR_ORDER, expected_dims=12)
    assert sampler.sample() == list(range(1, 13))
    with pytest.raises(StopIteration):
        sampler.sample()


def test_dataset_logger(tmp_path: Path) -> None:
    path = tmp_path / "dataset.jsonl"
    logger = DatasetLogger(path, "run123", SENSOR_ORDER, units=SENSOR_UNITS)
    logger.log_window(0, 1000, [1.0] * 12)
    logger.close()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(lines[0])
    assert payload["run_id"] == "run123"
    assert payload["window_id"] == 0
    assert payload["order"] == list(SENSOR_ORDER)
    assert payload["units"] == SENSOR_UNITS
    assert payload["window"] == [1.0] * 12
