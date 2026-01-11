from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from loralink_mllc.config.artifacts import ArtifactsManifest
from loralink_mllc.config.runspec import RunSpec
from loralink_mllc.runtime.scheduler import Clock, RealClock


class JsonlLogger:
    def __init__(
        self,
        out_dir: str | Path,
        run_id: str,
        role: str,
        mode: str,
        phy_profile_id: str,
        clock: Clock | None = None,
    ) -> None:
        self._dir = Path(out_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{run_id}_{role}.jsonl"
        self._clock = clock or RealClock()
        self._run_id = run_id
        self._role = role
        self._mode = mode
        self._phy_profile_id = phy_profile_id
        self._fh = self._path.open("a", encoding="utf-8")

    def _base_event(self, event: str) -> Dict[str, Any]:
        return {
            "ts_ms": self._clock.now_ms(),
            "run_id": self._run_id,
            "event": event,
            "role": self._role,
            "mode": self._mode,
            "phy_profile_id": self._phy_profile_id,
        }

    def log_run_start(self, runspec: RunSpec, manifest: ArtifactsManifest) -> None:
        payload = self._base_event("run_start")
        payload["runspec"] = runspec.as_dict()
        payload["artifacts_manifest"] = manifest.as_dict()
        payload["manifest_fingerprint"] = manifest.fingerprint()
        self._write(payload)

    def log_event(self, event: str, fields: Dict[str, Any]) -> None:
        payload = self._base_event(event)
        payload.update(fields)
        self._write(payload)

    def _write(self, payload: Dict[str, Any]) -> None:
        self._fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


