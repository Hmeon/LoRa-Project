#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"expected JSON object at top level: {path}")
    return data


def _metrics_obj(entry: object) -> Dict[str, Any] | None:
    if isinstance(entry, dict) and "metrics" in entry and isinstance(entry["metrics"], dict):
        return entry["metrics"]
    return entry if isinstance(entry, dict) else None


def _to_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _payload_bytes_mean(metrics: Dict[str, Any]) -> float | None:
    stats = metrics.get("payload_bytes")
    if isinstance(stats, dict):
        return _to_float(stats.get("mean"))
    return None


def _improve_pct(new: float | None, base: float | None) -> float | None:
    if new is None or base is None:
        return None
    if base == 0:
        return None
    return (new - base) / base * 100.0


def _reduce_pct(new: float | None, base: float | None) -> float | None:
    if new is None or base is None:
        return None
    if base == 0:
        return None
    return (base - new) / base * 100.0


def _pass(pct: float | None, target_pct: float) -> bool | None:
    if pct is None:
        return None
    return pct >= target_pct


def _load_energy_map(path: Path) -> Dict[str, float]:
    data = _load_json(path)
    runs = data.get("runs")
    if not isinstance(runs, list):
        raise SystemExit("phase4 energy report must contain 'runs': [ ... ]")
    out: Dict[str, float] = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        run_id = str(run.get("run_id", "")).strip()
        value = _to_float(run.get("energy_per_delivered_window_j"))
        if run_id and value is not None:
            out[run_id] = value
    return out


@dataclass(frozen=True)
class _Run:
    run_id: str
    payload_bytes_mean: float | None
    pdr: float | None
    etx: float | None
    total_toa_ms: float | None
    energy_per_delivered_window_j: float | None


def _collect_runs(
    phase3: Dict[str, Any], *, energy_map: Dict[str, float] | None = None
) -> List[_Run]:
    runs: list[_Run] = []
    for run_id, entry in phase3.items():
        metrics = _metrics_obj(entry)
        if metrics is None:
            continue
        runs.append(
            _Run(
                run_id=str(run_id),
                payload_bytes_mean=_payload_bytes_mean(metrics),
                pdr=_to_float(metrics.get("pdr")),
                etx=_to_float(metrics.get("etx")),
                total_toa_ms=_to_float(metrics.get("total_toa_ms")),
                energy_per_delivered_window_j=(
                    energy_map.get(str(run_id)) if energy_map is not None else None
                ),
            )
        )
    return runs


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Compute baseline-relative KPI deltas (PDR/ETX/Energy) from Phase 3/4 JSON reports."
        )
    )
    p.add_argument(
        "--phase3",
        required=True,
        help="Path to phase3_report JSON (or cli metrics JSON)",
    )
    p.add_argument("--phase4", default=None, help="Optional path to phase4_energy_report JSON")
    p.add_argument("--baseline", required=True, help="Baseline run_id for relative deltas")
    p.add_argument(
        "--variant",
        action="append",
        default=[],
        help=(
            "Variant run_id to evaluate (repeatable). If omitted, evaluates all non-baseline runs."
        ),
    )
    p.add_argument("--pdr-improve-pct", type=float, default=30.0)
    p.add_argument("--etx-reduce-pct", type=float, default=20.0)
    p.add_argument("--energy-reduce-pct", type=float, default=20.0)
    p.add_argument("--out", default=None, help="Write JSON report to this path (default: print)")
    return p


def main() -> int:
    args = build_parser().parse_args()
    phase3_path = Path(args.phase3)
    if not phase3_path.exists():
        raise SystemExit(f"phase3 report not found: {phase3_path}")
    phase3 = _load_json(phase3_path)

    energy_map: Dict[str, float] | None = None
    if args.phase4:
        phase4_path = Path(args.phase4)
        if not phase4_path.exists():
            raise SystemExit(f"phase4 report not found: {phase4_path}")
        energy_map = _load_energy_map(phase4_path)

    runs = _collect_runs(phase3, energy_map=energy_map)
    by_id = {r.run_id: r for r in runs}
    baseline_id = str(args.baseline)
    baseline = by_id.get(baseline_id)
    if baseline is None:
        raise SystemExit(f"baseline run_id not found in phase3 report: {baseline_id}")

    variants: Iterable[str] = args.variant or [r.run_id for r in runs if r.run_id != baseline_id]
    results: list[dict[str, object]] = []
    for run_id in variants:
        rid = str(run_id)
        if rid == baseline_id:
            continue
        run = by_id.get(rid)
        if run is None:
            results.append({"run_id": rid, "error": "run_id not found in phase3 report"})
            continue

        pdr_improve = _improve_pct(run.pdr, baseline.pdr)
        etx_reduce = _reduce_pct(run.etx, baseline.etx)
        energy_reduce = _reduce_pct(
            run.energy_per_delivered_window_j, baseline.energy_per_delivered_window_j
        )
        toa_reduce = _reduce_pct(run.total_toa_ms, baseline.total_toa_ms)

        results.append(
            {
                "run_id": run.run_id,
                "payload_bytes_mean": run.payload_bytes_mean,
                "pdr": run.pdr,
                "pdr_improve_pct": pdr_improve,
                "pdr_pass": _pass(pdr_improve, float(args.pdr_improve_pct)),
                "etx": run.etx,
                "etx_reduce_pct": etx_reduce,
                "etx_pass": _pass(etx_reduce, float(args.etx_reduce_pct)),
                "energy_per_delivered_window_j": run.energy_per_delivered_window_j,
                "energy_reduce_pct": energy_reduce,
                "energy_pass": _pass(energy_reduce, float(args.energy_reduce_pct)),
                "total_toa_ms": run.total_toa_ms,
                "toa_reduce_pct": toa_reduce,
            }
        )

    report: dict[str, object] = {
        "baseline_run_id": baseline.run_id,
        "baseline": {
            "payload_bytes_mean": baseline.payload_bytes_mean,
            "pdr": baseline.pdr,
            "etx": baseline.etx,
            "energy_per_delivered_window_j": baseline.energy_per_delivered_window_j,
            "total_toa_ms": baseline.total_toa_ms,
        },
        "targets": {
            "pdr_improve_pct": float(args.pdr_improve_pct),
            "etx_reduce_pct": float(args.etx_reduce_pct),
            "energy_reduce_pct": float(args.energy_reduce_pct),
        },
        "variants": sorted(
            results,
            key=lambda r: float(r["payload_bytes_mean"])
            if isinstance(r.get("payload_bytes_mean"), (int, float))
            else float("inf"),
        ),
        "notes": [
            "PDR improvement is baseline-relative percent: (variant - baseline) / baseline * 100.",
            (
                "ETX/Energy reduction is baseline-relative percent: "
                "(baseline - variant) / baseline * 100."
            ),
            (
                "If Phase 4 energy is not provided, energy fields are null; "
                "total_toa_ms can be a proxy."
            ),
        ],
    }

    output = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
