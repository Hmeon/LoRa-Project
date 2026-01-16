from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def _require_pyserial():
    try:
        import serial  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "pyserial is required. Install with `python -m pip install -e .[uart]`."
        ) from exc
    return serial


def _add_timestamp(payload: dict) -> dict:
    if "ts_ms" in payload or "ts" in payload or "timestamp" in payload:
        return payload
    payload["ts_ms"] = int(time.time() * 1000)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture newline-delimited JSON from serial and write JSONL."
    )
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--out", required=True, help="output JSONL path")
    parser.add_argument("--duration-s", type=float, default=0.0, help="0 means no limit")
    parser.add_argument("--max-lines", type=int, default=0, help="0 means no limit")
    parser.add_argument("--timeout-s", type=float, default=1.0)
    args = parser.parse_args()

    serial = _require_pyserial()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with serial.Serial(args.port, args.baud, timeout=args.timeout_s) as ser:
        with out_path.open("a", encoding="utf-8") as fh:
            start = time.time()
            written = 0
            while True:
                if args.duration_s > 0 and time.time() - start >= args.duration_s:
                    break
                if args.max_lines > 0 and written >= args.max_lines:
                    break
                raw = ser.readline()
                if not raw:
                    continue
                try:
                    text = raw.decode("utf-8", errors="ignore").strip()
                except Exception:
                    continue
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                payload = _add_timestamp(payload)
                fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
                fh.flush()
                written += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
