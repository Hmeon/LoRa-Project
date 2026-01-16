from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence


class DatasetLogger:
    def __init__(
        self,
        path: str | Path,
        run_id: str,
        order: Sequence[str],
        units: Mapping[str, str] | None = None,
    ) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._path.open("a", encoding="utf-8")
        self._run_id = run_id
        self._order = list(order)
        self._units = dict(units) if units else {}

    def log_window(self, window_id: int, ts_ms: int, window: Sequence[float]) -> None:
        payload: dict[str, Any] = {
            "ts_ms": ts_ms,
            "run_id": self._run_id,
            "window_id": window_id,
            "order": self._order,
            "units": self._units,
            "window": [float(value) for value in window],
        }
        self._fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()
