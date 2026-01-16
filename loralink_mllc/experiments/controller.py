from __future__ import annotations

from loralink_mllc.runtime.rx_node import RxNode
from loralink_mllc.runtime.scheduler import Clock
from loralink_mllc.runtime.tx_node import TxNode


def run_pair(
    tx_node: TxNode,
    rx_node: RxNode,
    clock: Clock,
    step_ms: int = 5,
    max_steps: int = 100000,
) -> None:
    for _ in range(max_steps):
        tx_node.process_once()
        rx_node.process_once()
        if tx_node.is_done():
            break
        clock.sleep_ms(step_ms)


