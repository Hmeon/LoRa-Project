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


def _load_spec(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("PyYAML is required to load sweep specs") from exc
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def _with_overrides(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    data = json.loads(json.dumps(base))
    for key, value in overrides.items():
        data[key] = value
    return data


def find_c50(sweep_path: str | Path, out_path: str | Path | None = None) -> Dict[str, Any]:
    spec = _load_spec(sweep_path)
    base_runspec = RunSpec.from_dict(spec["base_runspec"])
    base_runspec.validate()
    packets_per_profile = int(spec.get("packets_per_profile", 20))
    target_low = float(spec.get("target_pdr_low", 0.45))
    target_high = float(spec.get("target_pdr_high", 0.55))
    step_ms = int(spec.get("step_ms", 1))
    out_dir = spec.get("out_dir", base_runspec.logging.out_dir)

    results = []
    for idx, profile in enumerate(spec["profiles"]):
        profile_id = profile.get("profile_id", f"profile_{idx}")
        phy = profile["phy"]
        loss_rate = float(profile.get("loss_rate", 0.0))
        loss_rate_ab = profile.get("loss_rate_ab")
        loss_rate_ba = profile.get("loss_rate_ba")
        drop_pattern = profile.get("drop_pattern")
        drop_pattern_ab = profile.get("drop_pattern_ab")
        drop_pattern_ba = profile.get("drop_pattern_ba")
        base_dict = base_runspec.as_dict()
        base_dict["phy"] = phy
        base_dict["tx"]["max_windows"] = packets_per_profile
        base_dict["logging"]["out_dir"] = str(Path(out_dir) / profile_id)

        tx_dict = _with_overrides(base_dict, {"role": "tx", "run_id": f"{base_runspec.run_id}_{profile_id}_tx"})
        rx_dict = _with_overrides(base_dict, {"role": "rx", "run_id": f"{base_runspec.run_id}_{profile_id}_rx"})

        tx_spec = RunSpec.from_dict(tx_dict)
        rx_spec = RunSpec.from_dict(rx_dict)
        tx_spec.validate()
        rx_spec.validate()

        clock = FakeClock()
        link = create_mock_link(
            loss_rate=loss_rate,
            latency_ms=int(profile.get("latency_ms", 0)),
            seed=int(profile.get("seed", 0)),
            drop_pattern=drop_pattern,
            clock=clock,
            loss_rate_ab=loss_rate_ab,
            loss_rate_ba=loss_rate_ba,
            drop_pattern_ab=drop_pattern_ab,
            drop_pattern_ba=drop_pattern_ba,
        )
        tx_codec = create_codec(tx_spec.codec)
        rx_codec = create_codec(rx_spec.codec)
        schema_hash = payload_schema_hash(tx_codec.payload_schema())
        manifest = ArtifactsManifest.create(
            codec_id=tx_codec.codec_id,
            codec_version=tx_codec.codec_version,
            payload_schema_hash=schema_hash,
        )
        verify_manifest(tx_spec, manifest, tx_codec)
        verify_manifest(rx_spec, manifest, rx_codec)

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

        sampler = DummySampler(tx_spec.window.dims)
        tx_node = TxNode(tx_spec, link.a, tx_codec, tx_logger, sampler, clock=clock)
        rx_node = RxNode(rx_spec, link.b, rx_codec, rx_logger, clock=clock)

        run_pair(tx_node, rx_node, clock, step_ms=step_ms, max_steps=packets_per_profile * 10)
        metrics = tx_node.metrics()
        result = {
            "profile_id": profile_id,
            "phy": phy,
            "metrics": metrics,
            "loss_rate": loss_rate,
            "drop_pattern": drop_pattern,
            "loss_rate_ab": loss_rate_ab,
            "loss_rate_ba": loss_rate_ba,
            "drop_pattern_ab": drop_pattern_ab,
            "drop_pattern_ba": drop_pattern_ba,
        }
        results.append(result)
        tx_logger.close()
        rx_logger.close()

        if target_low <= metrics["pdr"] <= target_high:
            selected = {
                "profile_id": profile_id,
                "phy": phy,
                "metrics": metrics,
                "loss_rate": loss_rate,
                "drop_pattern": drop_pattern,
                "loss_rate_ab": loss_rate_ab,
                "loss_rate_ba": loss_rate_ba,
                "drop_pattern_ab": drop_pattern_ab,
                "drop_pattern_ba": drop_pattern_ba,
            }
            output = {"selected": selected, "results": results}
            if out_path is not None:
                Path(out_path).write_text(json.dumps(output, indent=2), encoding="utf-8")
            return output

    output = {"selected": None, "results": results}
    if out_path is not None:
        Path(out_path).write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


