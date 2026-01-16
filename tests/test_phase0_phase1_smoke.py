import json
from pathlib import Path

from loralink_mllc.experiments.phase0_c50 import find_c50
from loralink_mllc.experiments.phase1_ab import run_ab


def test_phase0_phase1_smoke(tmp_path: Path) -> None:
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
                "profile_id": "c50",
                "phy": base_runspec["phy"],
                "drop_pattern_ab": [False, True],
                "drop_pattern_ba": [False],
            }
        ],
        "packets_per_profile": 10,
        "target_pdr_low": 0.45,
        "target_pdr_high": 0.55,
        "out_dir": str(tmp_path),
    }
    sweep_path = tmp_path / "sweep.json"
    c50_path = tmp_path / "c50.json"
    sweep_path.write_text(json.dumps(sweep), encoding="utf-8")

    result = find_c50(sweep_path, out_path=c50_path)
    assert result["selected"] is not None
    assert 0.0 <= result["selected"]["metrics"]["pdr"] <= 1.0

    raw_runspec = json.loads(json.dumps(base_runspec))
    raw_runspec["run_id"] = "raw"
    raw_runspec["mode"] = "RAW"
    raw_runspec["codec"] = {"id": "raw", "version": "1", "params": {}}
    raw_runspec["tx"]["max_windows"] = 10

    latent_runspec = json.loads(json.dumps(base_runspec))
    latent_runspec["run_id"] = "latent"
    latent_runspec["mode"] = "LATENT"
    latent_runspec["codec"] = {"id": "zlib", "version": "1", "params": {"level": 6}}
    latent_runspec["tx"]["max_windows"] = 10

    raw_path = tmp_path / "raw.json"
    latent_path = tmp_path / "latent.json"
    raw_path.write_text(json.dumps(raw_runspec), encoding="utf-8")
    latent_path.write_text(json.dumps(latent_runspec), encoding="utf-8")

    report_path = tmp_path / "report.json"
    report = run_ab(c50_path, raw_path, latent_path, out_path=report_path)
    assert "raw" in report and "latent" in report
    assert report["raw"]["sent_count"] > 0
    assert report["latent"]["sent_count"] > 0


