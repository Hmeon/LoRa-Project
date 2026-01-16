#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


def _require_matplotlib():
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit(
            "matplotlib is required for plotting. Install with `python -m pip install -e .[viz]`."
        ) from exc
    return plt


def _to_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object at top level: {path}")
    return data


@dataclass(frozen=True)
class RunPoint:
    run_id: str
    payload_bytes_mean: float
    pdr: float | None
    etx: float | None
    ack_rtt_ms_mean: float | None
    rssi_dbm_mean: float | None
    recon_mae: float | None
    recon_mse: float | None
    energy_per_delivered_window_j: float | None


def _extract_points(phase3_report: Dict[str, Any]) -> List[RunPoint]:
    points: list[RunPoint] = []
    for run_id, entry in phase3_report.items():
        if not isinstance(entry, dict):
            continue
        metrics = entry.get("metrics")
        if not isinstance(metrics, dict):
            continue
        payload_stats = metrics.get("payload_bytes")
        if not isinstance(payload_stats, dict):
            continue
        payload_mean = _to_float(payload_stats.get("mean"))
        if payload_mean is None:
            continue
        ack_rtt_stats = metrics.get("ack_rtt_ms")
        rssi_stats = metrics.get("rssi_dbm")
        roundtrip = entry.get("roundtrip_over_acked")
        recon_mae = recon_mse = None
        if isinstance(roundtrip, dict):
            overall = roundtrip.get("overall")
            if isinstance(overall, dict):
                recon_mae = _to_float(overall.get("mae"))
                recon_mse = _to_float(overall.get("mse"))
        points.append(
            RunPoint(
                run_id=str(run_id),
                payload_bytes_mean=payload_mean,
                pdr=_to_float(metrics.get("pdr")),
                etx=_to_float(metrics.get("etx")),
                ack_rtt_ms_mean=(
                    _to_float(ack_rtt_stats.get("mean"))
                    if isinstance(ack_rtt_stats, dict)
                    else None
                ),
                rssi_dbm_mean=(
                    _to_float(rssi_stats.get("mean")) if isinstance(rssi_stats, dict) else None
                ),
                recon_mae=recon_mae,
                recon_mse=recon_mse,
                energy_per_delivered_window_j=None,
            )
        )
    return points


def _attach_energy(points: List[RunPoint], energy_report: Dict[str, Any]) -> List[RunPoint]:
    runs = energy_report.get("runs")
    if not isinstance(runs, list):
        return points
    by_run_id: dict[str, float] = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        run_id = str(run.get("run_id", "")).strip()
        value = _to_float(run.get("energy_per_delivered_window_j"))
        if run_id and value is not None:
            by_run_id[run_id] = value
    out: list[RunPoint] = []
    for point in points:
        out.append(
            RunPoint(
                run_id=point.run_id,
                payload_bytes_mean=point.payload_bytes_mean,
                pdr=point.pdr,
                etx=point.etx,
                ack_rtt_ms_mean=point.ack_rtt_ms_mean,
                rssi_dbm_mean=point.rssi_dbm_mean,
                recon_mae=point.recon_mae,
                recon_mse=point.recon_mse,
                energy_per_delivered_window_j=by_run_id.get(point.run_id),
            )
        )
    return out


def _write_csv(path: Path, points: List[RunPoint]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "run_id",
                "payload_bytes_mean",
                "pdr",
                "etx",
                "ack_rtt_ms_mean",
                "rssi_dbm_mean",
                "recon_mae",
                "recon_mse",
                "energy_per_delivered_window_j",
            ]
        )
        for point in sorted(points, key=lambda p: p.payload_bytes_mean):
            writer.writerow(
                [
                    point.run_id,
                    point.payload_bytes_mean,
                    point.pdr,
                    point.etx,
                    point.ack_rtt_ms_mean,
                    point.rssi_dbm_mean,
                    point.recon_mae,
                    point.recon_mse,
                    point.energy_per_delivered_window_j,
                ]
            )


def _plot_series(
    *,
    points: List[RunPoint],
    y_key: str,
    title: str,
    y_label: str,
    out_path: Path,
) -> None:
    plt = _require_matplotlib()
    xs: list[float] = []
    ys: list[float] = []
    labels: list[str] = []
    for p in sorted(points, key=lambda p: p.payload_bytes_mean):
        y_val = getattr(p, y_key)
        if y_val is None:
            continue
        xs.append(p.payload_bytes_mean)
        ys.append(float(y_val))
        labels.append(p.run_id)
    if not xs:
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(6.4, 4.0))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(xs, ys, marker="o")
    for x, y, label in zip(xs, ys, labels, strict=True):
        ax.annotate(label, (x, y), textcoords="offset points", xytext=(4, 4), fontsize=8)
    ax.set_title(title)
    ax.set_xlabel("payload_bytes (mean)")
    ax.set_ylabel(y_label)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Plot Phase 3/4 results from JSON reports. Input should be the output of "
            "`scripts/phase3_report.py` and optionally `scripts/phase4_energy_report.py`."
        )
    )
    p.add_argument("--phase3", required=True, help="Path to phase3_report JSON")
    p.add_argument("--phase4", default=None, help="Optional path to phase4_energy_report JSON")
    p.add_argument("--out-dir", required=True, help="Output directory for CSV/plots")
    p.add_argument(
        "--plots",
        action="store_true",
        help="Generate PNG plots (requires matplotlib)",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    phase3_report = _load_json(Path(args.phase3))
    points = _extract_points(phase3_report)
    if args.phase4:
        points = _attach_energy(points, _load_json(Path(args.phase4)))

    _write_csv(out_dir / "phase_summary.csv", points)
    (out_dir / "phase_summary.json").write_text(
        json.dumps([p.__dict__ for p in points], indent=2),
        encoding="utf-8",
    )

    if args.plots:
        _plot_series(
            points=points,
            y_key="pdr",
            title="PDR vs payload bytes",
            y_label="PDR",
            out_path=out_dir / "pdr_vs_payload.png",
        )
        _plot_series(
            points=points,
            y_key="etx",
            title="ETX vs payload bytes",
            y_label="ETX",
            out_path=out_dir / "etx_vs_payload.png",
        )
        _plot_series(
            points=points,
            y_key="recon_mae",
            title="Reconstruction MAE vs payload bytes",
            y_label="MAE",
            out_path=out_dir / "mae_vs_payload.png",
        )
        _plot_series(
            points=points,
            y_key="energy_per_delivered_window_j",
            title="Energy per delivered window vs payload bytes",
            y_label="Energy (J)",
            out_path=out_dir / "energy_vs_payload.png",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

