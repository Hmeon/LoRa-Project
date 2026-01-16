from __future__ import annotations

import argparse
import json
from pathlib import Path

from loralink_mllc.codecs import create_codec
from loralink_mllc.config import ArtifactsManifest, load_runspec, verify_manifest
from loralink_mllc.experiments.metrics import compute_metrics, load_events
from loralink_mllc.experiments.phase0_c50 import find_c50
from loralink_mllc.experiments.phase1_ab import run_ab
from loralink_mllc.radio.mock import create_mock_link
from loralink_mllc.radio.uart_e22 import UartE22Radio
from loralink_mllc.runtime.logging import JsonlLogger
from loralink_mllc.runtime.rx_node import RxNode
from loralink_mllc.runtime.scheduler import RealClock
from loralink_mllc.runtime.tx_node import DummySampler, TxNode
from loralink_mllc.sensing import CsvSensorSampler, DatasetLogger, JsonlSensorSampler
from loralink_mllc.sensing.schema import SENSOR_ORDER, SENSOR_UNITS


def _load_manifest(path: str | None, runspec_path: str) -> ArtifactsManifest:
    if path:
        return ArtifactsManifest.load(path)
    spec = load_runspec(runspec_path)
    if spec.artifacts_manifest:
        return ArtifactsManifest.load(spec.artifacts_manifest)
    raise ValueError("artifacts manifest path is required")


def _run_tx(args: argparse.Namespace) -> int:
    runspec = load_runspec(args.runspec)
    manifest = _load_manifest(args.manifest, args.runspec)
    codec = create_codec(runspec.codec)
    verify_manifest(runspec, manifest, codec)
    clock = RealClock()

    if args.sampler == "jsonl":
        if not args.sensor_path:
            raise ValueError("--sensor-path is required for jsonl sampler")
        sampler = JsonlSensorSampler(
            args.sensor_path,
            order=SENSOR_ORDER,
            loop=args.sensor_loop,
            expected_dims=runspec.window.dims,
        )
    elif args.sampler == "csv":
        if not args.sensor_path:
            raise ValueError("--sensor-path is required for csv sampler")
        sampler = CsvSensorSampler(
            args.sensor_path,
            order=SENSOR_ORDER,
            loop=args.sensor_loop,
            expected_dims=runspec.window.dims,
        )
    else:
        sampler = DummySampler(runspec.window.dims)

    if args.radio == "mock":
        link = create_mock_link(loss_rate=args.mock_loss_rate, latency_ms=args.mock_latency_ms)
        radio = link.a
    else:
        if not args.uart_port:
            raise ValueError("--uart-port is required for --radio uart")
        radio = UartE22Radio(
            port=args.uart_port,
            baudrate=args.uart_baud,
            max_payload_bytes=runspec.max_payload_bytes,
            rssi_byte_enabled=args.uart_rssi_byte,
        )

    logger = JsonlLogger(
        runspec.logging.out_dir,
        runspec.run_id,
        runspec.role,
        runspec.mode,
        runspec.phy_id(),
        clock=clock,
    )
    dataset_logger = None
    if args.dataset_out:
        dataset_logger = DatasetLogger(
            args.dataset_out, runspec.run_id, SENSOR_ORDER, units=SENSOR_UNITS
        )
    logger.log_run_start(runspec, manifest)
    node = TxNode(runspec, radio, codec, logger, sampler, dataset_logger, clock=clock)
    node.run(step_ms=args.step_ms)
    if dataset_logger:
        dataset_logger.close()
    logger.close()
    return 0


