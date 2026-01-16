#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def _load_json_or_yaml(path: Path) -> Dict[str, Any]:
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise SystemExit(
                "PyYAML is required to load YAML. Install with `pip install pyyaml`."
            ) from exc
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit("energy record must be a mapping at the top level")
        return data
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("energy record must be a mapping at the top level")
    return data


def _metrics_obj(entry: object) -> Dict[str, Any] | None:
    if isinstance(entry, dict) and "metrics" in entry and isinstance(entry["metrics"], dict):
        return entry["metrics"]
    return entry if isinstance(entry, dict) else None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Phase 4 helper: combine manual power measurements with a metrics report to compute "
            "energy per delivered window."
        )
    )
    p.add_argument(
        "--metrics",
        required=True,
        help="Path to metrics JSON (cli metrics or phase3_report)",
    )
    p.add_argument("--energy", required=True, help="Path to energy record YAML/JSON")
    p.add_argument("--out", default=None, help="Write report JSON to this path (default: print)")
    return p


def main() -> int:
    args = build_parser().parse_args()
    metrics_path = Path(args.metrics)
    energy_path = Path(args.energy)
    if not metrics_path.exists():
        raise SystemExit(f"metrics not found: {metrics_path}")
    if not energy_path.exists():
        raise SystemExit(f"energy record not found: {energy_path}")

    metrics_all = json.loads(metrics_path.read_text(encoding="utf-8"))
    if not isinstance(metrics_all, dict):
        raise SystemExit("metrics JSON must be a mapping keyed by run_id")

    energy = _load_json_or_yaml(energy_path)
    runs = energy.get("runs")
    if not isinstance(runs, list):
        raise SystemExit("energy record must contain 'runs': [ ... ]")

    report: Dict[str, Any] = {"method": energy.get("method"), "runs": []}
    for run in runs:
        if not isinstance(run, dict):
            continue
        run_id = str(run.get("run_id", "")).strip()
        if not run_id:
            continue

        metrics_entry = _metrics_obj(metrics_all.get(run_id))
        if metrics_entry is None:
            report["runs"].append({"run_id": run_id, "error": "run_id not found in metrics report"})
            continue

        avg_power_w = float(run["avg_power_w"])
        duration_s = float(run["duration_s"])
        energy_j = avg_power_w * duration_s

        rx_ok_count = metrics_entry.get("rx_ok_count", 0)
        acked_count = metrics_entry.get("acked_count", 0)
        delivered = int(rx_ok_count) if int(rx_ok_count) > 0 else int(acked_count)
        sent = int(metrics_entry.get("sent_count", 0))

        out_run: Dict[str, Any] = {
            "run_id": run_id,
            "avg_power_w": avg_power_w,
            "duration_s": duration_s,
            "energy_j": energy_j,
            "delivered_count": delivered,
            "sent_count": sent,
            "energy_per_delivered_window_j": (energy_j / delivered) if delivered else None,
            "energy_per_tx_attempt_j": (energy_j / sent) if sent else None,
            "notes": run.get("notes"),
        }
        report["runs"].append(out_run)

    output = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
