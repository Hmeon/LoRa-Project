from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from loralink_mllc.codecs.bam_artifacts import BamArtifacts


def _require_numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise SystemExit(
            "numpy is required. Install with `python -m pip install -e .[bam]`."
        ) from exc
    return np


def _resolve(base_dir: Path, path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def _ensure_parent(path: Path) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _write_norm(path: Path, length: int, force: bool) -> None:
    if path.exists() and not force:
        raise SystemExit(f"norm file already exists: {path}")
    _ensure_parent(path)
    data = {"mean": [0.0] * length, "std": [1.0] * length}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_layer(
    path: Path,
    W: Sequence[Sequence[float]],
    V: Sequence[Sequence[float]],
    force: bool,
) -> None:
    if path.exists() and not force:
        raise SystemExit(f"layer file already exists: {path}")
    _ensure_parent(path)
    np = _require_numpy()
    np.savez(path, W=np.asarray(W, dtype=np.float32), V=np.asarray(V, dtype=np.float32))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a toy identity BAM model matching a bam_manifest.json."
    )
    parser.add_argument("--manifest", required=True, help="path to bam_manifest.json")
    parser.add_argument(
        "--force", action="store_true", help="overwrite existing model/norm files"
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        raise SystemExit(f"manifest not found: {manifest_path}")

    artifacts = BamArtifacts.load(manifest_path)
    if artifacts.model_format != "layer_npz_v1":
        raise SystemExit("only model_format layer_npz_v1 is supported by this script")

    base_dir = manifest_path.parent
    model_dir = _resolve(base_dir, artifacts.model_path)
    model_dir.mkdir(parents=True, exist_ok=True)

    input_len = artifacts.expected_input_len()
    latent_dim = artifacts.latent_dim
    min_dim = min(input_len, latent_dim)

    np = _require_numpy()
    W = np.zeros((latent_dim, input_len), dtype=np.float32)
    V = np.zeros((input_len, latent_dim), dtype=np.float32)
    for idx in range(min_dim):
        W[idx, idx] = 1.0
        V[idx, idx] = 1.0

    layer_path = model_dir / "layer_0.npz"
    _write_layer(layer_path, W, V, args.force)

    if artifacts.norm_path:
        norm_path = _resolve(base_dir, artifacts.norm_path)
        _write_norm(norm_path, input_len, args.force)

    print("Wrote toy BAM model:")
    print(f"- layer: {layer_path}")
    if artifacts.norm_path:
        print(f"- norm: {_resolve(base_dir, artifacts.norm_path)}")
    print("Note: this is an identity/truncation baseline, not a trained model.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
