from __future__ import annotations

import argparse
import dataclasses
import json
import time


@dataclasses.dataclass(frozen=True)
class E22Config:
    addh: int
    addl: int
    netid: int
    reg0: int
    reg1: int
    reg2: int
    reg3: int

    @classmethod
    def from_bytes(cls, data: bytes) -> "E22Config":
        if len(data) != 7:
            raise ValueError("config must be 7 bytes (00H..06H)")
        return cls(*data)

    def to_bytes(self) -> bytes:
        return bytes(
            [
                self.addh & 0xFF,
                self.addl & 0xFF,
                self.netid & 0xFF,
                self.reg0 & 0xFF,
                self.reg1 & 0xFF,
                self.reg2 & 0xFF,
                self.reg3 & 0xFF,
            ]
        )

    def addr(self) -> int:
        return ((self.addh & 0xFF) << 8) | (self.addl & 0xFF)


BAUD_TO_BITS = {
    1200: 0b000,
    2400: 0b001,
    4800: 0b010,
    9600: 0b011,
    19200: 0b100,
    38400: 0b101,
    57600: 0b110,
    115200: 0b111,
}
BITS_TO_BAUD = {v: k for k, v in BAUD_TO_BITS.items()}

PARITY_TO_BITS = {"8N1": 0b00, "8O1": 0b01, "8E1": 0b10}
BITS_TO_PARITY = {v: k for k, v in PARITY_TO_BITS.items()}

AIR_SPEED_TO_BITS = {
    "0.3k": 0b000,
    "1.2k": 0b001,
    "2.4k": 0b010,
    "4.8k": 0b011,
    "9.6k": 0b100,
    "19.2k": 0b101,
    "38.4k": 0b110,
    "62.5k": 0b111,
}
BITS_TO_AIR_SPEED = {v: k for k, v in AIR_SPEED_TO_BITS.items()}

PACKET_SIZE_TO_BITS = {240: 0b00, 128: 0b01, 64: 0b10, 32: 0b11}
BITS_TO_PACKET_SIZE = {v: k for k, v in PACKET_SIZE_TO_BITS.items()}

TX_POWER_TO_BITS = {22: 0b00, 17: 0b01, 13: 0b10, 10: 0b11}
BITS_TO_TX_POWER = {v: k for k, v in TX_POWER_TO_BITS.items()}


def _encode_reg0(*, baud: int, parity: str, air_speed: str) -> int:
    return ((BAUD_TO_BITS[baud] & 0b111) << 5) | ((PARITY_TO_BITS[parity] & 0b11) << 3) | (
        AIR_SPEED_TO_BITS[air_speed] & 0b111
    )


def _decode_reg0(reg0: int) -> tuple[int | None, str | None, str | None]:
    baud_bits = (reg0 >> 5) & 0b111
    parity_bits = (reg0 >> 3) & 0b11
    air_bits = reg0 & 0b111
    return (
        BITS_TO_BAUD.get(baud_bits),
        BITS_TO_PARITY.get(parity_bits),
        BITS_TO_AIR_SPEED.get(air_bits),
    )


REG1_PACKET_SIZE_MASK = 0xC0
REG1_AMBIENT_NOISE_MASK = 0x20
REG1_TX_POWER_MASK = 0x03

REG3_RSSI_BYTE_MASK = 0x80
REG3_TRANSFER_METHOD_MASK = 0x40  # 0=transparent, 1=fixed-point


