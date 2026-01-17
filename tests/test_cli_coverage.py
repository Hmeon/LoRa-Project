import json
import runpy
import sys
from pathlib import Path

import pytest

from loralink_mllc.cli import main
from loralink_mllc.codecs.base import payload_schema_hash
from loralink_mllc.config.artifacts import ArtifactsManifest


def _write_runspec(
    tmp_path: Path, *, role: str, mode: str, artifacts_manifest: str | None = None
) -> Path:
    data = {
        "run_id": "cli_test",
        "role": role,
        "mode": mode,
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
        "max_payload_bytes": 238,
    }
    if artifacts_manifest is not None:
        data["artifacts_manifest"] = artifacts_manifest
    path = tmp_path / f"runspec_{role}_{mode}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _write_manifest(tmp_path: Path) -> Path:
    # RawCodec default schema is enough for manifest verification in CLI.
    schema = "raw:int16:le:scale=32767.0"
    manifest = ArtifactsManifest(
        codec_id="raw",
        codec_version="1",
        git_commit=None,
        norm_params_hash=None,
        payload_schema_hash=payload_schema_hash(schema),
        created_at="2020-01-01T00:00:00+00:00",
    )
    path = tmp_path / "artifacts.json"
    manifest.save(path)
    return path


def test_cli_tx_and_rx_with_patched_nodes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import loralink_mllc.cli as cli_mod

    manifest_path = _write_manifest(tmp_path)
    tx_runspec = _write_runspec(tmp_path, role="tx", mode="RAW")
    rx_runspec = _write_runspec(tmp_path, role="rx", mode="RAW")

    class _TxStub:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            return None

        def run(self, step_ms: int) -> None:  # noqa: ARG002
            return None

    class _RxStub:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            return None

        def run(self, step_ms: int, **kwargs) -> None:  # noqa: ARG002
            return None

    monkeypatch.setattr(cli_mod, "TxNode", _TxStub)
    monkeypatch.setattr(cli_mod, "RxNode", _RxStub)

    assert (
        main(
            [
                "tx",
                "--runspec",
                str(tx_runspec),
                "--manifest",
                str(manifest_path),
                "--radio",
                "mock",
                "--sampler",
                "dummy",
                "--step-ms",
                "0",
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "rx",
                "--runspec",
                str(rx_runspec),
                "--manifest",
                str(manifest_path),
                "--radio",
                "mock",
                "--step-ms",
                "0",
            ]
        )
        == 0
    )


def test_cli_keyboardinterrupt_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import loralink_mllc.cli as cli_mod

    manifest_path = _write_manifest(tmp_path)
    tx_runspec = _write_runspec(tmp_path, role="tx", mode="RAW")
    rx_runspec = _write_runspec(tmp_path, role="rx", mode="RAW")

    class _TxStub:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            return None

        def run(self, step_ms: int) -> None:  # noqa: ARG002
            raise KeyboardInterrupt

    class _RxStub:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            return None

        def run(self, step_ms: int, **kwargs) -> None:  # noqa: ARG002
            raise KeyboardInterrupt

    monkeypatch.setattr(cli_mod, "TxNode", _TxStub)
    monkeypatch.setattr(cli_mod, "RxNode", _RxStub)

    assert (
        main(
            [
                "tx",
                "--runspec",
                str(tx_runspec),
                "--manifest",
                str(manifest_path),
                "--radio",
                "mock",
                "--sampler",
                "dummy",
                "--step-ms",
                "0",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "rx",
                "--runspec",
                str(rx_runspec),
                "--manifest",
                str(manifest_path),
                "--radio",
                "mock",
                "--step-ms",
                "0",
            ]
        )
        == 0
    )


def test_cli_load_manifest_from_runspec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import loralink_mllc.cli as cli_mod

    manifest_path = _write_manifest(tmp_path)
    tx_runspec = _write_runspec(
        tmp_path,
        role="tx",
        mode="RAW",
        artifacts_manifest=str(manifest_path),
    )

    class _TxStub:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            return None

        def run(self, step_ms: int) -> None:  # noqa: ARG002
            return None

    monkeypatch.setattr(cli_mod, "TxNode", _TxStub)

    assert (
        main(
            [
                "tx",
                "--runspec",
                str(tx_runspec),
                "--radio",
                "mock",
                "--sampler",
                "dummy",
                "--step-ms",
                "0",
            ]
        )
        == 0
    )


