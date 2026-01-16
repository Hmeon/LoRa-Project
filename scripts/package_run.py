#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from loralink_mllc.config.artifacts import current_git_commit
from loralink_mllc.experiments.metrics import compute_metrics, load_events


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def _load_run_id(events: List[Dict[str, Any]]) -> str | None:
    run_ids = {str(e.get("run_id", "")) for e in events if e.get("run_id")}
    if len(run_ids) == 1:
        return next(iter(run_ids))
    return None


def _copy_any(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Package a run into a reproducible folder (and optional zip): logs + dataset + extras "
            "+ metrics + file hashes."
        )
    )
    p.add_argument("--log", action="append", required=True, help="Path to a TX/RX JSONL log")
    p.add_argument("--run-id", default=None, help="Run ID (auto-detected if logs contain one)")
    p.add_argument("--dataset", default=None, help="Optional dataset JSONL to include")
    p.add_argument(
        "--extra",
        action="append",
        default=[],
        help="Extra file/dir to include (repeatable)",
    )
    p.add_argument("--out-dir", required=True, help="Output directory for the package")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing package directory")
    p.add_argument("--zip", action="store_true", help="Also write <run_id>.zip next to the folder")
    return p


def main() -> int:
    args = build_parser().parse_args()
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    all_events: list[dict[str, Any]] = []
    log_paths = [Path(p) for p in args.log]
    for path in log_paths:
        if not path.exists():
            raise SystemExit(f"log not found: {path}")
        all_events.extend(load_events(path))

    detected_run_id = _load_run_id(all_events)
    run_id = str(args.run_id or detected_run_id or "").strip()
    if not run_id:
        raise SystemExit("run_id could not be detected from logs; pass --run-id explicitly")

    package_dir = out_root / run_id
    if package_dir.exists():
        if not args.overwrite:
            raise SystemExit(f"package dir exists: {package_dir} (use --overwrite)")
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)

    logs_dir = package_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    for path in log_paths:
        _copy_any(path, logs_dir / path.name)

    if args.dataset:
        dataset_path = Path(args.dataset)
        if not dataset_path.exists():
            raise SystemExit(f"dataset not found: {dataset_path}")
        _copy_any(dataset_path, package_dir / "dataset" / dataset_path.name)

    for extra in args.extra:
        extra_path = Path(extra)
        if not extra_path.exists():
            raise SystemExit(f"extra path not found: {extra_path}")
        _copy_any(extra_path, package_dir / "extra" / extra_path.name)

    metrics = compute_metrics(all_events)
    (package_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    created_at = datetime.now(timezone.utc).isoformat()
    package_manifest: Dict[str, Any] = {
        "run_id": run_id,
        "created_at": created_at,
        "git_commit": current_git_commit(),
        "files": [],
    }
    for path in _iter_files(package_dir):
        rel = path.relative_to(package_dir).as_posix()
        package_manifest["files"].append(
            {
                "path": rel,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_path(path),
            }
        )
    (package_dir / "package_manifest.json").write_text(
        json.dumps(package_manifest, indent=2), encoding="utf-8"
    )

    if args.zip:
        zip_path = out_root / f"{run_id}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in _iter_files(package_dir):
                rel = path.relative_to(package_dir).as_posix()
                zf.write(path, arcname=f"{run_id}/{rel}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

