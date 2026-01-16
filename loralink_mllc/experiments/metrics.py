from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


def _to_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("quantile requires non-empty list")
    if q <= 0:
        return float(sorted_values[0])
    if q >= 1:
        return float(sorted_values[-1])
    k = (len(sorted_values) - 1) * q
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return float(sorted_values[f])
    d = k - f
    return float(sorted_values[f] * (1.0 - d) + sorted_values[c] * d)


def _summary_stats(values: List[float]) -> Dict[str, Any] | None:
    if not values:
        return None
    values_sorted = sorted(values)
    total = float(sum(values_sorted))
    count = len(values_sorted)
    return {
        "count": count,
        "min": float(values_sorted[0]),
        "p50": _quantile(values_sorted, 0.5),
        "p90": _quantile(values_sorted, 0.9),
        "max": float(values_sorted[-1]),
        "mean": total / count,
    }


def load_events(path: str | Path) -> List[Dict[str, Any]]:
    path = Path(path)
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def compute_metrics(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    tx_sent = [e for e in events if e.get("event") == "tx_sent"]
    rx_ok = [e for e in events if e.get("event") == "rx_ok"]
    ack_recv = [e for e in events if e.get("event") == "ack_received"]
    tx_failed = [e for e in events if e.get("event") == "tx_failed"]
    rx_parse_fail = [e for e in events if e.get("event") == "rx_parse_fail"]
    ack_sent = [e for e in events if e.get("event") == "ack_sent"]
    recon_done = [e for e in events if e.get("event") == "recon_done"]

    sent_count = len(tx_sent)
    rx_ok_count = len(rx_ok)
    acked_count = len(ack_recv)
    unique_windows_sent: int | None = None
    delivered_windows: int | None = None
    first_attempt_window_ids = {
        e.get("window_id")
        for e in tx_sent
        if _to_int(e.get("attempt")) == 1 and _to_int(e.get("window_id")) is not None
    }
    if first_attempt_window_ids:
        unique_windows_sent = len(first_attempt_window_ids)
    delivered_window_ids = {
        e.get("window_id") for e in ack_recv if _to_int(e.get("window_id")) is not None
    }
    if delivered_window_ids:
        delivered_windows = len(delivered_window_ids)

    if sent_count and rx_ok_count:
        pdr = rx_ok_count / sent_count
    else:
        pdr = acked_count / sent_count if sent_count else 0.0
    etx = sent_count / max(acked_count, 1)

    toa_ms_values: List[float] = []
    payload_bytes_values: List[float] = []
    retries = 0
    for event in tx_sent:
        toa = _to_float(event.get("toa_ms_est"))
        if toa is not None:
            toa_ms_values.append(toa)
        payload_bytes = _to_float(event.get("payload_bytes"))
        if payload_bytes is not None:
            payload_bytes_values.append(payload_bytes)
        attempt = _to_int(event.get("attempt")) or 1
        if attempt > 1:
            retries += 1

    total_toa_ms = float(sum(toa_ms_values))

    rtt_ms_values: List[float] = []
    for event in ack_recv:
        rtt = _to_float(event.get("rtt_ms"))
        if rtt is not None:
            rtt_ms_values.append(rtt)

    rssi_dbm_values: List[float] = []
    for event in (*rx_ok, *ack_recv):
        rssi = _to_float(event.get("rssi_dbm"))
        if rssi is not None:
            rssi_dbm_values.append(rssi)

    recon_mae_values: List[float] = []
    recon_mse_values: List[float] = []
    for event in recon_done:
        mae = _to_float(event.get("mae"))
        mse = _to_float(event.get("mse"))
        if mae is not None:
            recon_mae_values.append(mae)
        if mse is not None:
            recon_mse_values.append(mse)

    return {
        "sent_count": sent_count,
        "acked_count": acked_count,
        "failed_count": len(tx_failed),
        "rx_ok_count": rx_ok_count,
        "rx_parse_fail_count": len(rx_parse_fail),
        "ack_sent_count": len(ack_sent),
        "ack_recv_event_count": len(ack_recv),
        "unique_windows_sent": unique_windows_sent,
        "delivered_windows": delivered_windows,
        "delivery_ratio": (
            (delivered_windows / unique_windows_sent)
            if (delivered_windows is not None and unique_windows_sent)
            else None
        ),
        "retries": retries,
        "pdr": pdr,
        "etx": etx,
        "total_toa_ms": total_toa_ms,
        "toa_ms_est": _summary_stats(toa_ms_values),
        "payload_bytes": _summary_stats(payload_bytes_values),
        "ack_rtt_ms": _summary_stats(rtt_ms_values),
        "rssi_dbm": _summary_stats(rssi_dbm_values),
        "recon_mae": _summary_stats(recon_mae_values),
        "recon_mse": _summary_stats(recon_mse_values),
    }

