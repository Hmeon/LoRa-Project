import builtins
import json
from pathlib import Path

import pytest

from loralink_mllc.experiments.phase0_c50 import _load_spec, find_c50
from loralink_mllc.experiments.phase1_ab import _load_json_or_yaml, run_ab


def _install_yaml_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
        if name == "yaml":
            raise ImportError("yaml disabled for test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_phase0_load_spec_yaml_requires_pyyaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sweep_path = tmp_path / "sweep.yaml"
    sweep_path.write_text("base_runspec: {}\nprofiles: []\n", encoding="utf-8")
    _install_yaml_import_error(monkeypatch)
    with pytest.raises(RuntimeError, match="PyYAML is required to load sweep specs"):
        _load_spec(sweep_path)


def test_phase0_load_spec_yaml_success(tmp_path: Path) -> None:
    sweep_path = tmp_path / "sweep.yaml"
    sweep_path.write_text("base_runspec: {run_id: x}\nprofiles: []\n", encoding="utf-8")
    data = _load_spec(sweep_path)
    assert data["base_runspec"]["run_id"] == "x"


def test_phase1_load_json_or_yaml_yaml_requires_pyyaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text("selected: {}\n", encoding="utf-8")
    _install_yaml_import_error(monkeypatch)
    with pytest.raises(RuntimeError, match="PyYAML is required to load YAML configs"):
        _load_json_or_yaml(cfg_path)


def test_phase1_load_json_or_yaml_yaml_success(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text("selected:\n  phy: {sf: 7}\n", encoding="utf-8")
    data = _load_json_or_yaml(cfg_path)
    assert data["selected"]["phy"]["sf"] == 7


def test_phase0_find_c50_returns_selected_none(tmp_path: Path) -> None:
    base_runspec = {
        "run_id": "smoke",
        "role": "tx",
        "mode": "RAW",
        "phy": {
            "sf": 7,
            "bw_hz": 125000,
            "cr": 5,
            "preamble": 8,
            "crc_on": True,
            "explicit_header": True,
            "tx_power_dbm": 14,
        },
        "window": {"dims": 12, "W": 1, "sample_hz": 1.0},
        "codec": {"id": "raw", "version": "1", "params": {}},
        "tx": {"guard_ms": 0, "ack_timeout_ms": 10, "max_retries": 0, "max_inflight": 1},
        "logging": {"out_dir": str(tmp_path)},
    }
    sweep = {
        "base_runspec": base_runspec,
        "profiles": [
            {
                "profile_id": "nohit",
                "phy": base_runspec["phy"],
                "drop_pattern_ab": [True],
                "drop_pattern_ba": [True],
            }
        ],
        "packets_per_profile": 5,
        "target_pdr_low": 0.9,
        "target_pdr_high": 1.0,
        "out_dir": str(tmp_path),
    }
    sweep_path = tmp_path / "sweep.json"
    out_path = tmp_path / "c50.json"
    sweep_path.write_text(json.dumps(sweep), encoding="utf-8")

    result = find_c50(sweep_path, out_path=out_path)
    assert result["selected"] is None
    assert json.loads(out_path.read_text(encoding="utf-8"))["selected"] is None


def test_phase1_run_ab_error_conditions(tmp_path: Path) -> None:
    c50_path = tmp_path / "c50.json"
    c50_path.write_text(json.dumps({"selected": None}), encoding="utf-8")

    base_runspec = {
        "run_id": "raw",
        "role": "tx",
        "mode": "RAW",
        "phy": {
            "sf": 7,
            "bw_hz": 125000,
            "cr": 5,
            "preamble": 8,
            "crc_on": True,
            "explicit_header": True,
            "tx_power_dbm": 14,
        },
        "window": {"dims": 12, "W": 1, "sample_hz": 1.0},
        "codec": {"id": "raw", "version": "1", "params": {}},
        "tx": {
            "guard_ms": 0,
            "ack_timeout_ms": 10,
            "max_retries": 0,
            "max_inflight": 1,
            "max_windows": 1,
        },
        "logging": {"out_dir": str(tmp_path)},
    }
    raw_path = tmp_path / "raw.json"
    latent_path = tmp_path / "latent.json"
    raw_path.write_text(json.dumps(base_runspec), encoding="utf-8")

    latent_spec = json.loads(json.dumps(base_runspec))
    latent_spec["run_id"] = "latent"
    latent_spec["mode"] = "LATENT"
    latent_spec["codec"] = {"id": "zlib", "version": "1", "params": {"level": 6}}
    latent_path.write_text(json.dumps(latent_spec), encoding="utf-8")

    with pytest.raises(ValueError, match="c50 selection missing"):
        run_ab(c50_path, raw_path, latent_path)

    c50_path.write_text(
        json.dumps({"selected": {"phy": base_runspec["phy"], "loss_rate": 0.0}}), encoding="utf-8"
    )

    bad_raw = json.loads(raw_path.read_text(encoding="utf-8"))
    bad_raw["mode"] = "LATENT"
    raw_path.write_text(json.dumps(bad_raw), encoding="utf-8")
    with pytest.raises(ValueError, match="raw runspec mode must be RAW"):
        run_ab(c50_path, raw_path, latent_path)

    raw_path.write_text(json.dumps(base_runspec), encoding="utf-8")
    bad_latent = json.loads(latent_path.read_text(encoding="utf-8"))
    bad_latent["mode"] = "RAW"
    latent_path.write_text(json.dumps(bad_latent), encoding="utf-8")
    with pytest.raises(ValueError, match="latent runspec mode must be LATENT"):
        run_ab(c50_path, raw_path, latent_path)

    bad_latent["mode"] = "LATENT"
    bad_latent["window"]["W"] = 2
    latent_path.write_text(json.dumps(bad_latent), encoding="utf-8")
    with pytest.raises(ValueError, match="window specs must match"):
        run_ab(c50_path, raw_path, latent_path)
