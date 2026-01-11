from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


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
    ack_recv = [e for e in events if e.get("event") == "ack_received"]
    tx_failed = [e for e in events if e.get("event") == "tx_failed"]
    sent_count = len(tx_sent)
    acked_count = len(ack_recv)
    pdr = acked_count / sent_count if sent_count else 0.0
    etx = sent_count / max(acked_count, 1)
    total_toa_ms = sum(e.get("toa_ms_est", 0.0) for e in tx_sent)
    return {
        "sent_count": sent_count,
        "acked_count": acked_count,
        "failed_count": len(tx_failed),
        "pdr": pdr,
        "etx": etx,
        "total_toa_ms": total_toa_ms,
    }

