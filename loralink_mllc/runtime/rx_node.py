from __future__ import annotations

from typing import Callable, Sequence

from loralink_mllc.codecs import CodecError, ICodec
from loralink_mllc.config.runspec import RunSpec
from loralink_mllc.protocol.packet import Packet, PacketError
from loralink_mllc.radio.base import IRadio, IRxRssi
from loralink_mllc.runtime.logging import JsonlLogger
from loralink_mllc.runtime.scheduler import Clock, RealClock


class RxNode:
    def __init__(
        self,
        runspec: RunSpec,
        radio: IRadio,
        codec: ICodec,
        logger: JsonlLogger,
        clock: Clock | None = None,
        truth_provider: Callable[[int], Sequence[float] | None] | None = None,
    ) -> None:
        self._runspec = runspec
        self._radio = radio
        self._codec = codec
        self._logger = logger
        self._clock = clock or RealClock()
        self._ack_seq = 0
        self._stop = False
        self._truth_provider = truth_provider
        self._max_payload_bytes = runspec.max_payload_bytes

    def stop(self) -> None:
        self._stop = True

    def _compute_errors(
        self, truth: Sequence[float], recon: Sequence[float]
    ) -> tuple[float, float]:
        if len(truth) != len(recon):
            raise ValueError("truth/recon length mismatch")
        if not truth:
            return 0.0, 0.0
        mae = sum(abs(a - b) for a, b in zip(truth, recon, strict=True)) / len(truth)
        mse = sum((a - b) ** 2 for a, b in zip(truth, recon, strict=True)) / len(truth)
        return mae, mse

    def process_once(self) -> None:
        if self._stop:
            return
        frame = self._radio.recv(timeout_ms=0)
        if frame is None:
            return
        try:
            packet = Packet.from_bytes(frame, max_payload_bytes=self._max_payload_bytes)
        except PacketError as exc:
            self._logger.log_event("rx_parse_fail", {"reason": str(exc)})
            return
        rx_payload: dict[str, object] = {
            "seq": packet.seq,
            "payload_bytes": len(packet.payload),
            "frame_bytes": len(frame),
        }
        if isinstance(self._radio, IRxRssi):
            rssi_dbm = self._radio.last_rx_rssi_dbm()
            if rssi_dbm is not None:
                rx_payload["rssi_dbm"] = rssi_dbm
        self._logger.log_event("rx_ok", rx_payload)
        if self._runspec.mode == "LATENT":
            try:
                recon = self._codec.decode(packet.payload)
                if self._truth_provider:
                    truth = self._truth_provider(packet.seq)
                else:
                    truth = None
                if truth is not None:
                    mae, mse = self._compute_errors(truth, recon)
                    self._logger.log_event(
                        "recon_done",
                        {"seq": packet.seq, "mae": mae, "mse": mse},
                    )
            except NotImplementedError as exc:
                self._logger.log_event(
                    "recon_not_implemented",
                    {"seq": packet.seq, "reason": str(exc)},
                )
            except (CodecError, ValueError) as exc:
                self._logger.log_event("recon_failed", {"seq": packet.seq, "reason": str(exc)})
        ack_packet = Packet(payload=bytes([packet.seq]), seq=self._ack_seq)
        self._radio.send(ack_packet.to_bytes(max_payload_bytes=self._max_payload_bytes))
        self._logger.log_event("ack_sent", {"ack_seq": packet.seq})
        self._ack_seq = (self._ack_seq + 1) % 256

    def run(self, step_ms: int = 5) -> None:
        while not self._stop:
            self.process_once()
            self._clock.sleep_ms(step_ms)


