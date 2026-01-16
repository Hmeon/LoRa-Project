from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Protocol, Sequence

from loralink_mllc.sensing.schema import SENSOR_ORDER, SensorSample


class SensorSampler(Protocol):
    def sample(self) -> Sequence[float]:
        ...


def _validate_order(order: Sequence[str], expected_dims: int | None) -> None:
    if expected_dims is not None and len(order) != expected_dims:
        raise ValueError(f"sensor order length {len(order)} does not match dims {expected_dims}")


class JsonlSensorSampler:
    def __init__(
        self,
        path: str | Path,
        order: Sequence[str] | None = None,
        loop: bool = False,
        expected_dims: int | None = None,
    ) -> None:
        self._path = Path(path)
        self._order = tuple(order or SENSOR_ORDER)
        self._loop = loop
        _validate_order(self._order, expected_dims)
        self._fh = self._path.open("r", encoding="utf-8")

    def sample(self) -> Sequence[float]:
        while True:
            line = self._fh.readline()
            if not line:
                if not self._loop:
                    raise StopIteration
                self._fh.seek(0)
                continue
            stripped = line.strip()
            if not stripped:
                continue
            data = json.loads(stripped)
            sample = SensorSample.from_dict(data)
            return sample.vector(self._order)


class CsvSensorSampler:
    def __init__(
        self,
        path: str | Path,
        order: Sequence[str] | None = None,
        loop: bool = False,
        expected_dims: int | None = None,
    ) -> None:
        self._path = Path(path)
        self._order = tuple(order or SENSOR_ORDER)
        self._loop = loop
        _validate_order(self._order, expected_dims)
        self._fh = self._path.open("r", encoding="utf-8", newline="")
        self._reader = csv.DictReader(self._fh)

    def _next_row(self) -> dict[str, str]:
        row = next(self._reader, None)
        if row is None:
            if not self._loop:
                raise StopIteration
            self._fh.seek(0)
            self._reader = csv.DictReader(self._fh)
            row = next(self._reader, None)
            if row is None:
                raise StopIteration
        return row

    def sample(self) -> Sequence[float]:
        row = self._next_row()
        sample = SensorSample.from_dict(row)
        return sample.vector(self._order)