def _run_rx(args: argparse.Namespace) -> int:
    runspec = load_runspec(args.runspec)
    manifest = _load_manifest(args.manifest, args.runspec)
    codec = create_codec(runspec.codec)
    verify_manifest(runspec, manifest, codec)
    clock = RealClock()

    if args.radio == "mock":
        link = create_mock_link(loss_rate=args.mock_loss_rate, latency_ms=args.mock_latency_ms)
        radio = link.b
    else:
        if not args.uart_port:
            raise ValueError("--uart-port is required for --radio uart")
        radio = UartE22Radio(
            port=args.uart_port,
            baudrate=args.uart_baud,
            max_payload_bytes=runspec.max_payload_bytes,
            rssi_byte_enabled=args.uart_rssi_byte,
        )

    logger = JsonlLogger(
        runspec.logging.out_dir,
        runspec.run_id,
        runspec.role,
        runspec.mode,
        runspec.phy_id(),
        clock=clock,
    )
    logger.log_run_start(runspec, manifest)
    node = RxNode(runspec, radio, codec, logger, clock=clock)
    node.run(step_ms=args.step_ms)
    logger.close()
    return 0


def _run_phase0(args: argparse.Namespace) -> int:
    find_c50(args.sweep, out_path=args.out)
    return 0


def _run_phase1(args: argparse.Namespace) -> int:
    run_ab(args.c50, args.raw, args.latent, out_path=args.out)
    return 0


def _run_metrics(args: argparse.Namespace) -> int:
    events = []
    for path in args.log:
        events.extend(load_events(path))
    grouped: dict[str, list[dict[str, object]]] = {}
    for event in events:
        run_id = str(event.get("run_id", "unknown"))
        grouped.setdefault(run_id, []).append(event)
    report = {run_id: compute_metrics(run_events) for run_id, run_events in grouped.items()}
    output = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="loralink_mllc")
    sub = parser.add_subparsers(dest="cmd", required=True)

    tx = sub.add_parser("tx", help="run TX node")
    tx.add_argument("--runspec", required=True)
    tx.add_argument("--manifest")
    tx.add_argument("--radio", choices=["mock", "uart"], default="mock")
    tx.add_argument("--uart-port")
    tx.add_argument("--uart-baud", type=int, default=9600)
    tx.add_argument(
        "--uart-rssi-byte",
        action="store_true",
        help="expect 1 trailing RSSI byte after each received UART frame (E22 RSSI byte output)",
    )
    tx.add_argument("--mock-loss-rate", type=float, default=0.0)
    tx.add_argument("--mock-latency-ms", type=int, default=0)
    tx.add_argument("--sampler", choices=["dummy", "jsonl", "csv"], default="dummy")
    tx.add_argument("--sensor-path")
    tx.add_argument("--sensor-loop", action="store_true")
    tx.add_argument("--dataset-out")
    tx.add_argument("--step-ms", type=int, default=5)
    tx.set_defaults(func=_run_tx)

    rx = sub.add_parser("rx", help="run RX node")
    rx.add_argument("--runspec", required=True)
    rx.add_argument("--manifest")
    rx.add_argument("--radio", choices=["mock", "uart"], default="mock")
    rx.add_argument("--uart-port")
    rx.add_argument("--uart-baud", type=int, default=9600)
    rx.add_argument(
        "--uart-rssi-byte",
        action="store_true",
        help="expect 1 trailing RSSI byte after each received UART frame (E22 RSSI byte output)",
    )
    rx.add_argument("--mock-loss-rate", type=float, default=0.0)
    rx.add_argument("--mock-latency-ms", type=int, default=0)
    rx.add_argument("--step-ms", type=int, default=5)
    rx.set_defaults(func=_run_rx)

    phase0 = sub.add_parser("phase0", help="run Phase 0 sweep for C50")
    phase0.add_argument("--sweep", required=True)
    phase0.add_argument("--out", required=True)
    phase0.set_defaults(func=_run_phase0)

    phase1 = sub.add_parser("phase1", help="run Phase 1 A/B at C50")
    phase1.add_argument("--c50", required=True)
    phase1.add_argument("--raw", required=True)
    phase1.add_argument("--latent", required=True)
    phase1.add_argument("--out", required=True)
    phase1.set_defaults(func=_run_phase1)

    metrics = sub.add_parser("metrics", help="compute link metrics from JSONL logs")
    metrics.add_argument("--log", action="append", required=True, help="path to a JSONL log")
    metrics.add_argument("--out")
    metrics.set_defaults(func=_run_metrics)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())


