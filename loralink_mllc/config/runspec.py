from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Literal

Role = Literal["tx", "rx", "controller"]
Mode = Literal["RAW", "LATENT"]


@dataclass(frozen=True)
class PhySpec:
    sf: int
    bw_hz: int
    cr: int
    preamble: int
    crc_on: bool
    explicit_header: bool
    tx_power_dbm: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhySpec":
        return cls(
            sf=int(data["sf"]),
            bw_hz=int(data["bw_hz"]),
            cr=int(data["cr"]),
            preamble=int(data["preamble"]),
            crc_on=bool(data["crc_on"]),
            explicit_header=bool(data["explicit_header"]),
            tx_power_dbm=int(data["tx_power_dbm"]),
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
    sample_hz: float = 1.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WindowSpec":
        return cls(
            dims=int(data.get("dims", 12)),
            W=int(data["W"]),
            sample_hz=float(data["sample_hz"]),
        )


@dataclass(frozen=True)
class CodecSpec:
    id: str
    version: str
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodecSpec":
        params = data.get("params") or {}
        return cls(id=str(data["id"]), version=str(data["version"]), params=dict(params))


@dataclass(frozen=True)
class TxSpec:
    guard_ms: int
    ack_timeout_ms: int
    max_retries: int
    max_inflight: int = 1
    max_windows: int | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TxSpec":
        return cls(
            guard_ms=int(data["guard_ms"]),
            ack_timeout_ms=int(data["ack_timeout_ms"]),
            max_retries=int(data["max_retries"]),
            max_inflight=int(data.get("max_inflight", 1)),
            max_windows=(int(data["max_windows"]) if "max_windows" in data else None),
        )


@dataclass(frozen=True)
class LoggingSpec:
    out_dir: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoggingSpec":
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
    artifacts_manifest: str | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunSpec":
        return cls(
            run_id=str(data["run_id"]),
            role=data["role"],
            mode=data["mode"],
            phy=PhySpec.from_dict(data["phy"]),
            window=WindowSpec.from_dict(data["window"]),
            codec=CodecSpec.from_dict(data["codec"]),
            tx=TxSpec.from_dict(data["tx"]),
            logging=LoggingSpec.from_dict(data["logging"]),
            artifacts_manifest=data.get("artifacts_manifest"),
        )

    def validate(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if self.role not in ("tx", "rx", "controller"):
            raise ValueError(f"invalid role: {self.role}")
        if self.mode not in ("RAW", "LATENT"):
            raise ValueError(f"invalid mode: {self.mode}")
        if self.window.dims <= 0 or self.window.W <= 0:
            raise ValueError("window dims and W must be > 0")
        if self.window.sample_hz <= 0:
            raise ValueError("window sample_hz must be > 0")
        if self.phy.sf <= 0 or self.phy.bw_hz <= 0 or self.phy.cr <= 0:
            raise ValueError("phy values must be > 0")
        if self.tx.guard_ms < 0 or self.tx.ack_timeout_ms <= 0:
            raise ValueError("tx guard_ms must be >=0 and ack_timeout_ms > 0")
        if self.tx.max_retries < 0 or self.tx.max_inflight <= 0:
            raise ValueError("tx retries/inflight must be >= 0")

    def phy_profile_id(self) -> str:
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
            },
            "window": {
                "dims": self.window.dims,
                "W": self.window.W,
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