def _fmt_hex_bytes(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def _parse_int_auto(value: str) -> int:
    return int(value, 0)


def _read_exact(ser, n: int, timeout_s: float) -> bytes:
    deadline = time.monotonic() + max(0.0, timeout_s)
    out = bytearray()
    while len(out) < n and time.monotonic() < deadline:
        chunk = ser.read(n - len(out))
        if chunk:
            out.extend(chunk)
            continue
        time.sleep(0.01)
    return bytes(out)


def read_config(port: str, *, baudrate: int, timeout_s: float = 1.0) -> E22Config:
    import serial  # type: ignore

    cmd = bytes([0xC1, 0x00, 0x07])
    with serial.Serial(port, baudrate, timeout=0.2, write_timeout=0.5) as ser:
        ser.reset_input_buffer()
        ser.write(cmd)
        ser.flush()
        resp = _read_exact(ser, 10, timeout_s=timeout_s)
    if len(resp) != 10 or resp[:3] != cmd:
        raise RuntimeError(f"unexpected read response: {_fmt_hex_bytes(resp)}")
    return E22Config.from_bytes(resp[3:])


def write_config(
    port: str,
    *,
    baudrate: int,
    config: E22Config,
    save: bool,
    timeout_s: float = 1.0,
) -> bytes:
    import serial  # type: ignore

    header = 0xC0 if save else 0xC2
    cmd = bytes([header, 0x00, 0x07]) + config.to_bytes()
    expected_echo = bytes([0xC1, 0x00, 0x07]) + config.to_bytes()
    with serial.Serial(port, baudrate, timeout=0.2, write_timeout=0.5) as ser:
        ser.reset_input_buffer()
        ser.write(cmd)
        ser.flush()
        resp = _read_exact(ser, 10, timeout_s=timeout_s)
    if resp and resp != expected_echo:
        raise RuntimeError(
            "unexpected write echo.\n"
            f"expected: {_fmt_hex_bytes(expected_echo)}\n"
            f"actual:   {_fmt_hex_bytes(resp)}"
        )
    return resp


def read_channel_rssi(port: str, *, baudrate: int, timeout_s: float = 1.0) -> tuple[int, int]:
    """
    Query ambient noise RSSI and the last packet RSSI.

    Command: C0 C1 C2 C3 00 02
    Response: C1 00 02 <noise_rssi> <last_pkt_rssi>

    Values are returned as dBm using the Ebyte convention: rssi_dbm = rssi_byte - 256.
    """
    import serial  # type: ignore

    cmd = bytes([0xC0, 0xC1, 0xC2, 0xC3, 0x00, 0x02])
    with serial.Serial(port, baudrate, timeout=0.2, write_timeout=0.5) as ser:
        ser.reset_input_buffer()
        ser.write(cmd)
        ser.flush()
        resp = _read_exact(ser, 5, timeout_s=timeout_s)
    if len(resp) != 5 or resp[:3] != bytes([0xC1, 0x00, 0x02]):
        raise RuntimeError(f"unexpected RSSI response: {_fmt_hex_bytes(resp)}")
    noise_dbm = int(resp[3]) - 256
    last_pkt_dbm = int(resp[4]) - 256
    return noise_dbm, last_pkt_dbm


def _print_config(cfg: E22Config) -> None:
    baud, parity, air_speed = _decode_reg0(cfg.reg0)
    packet_bits = (cfg.reg1 >> 6) & 0b11
    packet_size = BITS_TO_PACKET_SIZE.get(packet_bits)
    tx_power = BITS_TO_TX_POWER.get(cfg.reg1 & 0b11)
    ambient_noise = bool(cfg.reg1 & REG1_AMBIENT_NOISE_MASK)
    rssi_byte = bool(cfg.reg3 & REG3_RSSI_BYTE_MASK)
    transfer_fixed = bool(cfg.reg3 & REG3_TRANSFER_METHOD_MASK)

    freq_mhz = 850.125 + (cfg.reg2 & 0xFF) * 1.0

    print("E22 config (00H..06H):")
    print(f"- addr:    0x{cfg.addr():04X} (ADDH=0x{cfg.addh:02X}, ADDL=0x{cfg.addl:02X})")
    print(f"- netid:   0x{cfg.netid:02X}")
    print(f"- reg0:    0x{cfg.reg0:02X} (uart={baud}bps, parity={parity}, air_speed={air_speed})")
    print(
        f"- reg1:    0x{cfg.reg1:02X} (packet_size={packet_size}, tx_power_dbm={tx_power}, "
        f"ambient_noise={ambient_noise})"
    )
    print(f"- reg2:    0x{cfg.reg2:02X} (channel={cfg.reg2}, freq={freq_mhz:.3f} MHz)")
    print(
        f"- reg3:    0x{cfg.reg3:02X} (rssi_byte={rssi_byte}, "
        f"transfer={'fixed' if transfer_fixed else 'transparent'})"
    )


def _apply_updates(cfg: E22Config, *, args: argparse.Namespace) -> E22Config:
    addh, addl = cfg.addh, cfg.addl
    netid = cfg.netid
    reg0, reg1, reg2, reg3 = cfg.reg0, cfg.reg1, cfg.reg2, cfg.reg3

    if args.addr is not None:
        addr = int(args.addr) & 0xFFFF
        addh, addl = (addr >> 8) & 0xFF, addr & 0xFF
    if args.netid is not None:
        netid = int(args.netid) & 0xFF
    if args.channel is not None:
        reg2 = int(args.channel) & 0xFF

    if args.uart_baud is not None or args.uart_parity is not None or args.air_speed is not None:
        cur_baud, cur_parity, cur_air = _decode_reg0(reg0)
        baud = int(args.uart_baud) if args.uart_baud is not None else int(cur_baud or 9600)
        parity = args.uart_parity if args.uart_parity is not None else str(cur_parity or "8N1")
        air = args.air_speed if args.air_speed is not None else str(cur_air or "2.4k")
        reg0 = _encode_reg0(baud=baud, parity=parity, air_speed=air)

    if args.packet_size is not None:
        reg1 = (reg1 & ~REG1_PACKET_SIZE_MASK) | (
            (PACKET_SIZE_TO_BITS[int(args.packet_size)] & 0b11) << 6
        )
    if args.tx_power_dbm is not None:
        reg1 = (reg1 & ~REG1_TX_POWER_MASK) | (TX_POWER_TO_BITS[int(args.tx_power_dbm)] & 0b11)
    if args.ambient_noise is not None:
        if args.ambient_noise:
            reg1 |= REG1_AMBIENT_NOISE_MASK
        else:
            reg1 &= ~REG1_AMBIENT_NOISE_MASK

    if args.rssi_byte is not None:
        if args.rssi_byte:
            reg3 |= REG3_RSSI_BYTE_MASK
        else:
            reg3 &= ~REG3_RSSI_BYTE_MASK
    if args.transfer_method is not None:
        if args.transfer_method == "fixed":
            reg3 |= REG3_TRANSFER_METHOD_MASK
        else:
            reg3 &= ~REG3_TRANSFER_METHOD_MASK

    return E22Config(
        addh=addh,
        addl=addl,
        netid=netid,
        reg0=reg0,
        reg1=reg1,
        reg2=reg2,
        reg3=reg3,
    )


def _add_common_serial_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--port",
        required=True,
        help="UART serial port (e.g., /dev/ttyAMA0 or COM3)",
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=9600,
        help="baudrate for the PC<->module config UART (default: 9600)",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="e22_tool",
        description="E22 UART configuration helper (read/modify 00H..06H).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    read_p = sub.add_parser("read", help="read and print current config")
    _add_common_serial_args(read_p)

    rssi_p = sub.add_parser("rssi", help="query ambient noise and last-packet RSSI")
    _add_common_serial_args(rssi_p)
    rssi_p.add_argument("--json", action="store_true", help="print as JSON")

    set_p = sub.add_parser("set", help="update selected fields (read-modify-write)")
    _add_common_serial_args(set_p)
    set_p.add_argument(
        "--save",
        action="store_true",
        help="persist settings (0xC0). Default is temp (0xC2).",
    )
    set_p.add_argument("--verify", action="store_true", help="re-read and print after write")

    set_p.add_argument("--addr", type=_parse_int_auto, help="module address (e.g., 0x0000)")
    set_p.add_argument("--netid", type=_parse_int_auto, help="NETID (e.g., 0x00)")
    set_p.add_argument("--channel", type=_parse_int_auto, help="channel byte (e.g., 0x32)")

    set_p.add_argument("--uart-baud", type=int, choices=sorted(BAUD_TO_BITS.keys()))
    set_p.add_argument("--uart-parity", choices=sorted(PARITY_TO_BITS.keys()))
    set_p.add_argument("--air-speed", choices=sorted(AIR_SPEED_TO_BITS.keys()))

    set_p.add_argument("--packet-size", type=int, choices=sorted(PACKET_SIZE_TO_BITS.keys()))
    set_p.add_argument("--tx-power-dbm", type=int, choices=sorted(TX_POWER_TO_BITS.keys()))
    set_p.add_argument(
        "--ambient-noise",
        type=lambda x: x.lower() in {"1", "true", "yes", "on"},
        help="set REG1 ambient noise bit (true/false). Example: --ambient-noise true",
    )
    set_p.add_argument(
        "--rssi-byte",
        type=lambda x: x.lower() in {"1", "true", "yes", "on"},
        help="set REG3 RSSI byte output (true/false). Example: --rssi-byte true",
    )
    set_p.add_argument("--transfer-method", choices=["transparent", "fixed"])

    args = parser.parse_args(argv)

    if args.cmd == "read":
        cfg = read_config(args.port, baudrate=args.rate)
        _print_config(cfg)
        return 0

    if args.cmd == "rssi":
        noise_dbm, last_pkt_dbm = read_channel_rssi(args.port, baudrate=args.rate)
        if args.json:
            print(
                json.dumps({"noise_dbm": noise_dbm, "last_packet_dbm": last_pkt_dbm})
            )
        else:
            print("E22 channel RSSI:")
            print(f"- noise_dbm:       {noise_dbm}")
            print(f"- last_packet_dbm: {last_pkt_dbm}")
        return 0

    if args.cmd == "set":
        if not args.save:
            print("NOTE: writing in TEMP mode (0xC2). Use --save to persist (0xC0).")
        cfg = read_config(args.port, baudrate=args.rate)
        updated = _apply_updates(cfg, args=args)
        if updated == cfg:
            print("No changes requested; nothing to write.")
            _print_config(cfg)
            return 0
        print("Before:")
        _print_config(cfg)
        write_config(args.port, baudrate=args.rate, config=updated, save=bool(args.save))
        print("After (written):")
        _print_config(updated)
        if args.verify:
            print("After (re-read):")
            reread = read_config(args.port, baudrate=args.rate)
            _print_config(reread)
        return 0

    raise RuntimeError(f"unknown cmd: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
