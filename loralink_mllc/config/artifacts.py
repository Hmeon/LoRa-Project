from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from loralink_mllc.codecs.base import ICodec, payload_schema_hash
from loralink_mllc.config.runspec import RunSpec


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: str | Path) -> str:
    path = Path(path)
    return _sha256_bytes(path.read_bytes())


def current_git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


@dataclass(frozen=True)
class ArtifactsManifest:
    codec_id: str
    codec_version: str
    git_commit: str | None
    norm_params_hash: str | None
    payload_schema_hash: str
    created_at: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactsManifest":
        return cls(
            codec_id=str(data["codec_id"]),
            codec_version=str(data["codec_version"]),
            git_commit=data.get("git_commit"),
            norm_params_hash=data.get("norm_params_hash"),
            payload_schema_hash=str(data["payload_schema_hash"]),
            created_at=str(data["created_at"]),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "codec_id": self.codec_id,
            "codec_version": self.codec_version,
            "git_commit": self.git_commit,
            "norm_params_hash": self.norm_params_hash,
            "payload_schema_hash": self.payload_schema_hash,
            "created_at": self.created_at,
        }

    def fingerprint(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True).encode("utf-8")
        return _sha256_bytes(payload)

    @classmethod
    def create(
        cls,
        codec_id: str,
        codec_version: str,
        payload_schema_hash: str,
        norm_params_hash: str | None = None,
        git_commit: str | None = None,
    ) -> "ArtifactsManifest":
        if git_commit is None:
            git_commit = current_git_commit()
        created_at = datetime.now(timezone.utc).isoformat()
        return cls(
            codec_id=codec_id,
            codec_version=codec_version,
            git_commit=git_commit,
            norm_params_hash=norm_params_hash,
            payload_schema_hash=payload_schema_hash,
            created_at=created_at,
        )

    @classmethod
    def load(cls, path: str | Path) -> "ArtifactsManifest":
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.write_text(json.dumps(self.as_dict(), indent=2), encoding="utf-8")


def verify_manifest(runspec: RunSpec, manifest: ArtifactsManifest, codec: ICodec) -> None:
    if manifest.codec_id != runspec.codec.id:
        raise ValueError("manifest codec_id does not match runspec codec.id")
    if manifest.codec_version != runspec.codec.version:
        raise ValueError("manifest codec_version does not match runspec codec.version")
    schema_hash = payload_schema_hash(codec.payload_schema())
    if manifest.payload_schema_hash != schema_hash:
        raise ValueError("manifest payload_schema_hash does not match codec schema")
    norm_path = runspec.codec.params.get("norm_path") if runspec.codec.params else None
    if manifest.norm_params_hash and norm_path:
        actual = hash_file(norm_path)
        if actual != manifest.norm_params_hash:
            raise ValueError("norm_params_hash does not match norm file")


