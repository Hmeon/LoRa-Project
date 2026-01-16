#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from loralink_mllc.codecs import create_codec
from loralink_mllc.config import ArtifactsManifest, load_runspec, verify_manifest
from loralink_mllc.config.runspec import RunSpec
from loralink_mllc.experiments.metrics import compute_metrics, load_events


def _to_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_no}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"invalid JSONL object at {path}:{line_no}: expected mapping")
        yield record


def _load_dataset_by_run_id(dataset_path: Path) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in _iter_jsonl(dataset_path):
        run_id = str(record.get("run_id", ""))
        if not run_id:
            continue
        grouped.setdefault(run_id, []).append(record)
    return grouped


def _first_run_start(events: Sequence[Dict[str, Any]]) -> Dict[str, Any] | None:
    for event in events:
        if event.get("event") == "run_start":
            return event
    return None


def _extract_runspec(events: Sequence[Dict[str, Any]]) -> RunSpec | None:
    run_start = _first_run_start(events)
    if not run_start:
        return None
    runspec = run_start.get("runspec")
    if not isinstance(runspec, dict):
        return None
    spec = RunSpec.from_dict(runspec)
    spec.validate()
    return spec


def _extract_manifest(events: Sequence[Dict[str, Any]]) -> ArtifactsManifest | None:
    run_start = _first_run_start(events)
    if not run_start:
        return None
    manifest = run_start.get("artifacts_manifest")
    if not isinstance(manifest, dict):
        return None
    return ArtifactsManifest.from_dict(manifest)


@dataclass
class _Finding:
    errors: List[str]
    warnings: List[str]

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def _infer_window_id_map(tx_events: Sequence[Dict[str, Any]], finding: _Finding) -> dict[int, int]:
    inflight: dict[int, int] = {}
    next_window_id = 0
    for event in tx_events:
        kind = event.get("event")
        if kind == "tx_sent":
            seq = _to_int(event.get("seq"))
            if seq is None:
                continue
            attempt = _to_int(event.get("attempt")) or 1
            if attempt != 1:
                continue
            window_id = _to_int(event.get("window_id"))
            if window_id is None:
                finding.warn("tx_sent missing window_id; dataset join may be incomplete")
                window_id = next_window_id
            inflight[seq] = window_id
            next_window_id = max(next_window_id, window_id + 1)
        elif kind == "tx_failed":
            seq = _to_int(event.get("seq"))
            if seq is None:
                continue
            inflight.pop(seq, None)
        elif kind == "ack_received":
            ack_seq = _to_int(event.get("ack_seq"))
            if ack_seq is None:
                continue
            inflight.pop(ack_seq, None)
    return inflight


def _acked_window_ids(
    events: Sequence[Dict[str, Any]], finding: _Finding
) -> list[int]:
    tx_events = [e for e in events if e.get("role") == "tx"]
    tx_events.sort(key=lambda e: _to_int(e.get("ts_ms")) or 0)
    seq_to_window: dict[int, int] = {}
    next_window_id = 0
    acked: list[int] = []

    for event in tx_events:
        kind = event.get("event")
        if kind == "tx_sent":
            seq = _to_int(event.get("seq"))
            if seq is None:
                continue
            attempt = _to_int(event.get("attempt")) or 1
            window_id = _to_int(event.get("window_id"))
            if attempt == 1:
                if window_id is None:
                    finding.warn("tx_sent missing window_id; inferring by order")
                    window_id = next_window_id
                seq_to_window[seq] = window_id
                next_window_id = max(next_window_id, window_id + 1)
            else:
                if window_id is not None:
                    seq_to_window.setdefault(seq, window_id)
        elif kind == "ack_received":
            ack_seq = _to_int(event.get("ack_seq"))
            if ack_seq is None:
                continue
            window_id = _to_int(event.get("window_id"))
            if window_id is None:
                window_id = seq_to_window.get(ack_seq)
            if window_id is None:
                finding.warn("ack_received missing window_id; cannot join to dataset")
                continue
            acked.append(window_id)
            seq_to_window.pop(ack_seq, None)

    return acked


