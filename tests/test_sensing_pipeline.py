import json
from pathlib import Path

import pytest

from loralink_mllc.sensing.dataset import DatasetLogger
from loralink_mllc.sensing.sampler import CsvSensorSampler, JsonlSensorSampler, NoSampleAvailable
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


def test_sensor_sample_timestamp_parsing_and_attitude_alias() -> None:
    data = {
        "timestamp": "2025-01-01T00:00:00Z",
        "gps": {"lat": 1.0, "lon": 2.0, "alt": 3.0},
        "accel": {"ax": 4.0, "ay": 5.0, "az": 6.0},
        "gyro": {"gx": 7.0, "gy": 8.0, "gz": 9.0},
        "attitude": {"roll": 10.0, "pitch": 11.0, "yaw": 12.0},
    }
    sample = SensorSample.from_dict(data)
    assert sample.ts_ms > 0
    assert sample.vector() == list(range(1, 13))


def test_sensor_sample_timestamp_naive_assumed_utc() -> None:
    data = {
        "timestamp": "2025-01-01T00:00:00",
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
    assert sample.ts_ms > 0


def test_sensor_sample_invalid_timestamp_and_float_raise() -> None:
    with pytest.raises(SensorSampleError, match="invalid timestamp"):
        SensorSample.from_dict({"timestamp": "not-a-ts"})
    with pytest.raises(SensorSampleError, match="invalid lat value"):
        SensorSample.from_dict(
            {
                "ts_ms": 1,
                "lat": "NaN?",
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
        )


def test_sensor_sample_as_dict_roundtrip() -> None:
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
    assert SensorSample.from_dict(sample.as_dict()) == sample


def test_sensor_sample_missing_fields() -> None:
    with pytest.raises(SensorSampleError):
        SensorSample.from_dict({"ts_ms": 1})


def test_sensor_sample_missing_timestamp_field() -> None:
    with pytest.raises(SensorSampleError, match="missing ts_ms/ts/timestamp"):
        SensorSample.from_dict(
            {
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
        )


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
    sampler = JsonlSensorSampler(path, order=SENSOR_ORDER, expected_dims=12, follow=True)
    sampler.sample()
    sampler.sample()
    with pytest.raises(NoSampleAvailable):
        sampler.sample()
    sampler = JsonlSensorSampler(path, order=SENSOR_ORDER, expected_dims=12, loop=True)
    ts_ms, sample = sampler.sample_with_ts()
    assert ts_ms == 1
    assert sample == list(range(1, 13))


def test_jsonl_sensor_sampler_loop_and_ignores_empty_lines(tmp_path: Path) -> None:
    path = tmp_path / "sensor.jsonl"
    path.write_text(
        "\n\n"
        + json.dumps(
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
            }
        )
        + "\n",
        encoding="utf-8",
    )
    sampler = JsonlSensorSampler(path, loop=True, expected_dims=12)
    assert sampler.sample() == list(range(1, 13))
    assert sampler.sample() == list(range(1, 13))


def test_samplers_validate_order_length(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "sensor.jsonl"
    jsonl_path.write_text(json.dumps({"ts_ms": 1, "lat": 1, "lon": 2, "alt": 3}), encoding="utf-8")
    with pytest.raises(ValueError, match="order length"):
        JsonlSensorSampler(jsonl_path, order=("lat",), expected_dims=12)
    csv_path = tmp_path / "sensor.csv"
    csv_path.write_text("ts_ms,lat\n1,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="order length"):
        CsvSensorSampler(csv_path, order=("lat",), expected_dims=12)


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
    sampler = CsvSensorSampler(path, order=SENSOR_ORDER, expected_dims=12, follow=True)
    sampler.sample()
    with pytest.raises(NoSampleAvailable):
        sampler.sample()
    sampler = CsvSensorSampler(path, order=SENSOR_ORDER, expected_dims=12, loop=True)
    ts_ms, sample = sampler.sample_with_ts()
    assert ts_ms == 1
    assert sample == list(range(1, 13))


def test_csv_sensor_sampler_loop_handles_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("ts_ms,lat,lon,alt,ax,ay,az,gx,gy,gz,roll,pitch,yaw\n", encoding="utf-8")
    sampler = CsvSensorSampler(path, loop=True, expected_dims=12)
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