def test_cli_load_manifest_missing_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import loralink_mllc.cli as cli_mod

    tx_runspec = _write_runspec(tmp_path, role="tx", mode="RAW")

    class _TxStub:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            return None

        def run(self, step_ms: int) -> None:  # noqa: ARG002
            return None

    monkeypatch.setattr(cli_mod, "TxNode", _TxStub)
    with pytest.raises(ValueError, match="artifacts manifest path is required"):
        main(["tx", "--runspec", str(tx_runspec)])


def test_cli_tx_requires_sensor_path_for_jsonl_and_csv(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    tx_runspec = _write_runspec(tmp_path, role="tx", mode="RAW")
    with pytest.raises(ValueError, match="--sensor-path is required"):
        main(
            [
                "tx",
                "--runspec",
                str(tx_runspec),
                "--manifest",
                str(manifest_path),
                "--sampler",
                "jsonl",
            ]
        )
    with pytest.raises(ValueError, match="--sensor-path is required"):
        main(
            [
                "tx",
                "--runspec",
                str(tx_runspec),
                "--manifest",
                str(manifest_path),
                "--sampler",
                "csv",
            ]
        )


def test_cli_tx_jsonl_and_csv_sampler_init(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import loralink_mllc.cli as cli_mod

    manifest_path = _write_manifest(tmp_path)
    tx_runspec = _write_runspec(tmp_path, role="tx", mode="RAW")

    jsonl_path = tmp_path / "sensor.jsonl"
    jsonl_path.write_text(
        json.dumps(
            {
                "ts_ms": 1,
                "lat": 1,
                "lon": 2,
                "alt": 3,
                "ax": 4,
                "ay": 5,
                "az": 6,
                "gx": 7,
                "gy": 8,
                "gz": 9,
                "roll": 10,
                "pitch": 11,
                "yaw": 12,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    csv_path = tmp_path / "sensor.csv"
    csv_path.write_text(
        "ts_ms,lat,lon,alt,ax,ay,az,gx,gy,gz,roll,pitch,yaw\n1,1,2,3,4,5,6,7,8,9,10,11,12\n",
        encoding="utf-8",
    )

    class _TxStub:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            return None

        def run(self, step_ms: int) -> None:  # noqa: ARG002
            return None

    monkeypatch.setattr(cli_mod, "TxNode", _TxStub)

    assert (
        main(
            [
                "tx",
                "--runspec",
                str(tx_runspec),
                "--manifest",
                str(manifest_path),
                "--sampler",
                "jsonl",
                "--sensor-path",
                str(jsonl_path),
                "--radio",
                "mock",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "tx",
                "--runspec",
                str(tx_runspec),
                "--manifest",
                str(manifest_path),
                "--sampler",
                "csv",
                "--sensor-path",
                str(csv_path),
                "--radio",
                "mock",
            ]
        )
        == 0
    )


def test_cli_uart_requires_port_and_can_instantiate_when_patched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import loralink_mllc.cli as cli_mod

    manifest_path = _write_manifest(tmp_path)
    rx_runspec = _write_runspec(tmp_path, role="rx", mode="RAW")

    with pytest.raises(ValueError, match="--uart-port is required"):
        main(
            [
                "rx",
                "--runspec",
                str(rx_runspec),
                "--manifest",
                str(manifest_path),
                "--radio",
                "uart",
            ]
        )

    class _RadioStub:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            return None

        def send(self, frame: bytes) -> None:  # pragma: no cover
            return None

        def recv(self, timeout_ms: int):  # pragma: no cover
            return None

        def close(self) -> None:  # pragma: no cover
            return None

    class _RxStub:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            return None

        def run(self, step_ms: int, **kwargs) -> None:  # noqa: ARG002
            return None

    monkeypatch.setattr(cli_mod, "UartE22Radio", _RadioStub)
    monkeypatch.setattr(cli_mod, "RxNode", _RxStub)

    assert (
        main(
            [
                "rx",
                "--runspec",
                str(rx_runspec),
                "--manifest",
                str(manifest_path),
                "--radio",
                "uart",
                "--uart-port",
                "COM1",
                "--uart-baud",
                "9600",
                "--uart-rssi-byte",
            ]
        )
        == 0
    )


def test_cli_tx_uart_requires_port_and_dataset_logger_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import loralink_mllc.cli as cli_mod

    manifest_path = _write_manifest(tmp_path)
    tx_runspec = _write_runspec(tmp_path, role="tx", mode="RAW")

    with pytest.raises(ValueError, match="--uart-port is required"):
        main(
            [
                "tx",
                "--runspec",
                str(tx_runspec),
                "--manifest",
                str(manifest_path),
                "--radio",
                "uart",
            ]
        )

    class _RadioStub:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            return None

        def send(self, frame: bytes) -> None:  # pragma: no cover
            return None

        def recv(self, timeout_ms: int):  # pragma: no cover
            return None

        def close(self) -> None:  # pragma: no cover
            return None

    class _TxStub:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            return None

        def run(self, step_ms: int) -> None:  # noqa: ARG002
            return None

    monkeypatch.setattr(cli_mod, "UartE22Radio", _RadioStub)
    monkeypatch.setattr(cli_mod, "TxNode", _TxStub)

    dataset_path = tmp_path / "dataset.jsonl"
    assert (
        main(
            [
                "tx",
                "--runspec",
                str(tx_runspec),
                "--manifest",
                str(manifest_path),
                "--radio",
                "uart",
                "--uart-port",
                "COM1",
                "--dataset-out",
                str(dataset_path),
                "--step-ms",
                "0",
            ]
        )
        == 0
    )


def test_cli_phase0_phase1_and_metrics(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base_runspec_path = _write_runspec(tmp_path, role="tx", mode="RAW")
    sweep = {
        "base_runspec": json.loads(base_runspec_path.read_text(encoding="utf-8")),
        "profiles": [
            {
                "profile_id": "c50",
                "phy": {
                    "sf": 7,
                    "bw_hz": 125000,
                    "cr": 5,
                    "preamble": 8,
                    "crc_on": True,
                    "explicit_header": True,
                    "tx_power_dbm": 14,
                },
                "drop_pattern_ab": [False, True],
                "drop_pattern_ba": [False],
            }
        ],
        "packets_per_profile": 5,
        "target_pdr_low": 0.0,
        "target_pdr_high": 1.0,
        "out_dir": str(tmp_path),
    }
    sweep_path = tmp_path / "sweep.json"
    c50_path = tmp_path / "c50.json"
    sweep_path.write_text(json.dumps(sweep), encoding="utf-8")

    assert main(["phase0", "--sweep", str(sweep_path), "--out", str(c50_path)]) == 0

    raw_path = _write_runspec(tmp_path, role="tx", mode="RAW")
    latent = json.loads(raw_path.read_text(encoding="utf-8"))
    latent["mode"] = "LATENT"
    latent["run_id"] = "latent"
    latent["codec"] = {"id": "zlib", "version": "1", "params": {"level": 6}}
    latent_path = tmp_path / "latent.json"
    latent_path.write_text(json.dumps(latent), encoding="utf-8")

    report_path = tmp_path / "report.json"
    assert (
        main(
            [
                "phase1",
                "--c50",
                str(c50_path),
                "--raw",
                str(raw_path),
                "--latent",
                str(latent_path),
                "--out",
                str(report_path),
            ]
        )
        == 0
    )

    log_path = tmp_path / "log.jsonl"
    log_path.write_text(json.dumps({"event": "tx_sent", "run_id": "r"}) + "\n", encoding="utf-8")
    assert main(["metrics", "--log", str(log_path)]) == 0
    out = capsys.readouterr().out
    assert "r" in out

    metrics_out = tmp_path / "metrics.json"
    assert main(["metrics", "--log", str(log_path), "--out", str(metrics_out)]) == 0
    assert metrics_out.exists()


def test_cli_main_module_entrypoint_executes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_path = tmp_path / "log.jsonl"
    log_path.write_text(json.dumps({"event": "tx_sent"}) + "\n", encoding="utf-8")
    monkeypatch.delitem(sys.modules, "loralink_mllc.cli", raising=False)
    monkeypatch.setattr(sys, "argv", ["loralink_mllc.cli", "metrics", "--log", str(log_path)])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("loralink_mllc.cli", run_name="__main__")
    assert exc.value.code == 0