def _validate_dataset(
    records: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    expected_len: int | None,
    expected_dims: int | None,
    finding: _Finding,
) -> dict[int, list[float]]:
    windows: dict[int, list[float]] = {}
    for idx, record in enumerate(records):
        window_id = _to_int(record.get("window_id"))
        window = record.get("window")
        if window_id is None or not isinstance(window, list):
            finding.warn(f"dataset record {idx} missing window_id/window")
            continue
        if expected_len is not None and len(window) != expected_len:
            finding.error(
                f"dataset window_len mismatch for run_id={run_id} window_id={window_id}: "
                f"{len(window)} != {expected_len}"
            )
        order = record.get("order")
        if expected_dims is not None and isinstance(order, list) and len(order) != expected_dims:
            finding.error(
                f"dataset order_len mismatch for run_id={run_id} window_id={window_id}: "
                f"{len(order)} != {expected_dims}"
            )
        units = record.get("units")
        if units is not None and not isinstance(units, dict):
            finding.warn(
                f"dataset units is not a mapping for run_id={run_id} window_id={window_id}"
            )

        if window_id in windows:
            finding.warn(f"duplicate dataset window_id={window_id} for run_id={run_id}")
        windows[window_id] = [float(v) for v in window]
    return windows


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Validate a run's logs/artifacts/dataset for reproducibility."
    )
    p.add_argument("--log", action="append", required=True, help="Path to a TX/RX JSONL log")
    p.add_argument("--runspec", default=None, help="Optional RunSpec file to validate against")
    p.add_argument(
        "--manifest",
        default=None,
        help="Optional artifacts manifest JSON to validate against",
    )
    p.add_argument("--dataset", default=None, help="Optional dataset_raw.jsonl for join checks")
    p.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    p.add_argument("--out", default=None, help="Write report JSON to this path (default: print)")
    return p


def main() -> int:
    args = build_parser().parse_args()
    all_events: list[dict[str, Any]] = []
    for path in args.log:
        all_events.extend(load_events(path))

    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in all_events:
        run_id = str(event.get("run_id", "unknown"))
        grouped.setdefault(run_id, []).append(event)

    dataset_by_run: dict[str, list[dict[str, Any]]] | None = None
    if args.dataset:
        dataset_path = Path(args.dataset)
        if not dataset_path.exists():
            raise SystemExit(f"dataset not found: {dataset_path}")
        dataset_by_run = _load_dataset_by_run_id(dataset_path)

    expected_runspec: RunSpec | None = None
    if args.runspec:
        expected_runspec = load_runspec(args.runspec)

    expected_manifest: ArtifactsManifest | None = None
    if args.manifest:
        expected_manifest = ArtifactsManifest.load(args.manifest)

    report: dict[str, object] = {}
    for run_id, events in grouped.items():
        finding = _Finding(errors=[], warnings=[])
        metrics = compute_metrics(events)
        roles = sorted({str(e.get("role", "")) for e in events if e.get("role")})

        runspec = _extract_runspec(events)
        manifest = _extract_manifest(events)
        if expected_runspec is not None:
            if run_id != expected_runspec.run_id:
                finding.error(
                    f"--runspec run_id {expected_runspec.run_id} does not match log run_id {run_id}"
                )
            runspec = expected_runspec
        if expected_manifest is not None:
            manifest = expected_manifest

        if runspec is None:
            finding.warn("missing run_start.runspec in logs")
        if manifest is None:
            finding.warn("missing run_start.artifacts_manifest in logs")

        codec_error = None
        if runspec is not None and manifest is not None:
            try:
                codec = create_codec(runspec.codec)
                verify_manifest(runspec, manifest, codec)
            except Exception as exc:
                codec_error = str(exc)
                finding.error(f"artifacts verification failed: {codec_error}")

        dataset_summary: dict[str, object] | None = None
        if dataset_by_run is not None:
            records = dataset_by_run.get(run_id, [])
            expected_len = runspec.window.dims * runspec.window.W if runspec is not None else None
            expected_dims = runspec.window.dims if runspec is not None else None
            windows = _validate_dataset(
                records,
                run_id=run_id,
                expected_len=expected_len,
                expected_dims=expected_dims,
                finding=finding,
            )
            acked_ids = _acked_window_ids(events, finding)
            missing_acked = [wid for wid in acked_ids if wid not in windows]
            if missing_acked:
                finding.warn(f"{len(missing_acked)} acked window_ids missing from dataset")
            dataset_summary = {
                "records": len(records),
                "unique_window_ids": len(windows),
                "acked_windows": len(acked_ids),
                "missing_acked_windows": len(missing_acked),
            }

        if args.strict and finding.warnings:
            finding.errors.extend([f"warning(strict): {w}" for w in finding.warnings])

        report[run_id] = {
            "roles": roles,
            "metrics": metrics,
            "dataset": dataset_summary,
            "errors": finding.errors,
            "warnings": finding.warnings,
        }

    output = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
