from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from loralink_mllc.codecs import create_codec, payload_schema_hash
from loralink_mllc.config.artifacts import ArtifactsManifest, verify_manifest
from loralink_mllc.config.runspec import RunSpec
from loralink_mllc.experiments.controller import run_pair
from loralink_mllc.radio.mock import create_mock_link
from loralink_mllc.runtime.logging import JsonlLogger
from loralink_mllc.runtime.scheduler import FakeClock
from loralink_mllc.runtime.tx_node import DummySampler, TxNode
from loralink_mllc.runtime.rx_node import RxNode


def _load_json_or_yaml(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("PyYAML is required to load YAML configs") from exc
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def run_ab(
    c50_path: str | Path,
    raw_runspec_path: str | Path,
    latent_runspec_path: str | Path,
    out_path: str | Path | None = None,
) -> Dict[str, Any]:
    c50 = _load_json_or_yaml(c50_path)
    selected = c50.get("selected")
    if not selected:
        raise ValueError("c50 selection missing")
    phy = selected["phy"]
    loss_rate = float(selected.get("loss_rate", 0.0))
    loss_rate_ab = selected.get("loss_rate_ab")
    loss_rate_ba = selected.get("loss_rate_ba")
    drop_pattern = selected.get("drop_pattern")
    drop_pattern_ab = selected.get("drop_pattern_ab")
    drop_pattern_ba = selected.get("drop_pattern_ba")

    raw_spec = RunSpec.from_dict(_load_json_or_yaml(raw_runspec_path))
    latent_spec = RunSpec.from_dict(_load_json_or_yaml(latent_runspec_path))
    raw_spec.validate()
    latent_spec.validate()
    if raw_spec.mode != "RAW":
        raise ValueError("raw runspec mode must be RAW")
    if latent_spec.mode != "LATENT":
        raise ValueError("latent runspec mode must be LATENT")
    if raw_spec.window != latent_spec.window:
        raise ValueError("raw/latent window specs must match")

    def _prepare_spec(spec: RunSpec, role: str, suffix: str, out_dir: str) -> RunSpec:
        data = spec.as_dict()
        data["role"] = role
        data["run_id"] = f"{spec.run_id}_{suffix}_{role}"
        data["phy"] = phy
        data["logging"]["out_dir"] = out_dir
        return RunSpec.from_dict(data)

    def _run_once(spec: RunSpec, label: str) -> Dict[str, Any]:
        clock = FakeClock()
        link = create_mock_link(
            loss_rate=loss_rate,
            latency_ms=0,
            seed=0,
            drop_pattern=drop_pattern,
            clock=clock,
            loss_rate_ab=loss_rate_ab,
            loss_rate_ba=loss_rate_ba,
            drop_pattern_ab=drop_pattern_ab,
            drop_pattern_ba=drop_pattern_ba,
        )
        codec = create_codec(spec.codec)
        schema_hash = payload_schema_hash(codec.payload_schema())
        manifest = ArtifactsManifest.create(
            codec_id=codec.codec_id,
            codec_version=codec.codec_version,
            payload_schema_hash=schema_hash,
        )
        verify_manifest(spec, manifest, codec)

        tx_spec = _prepare_spec(spec, "tx", label, spec.logging.out_dir)
        rx_spec = _prepare_spec(spec, "rx", label, spec.logging.out_dir)
        tx_spec.validate()
        rx_spec.validate()

        tx_logger = JsonlLogger(
            tx_spec.logging.out_dir,
            tx_spec.run_id,
            tx_spec.role,
            tx_spec.mode,
            tx_spec.phy_profile_id(),
            clock=clock,
        )
        rx_logger = JsonlLogger(
            rx_spec.logging.out_dir,
            rx_spec.run_id,
            rx_spec.role,
            rx_spec.mode,
            rx_spec.phy_profile_id(),
            clock=clock,
        )
        tx_logger.log_run_start(tx_spec, manifest)
        rx_logger.log_run_start(rx_spec, manifest)

        sampler = DummySampler(spec.window.dims)
        tx_node = TxNode(tx_spec, link.a, codec, tx_logger, sampler, clock=clock)
        rx_node = RxNode(rx_spec, link.b, codec, rx_logger, clock=clock)
        max_steps = (spec.tx.max_windows or 1000) * 10
        run_pair(tx_node, rx_node, clock, step_ms=1, max_steps=max_steps)
        metrics = tx_node.metrics()
        tx_logger.close()
        rx_logger.close()
        return metrics

    raw_metrics = _run_once(raw_spec, "raw")
    latent_metrics = _run_once(latent_spec, "latent")

    report = {
        "phy": phy,
        "raw": raw_metrics,
        "latent": latent_metrics,
        "delta": {
            "pdr": latent_metrics["pdr"] - raw_metrics["pdr"],
            "etx": latent_metrics["etx"] - raw_metrics["etx"],
            "total_toa_ms": latent_metrics["total_toa_ms"] - raw_metrics["total_toa_ms"],
        },
    }
    if out_path is not None:
        Path(out_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


