import builtins
import json
from pathlib import Path

import pytest

from loralink_mllc.config.runspec import RunSpec, load_runspec, save_runspec


def _install_yaml_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
        if name == "yaml":
            raise ImportError("yaml disabled for test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def _base_runspec_dict(tmp_path: Path) -> dict:
    return {
        "run_id": "x",
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
        "window": {"dims": 12, "W": 1, "stride": 1, "sample_hz": 1.0},
        "codec": {"id": "raw", "version": "1", "params": {}},
        "tx": {"guard_ms": 0, "ack_timeout_ms": 10, "max_retries": 0, "max_inflight": 1},
        "logging": {"out_dir": str(tmp_path)},
        "max_payload_bytes": 238,
    }


def test_runspec_require_keys_raises(tmp_path: Path) -> None:
    data = _base_runspec_dict(tmp_path)
    del data["phy"]
    with pytest.raises(ValueError, match="missing runspec keys"):
        RunSpec.from_dict(data)


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda d: d.update(run_id=""), "run_id must be non-empty"),
        (lambda d: d.update(role="nope"), "invalid role"),
        (lambda d: d.update(mode="nope"), "invalid mode"),
        (lambda d: d["window"].update(dims=0), "window dims and W"),
        (lambda d: d["window"].update(W=0), "window dims and W"),
        (lambda d: d["window"].update(stride=0), "window stride"),
        (lambda d: d["window"].update(sample_hz=0), "window sample_hz"),
        (lambda d: d["phy"].update(sf=0), "phy values must be > 0"),
        (lambda d: d["phy"].update(bw_hz=0), "phy values must be > 0"),
        (lambda d: d["phy"].update(cr=0), "phy values must be > 0"),
        (lambda d: d["tx"].update(guard_ms=-1), "guard_ms must be"),
        (lambda d: d["tx"].update(ack_timeout_ms=0), "ack_timeout_ms"),
        (lambda d: d["tx"].update(max_retries=-1), "retries/inflight"),
        (lambda d: d["tx"].update(max_inflight=0), "retries/inflight"),
        (lambda d: d.update(max_payload_bytes=0), "max_payload_bytes"),
        (lambda d: d.update(max_payload_bytes=256), "max_payload_bytes"),
    ],
)
def test_runspec_validate_error_branches(
    tmp_path: Path, mutator, match: str  # type: ignore[no-untyped-def]
) -> None:
    data = _base_runspec_dict(tmp_path)
    mutator(data)
    spec = RunSpec.from_dict(data)
    with pytest.raises(ValueError, match=match):
        spec.validate()


def test_load_runspec_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_runspec(tmp_path / "missing.json")


def test_save_and_load_runspec_json_and_yaml(tmp_path: Path) -> None:
    spec = RunSpec.from_dict(_base_runspec_dict(tmp_path))
    spec.validate()

    json_path = tmp_path / "runspec.json"
    save_runspec(json_path, spec)
    assert load_runspec(json_path) == spec

    yaml_path = tmp_path / "runspec.yaml"
    save_runspec(yaml_path, spec)
    assert load_runspec(yaml_path) == spec


def test_load_runspec_yaml_requires_pyyaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = tmp_path / "runspec.yaml"
    yaml_path.write_text("run_id: x\n", encoding="utf-8")
    _install_yaml_import_error(monkeypatch)
    with pytest.raises(RuntimeError, match="PyYAML is required to load YAML runspecs"):
        load_runspec(yaml_path)


def test_save_runspec_yaml_requires_pyyaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = RunSpec.from_dict(_base_runspec_dict(tmp_path))
    spec.validate()
    yaml_path = tmp_path / "runspec.yaml"
    _install_yaml_import_error(monkeypatch)
    with pytest.raises(RuntimeError, match="PyYAML is required to write YAML runspecs"):
        save_runspec(yaml_path, spec)


def test_runspec_as_dict_smoke(tmp_path: Path) -> None:
    spec = RunSpec.from_dict(_base_runspec_dict(tmp_path))
    spec.validate()
    data = spec.as_dict()
    assert json.loads(json.dumps(data))["run_id"] == "x"


def test_runspec_phy_ldro_parsing(tmp_path: Path) -> None:
    data_bool = _base_runspec_dict(tmp_path)
    data_bool["phy"]["ldro"] = True
    assert RunSpec.from_dict(data_bool).phy.ldro is True

    data_on = _base_runspec_dict(tmp_path)
    data_on["phy"]["ldro"] = "on"
    assert RunSpec.from_dict(data_on).phy.ldro is True

    data_off = _base_runspec_dict(tmp_path)
    data_off["phy"]["ldro"] = "off"
    assert RunSpec.from_dict(data_off).phy.ldro is False

    data_auto = _base_runspec_dict(tmp_path)
    data_auto["phy"]["ldro"] = "auto"
    assert RunSpec.from_dict(data_auto).phy.ldro is None

    data_int = _base_runspec_dict(tmp_path)
    data_int["phy"]["ldro"] = 1
    assert RunSpec.from_dict(data_int).phy.ldro is True

    data_bad = _base_runspec_dict(tmp_path)
    data_bad["phy"]["ldro"] = "maybe"
    with pytest.raises(ValueError, match="invalid bool value"):
        RunSpec.from_dict(data_bad)


def test_runspec_tx_ack_timeout_parsing(tmp_path: Path) -> None:
    data_auto = _base_runspec_dict(tmp_path)
    data_auto["tx"]["ack_timeout_ms"] = "auto"
    spec_auto = RunSpec.from_dict(data_auto)
    assert spec_auto.tx.ack_timeout_ms is None
    spec_auto.validate()

    data_none = _base_runspec_dict(tmp_path)
    data_none["tx"]["ack_timeout_ms"] = None
    spec_none = RunSpec.from_dict(data_none)
    assert spec_none.tx.ack_timeout_ms is None
    spec_none.validate()

    data_str = _base_runspec_dict(tmp_path)
    data_str["tx"]["ack_timeout_ms"] = "123"
    assert RunSpec.from_dict(data_str).tx.ack_timeout_ms == 123

    data_float = _base_runspec_dict(tmp_path)
    data_float["tx"]["ack_timeout_ms"] = 12.7
    assert RunSpec.from_dict(data_float).tx.ack_timeout_ms == 12

    data_bad = _base_runspec_dict(tmp_path)
    data_bad["tx"]["ack_timeout_ms"] = True
    with pytest.raises(ValueError, match="invalid int value"):
        RunSpec.from_dict(data_bad)

    data_bad2 = _base_runspec_dict(tmp_path)
    data_bad2["tx"]["ack_timeout_ms"] = object()
    with pytest.raises(ValueError, match="invalid int value"):
        RunSpec.from_dict(data_bad2)


def test_runspec_phy_profile_id(tmp_path: Path) -> None:
    spec = RunSpec.from_dict(_base_runspec_dict(tmp_path))
    spec.validate()
    assert spec.phy_profile_id() == spec.phy_id()
