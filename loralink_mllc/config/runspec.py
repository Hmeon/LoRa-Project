from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Literal

Role = Literal["tx", "rx"]
Mode = Literal["RAW", "LATENT"]


def _require_keys(data: Dict[str, Any], keys: Iterable[str], context: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"missing {context} keys: {joined}")


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"", "auto", "none", "null"}:
            return None
        if text in {"1", "true", "on", "yes"}:
            return True
        if text in {"0", "false", "off", "no"}:
            return False
    raise ValueError(f"invalid bool value: {value!r}")


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"invalid int value: {value!r}")
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"", "auto", "none", "null"}:
            return None
        return int(text)
    raise ValueError(f"invalid int value: {value!r}")


@dataclass(frozen=True)
class PhySpec:
    sf: int
    bw_hz: int
    cr: int
    preamble: int
    crc_on: bool
    explicit_header: bool
    tx_power_dbm: int
    ldro: bool | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhySpec":
        _require_keys(
            data,
            ["sf", "bw_hz", "cr", "preamble", "crc_on", "explicit_header", "tx_power_dbm"],
            "phy",
        )
        return cls(
            sf=int(data["sf"]),
            bw_hz=int(data["bw_hz"]),
            cr=int(data["cr"]),
            preamble=int(data["preamble"]),
            crc_on=bool(data["crc_on"]),
            explicit_header=bool(data["explicit_header"]),
            tx_power_dbm=int(data["tx_power_dbm"]),
            ldro=_optional_bool(data.get("ldro")),
        )

    def profile_id(self) -> str:
        return (
            f"sf{self.sf}_bw{self.bw_hz}_cr{self.cr}_pre{self.preamble}_"
            f"crc{int(self.crc_on)}_hdr{int(self.explicit_header)}_pwr{self.tx_power_dbm}"
        )


@dataclass(frozen=True)
class WindowSpec:
    dims: int = 12
    W: int = 1
    stride: int = 1
    sample_hz: float = 1.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WindowSpec":
        _require_keys(data, ["W", "sample_hz"], "window")
        return cls(
            dims=int(data.get("dims", 12)),
            W=int(data["W"]),
            stride=int(data.get("stride", 1)),
            sample_hz=float(data["sample_hz"]),
        )


@dataclass(frozen=True)
class CodecSpec:
    id: str
    version: str
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodecSpec":
        _require_keys(data, ["id", "version"], "codec")
        params = data.get("params") or {}
        return cls(id=str(data["id"]), version=str(data["version"]), params=dict(params))


@dataclass(frozen=True)
class TxSpec:
    guard_ms: int
    ack_timeout_ms: int | None
    max_retries: int
    max_inflight: int = 1
    max_windows: int | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TxSpec":
        _require_keys(data, ["guard_ms", "ack_timeout_ms", "max_retries"], "tx")
        ack_timeout_raw = data.get("ack_timeout_ms")
        max_windows_raw = data.get("max_windows")
        return cls(
            guard_ms=int(data["guard_ms"]),
            ack_timeout_ms=_optional_int(ack_timeout_raw),
            max_retries=int(data["max_retries"]),
            max_inflight=int(data.get("max_inflight", 1)),
            max_windows=(int(max_windows_raw) if max_windows_raw is not None else None),
        )


@dataclass(frozen=True)
class LoggingSpec:
    out_dir: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoggingSpec":
        _require_keys(data, ["out_dir"], "logging")
        return cls(out_dir=str(data["out_dir"]))


@dataclass(frozen=True)
class RunSpec:
    run_id: str
    role: Role
    mode: Mode
    phy: PhySpec
    window: WindowSpec
    codec: CodecSpec
    tx: TxSpec
    logging: LoggingSpec
    max_payload_bytes: int = 238
    artifacts_manifest: str | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunSpec":
        _require_keys(
            data,
            ["run_id", "role", "mode", "phy", "window", "codec", "tx", "logging"],
            "runspec",
        )
        return cls(
            run_id=str(data["run_id"]),
            role=data["role"],
            mode=data["mode"],
            phy=PhySpec.from_dict(data["phy"]),
            window=WindowSpec.from_dict(data["window"]),
            codec=CodecSpec.from_dict(data["codec"]),
            tx=TxSpec.from_dict(data["tx"]),
            logging=LoggingSpec.from_dict(data["logging"]),
            max_payload_bytes=int(data.get("max_payload_bytes", 238)),
            artifacts_manifest=data.get("artifacts_manifest"),
        )

    def validate(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if self.role not in ("tx", "rx"):
            raise ValueError(f"invalid role: {self.role}")
        if self.mode not in ("RAW", "LATENT"):
            raise ValueError(f"invalid mode: {self.mode}")
        if self.window.dims <= 0 or self.window.W <= 0:
            raise ValueError("window dims and W must be > 0")
        if self.window.stride <= 0:
            raise ValueError("window stride must be > 0")
        if self.window.sample_hz <= 0:
            raise ValueError("window sample_hz must be > 0")
        if self.phy.sf <= 0 or self.phy.bw_hz <= 0 or self.phy.cr <= 0:
            raise ValueError("phy values must be > 0")
        if self.tx.guard_ms < 0:
            raise ValueError("tx guard_ms must be >=0")
        if self.tx.ack_timeout_ms is not None and self.tx.ack_timeout_ms <= 0:
            raise ValueError("tx ack_timeout_ms must be > 0 (or null/auto)")
        if self.tx.max_retries < 0 or self.tx.max_inflight <= 0:
            raise ValueError("tx retries/inflight must be >= 0")
        if self.max_payload_bytes <= 0 or self.max_payload_bytes > 255:
            raise ValueError("max_payload_bytes must be 1..255")

    def phy_profile_id(self) -> str:
        return self.phy.profile_id()

    def phy_id(self) -> str:
        return self.phy.profile_id()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "role": self.role,
            "mode": self.mode,
            "phy": {
                "sf": self.phy.sf,
                "bw_hz": self.phy.bw_hz,
                "cr": self.phy.cr,
                "preamble": self.phy.preamble,
                "crc_on": self.phy.crc_on,
                "explicit_header": self.phy.explicit_header,
                "tx_power_dbm": self.phy.tx_power_dbm,
                "ldro": self.phy.ldro,
            },
            "window": {
                "dims": self.window.dims,
                "W": self.window.W,
                "stride": self.window.stride,
                "sample_hz": self.window.sample_hz,
            },
            "codec": {
                "id": self.codec.id,
                "version": self.codec.version,
                "params": dict(self.codec.params),
            },
            "tx": {
                "guard_ms": self.tx.guard_ms,
                "ack_timeout_ms": self.tx.ack_timeout_ms,
                "max_retries": self.tx.max_retries,
                "max_inflight": self.tx.max_inflight,
                "max_windows": self.tx.max_windows,
            },
            "logging": {"out_dir": self.logging.out_dir},
            "max_payload_bytes": self.max_payload_bytes,
            "artifacts_manifest": self.artifacts_manifest,
        }


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to load YAML runspecs") from exc
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_runspec(path: str | Path) -> RunSpec:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = _load_yaml(path)
    else:
        data = _load_json(path)
    spec = RunSpec.from_dict(data)
    spec.validate()
    return spec


def save_runspec(path: str | Path, spec: RunSpec) -> None:
    path = Path(path)
    data = spec.as_dict()
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("PyYAML is required to write YAML runspecs") from exc
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

