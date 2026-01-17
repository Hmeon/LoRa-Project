import builtins
import json
from pathlib import Path

import pytest

from loralink_mllc.codecs.bam import BamCodec, _parse_layer_index, _require_numpy
from loralink_mllc.codecs.bam_artifacts import BamArtifacts
from loralink_mllc.codecs.base import CodecError


def _write_layer_npz(path: Path, *, W, V) -> None:  # type: ignore[no-untyped-def]
    np = pytest.importorskip("numpy")
    np.savez(path, W=W, V=V)


def _artifacts(
    *,
    model_path: str,
    model_format: str = "layer_npz_v1",
    latent_dim: int = 2,
    packing: str = "float32",
    input_dims: int = 2,
    window_W: int = 1,
    window_stride: int = 1,
    scale: float | None = None,
    delta: float | None = None,
    encode_cycles: int = 0,
    decode_cycles: int = 0,
    norm_path: str | None = None,
) -> BamArtifacts:
    return BamArtifacts(
        manifest_version="1",
        model_format=model_format,
        model_path=model_path,
        latent_dim=latent_dim,
        packing=packing,
        scale=scale,
        delta=delta,
        encode_cycles=encode_cycles,
        decode_cycles=decode_cycles,
        input_dims=input_dims,
        window_W=window_W,
        window_stride=window_stride,
        norm_path=norm_path,
        notes=None,
    )


def _make_identity_model(tmp_path: Path, *, name: str = "model") -> Path:
    np = pytest.importorskip("numpy")
    model_dir = tmp_path / name
    model_dir.mkdir()
    _write_layer_npz(
        model_dir / "layer_0.npz",
        W=np.eye(2, dtype=np.float32),
        V=np.eye(2, dtype=np.float32),
    )
    return model_dir


def test_require_numpy_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
        if name == "numpy":
            raise ImportError("no numpy")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(CodecError, match="requires numpy"):
        _require_numpy()


def test_parse_layer_index_invalid_filename() -> None:
    with pytest.raises(CodecError, match="invalid layer filename"):
        _parse_layer_index(Path("not_a_layer.npz"))


def test_validate_dynamics_rejects_negative_cycles(tmp_path: Path) -> None:
    with pytest.raises(CodecError, match="encode_cycles"):
        BamCodec(_artifacts(model_path=".", encode_cycles=-1), base_dir=tmp_path)


def test_validate_dynamics_rejects_delta_ge_0_5_with_cycles(tmp_path: Path) -> None:
    with pytest.raises(CodecError, match="delta must be < 0.5"):
        BamCodec(_artifacts(model_path=".", delta=0.5, encode_cycles=1), base_dir=tmp_path)


def test_resolve_path_absolute(tmp_path: Path) -> None:
    model_dir = _make_identity_model(tmp_path)
    codec = BamCodec(_artifacts(model_path=model_dir.name), base_dir=tmp_path)
    assert codec._resolve_path(str(tmp_path)).is_absolute()


def test_load_layers_error_model_format(tmp_path: Path) -> None:
    with pytest.raises(CodecError, match="unsupported bam model_format"):
        BamCodec(_artifacts(model_path=".", model_format="nope"), base_dir=tmp_path)


def test_load_layers_error_model_path_missing(tmp_path: Path) -> None:
    with pytest.raises(CodecError, match="model_path does not exist"):
        BamCodec(_artifacts(model_path="missing_dir"), base_dir=tmp_path)


def test_load_layers_error_model_path_not_dir(tmp_path: Path) -> None:
    file_path = tmp_path / "model.bin"
    file_path.write_bytes(b"x")
    with pytest.raises(CodecError, match="requires model_path to be a directory"):
        BamCodec(_artifacts(model_path=file_path.name), base_dir=tmp_path)


def test_load_layers_error_no_layers_found(tmp_path: Path) -> None:
    empty_dir = tmp_path / "model"
    empty_dir.mkdir()
    with pytest.raises(CodecError, match="no layer_\\*\\.npz files found"):
        BamCodec(_artifacts(model_path=empty_dir.name), base_dir=tmp_path)


def test_load_layers_error_invalid_layer_filename(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "layer_bad.npz").write_bytes(b"not a zip")
    with pytest.raises(CodecError, match="invalid layer filename"):
        BamCodec(_artifacts(model_path=model_dir.name), base_dir=tmp_path)


def test_load_layers_error_missing_W_or_V(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    np.savez(model_dir / "layer_0.npz", W=np.eye(2, dtype=np.float32))
    with pytest.raises(CodecError, match="missing W/V"):
        BamCodec(_artifacts(model_path=model_dir.name), base_dir=tmp_path)


def test_load_layers_error_weights_not_2d(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    W = np.zeros((2, 2, 1), dtype=np.float32)
    V = np.zeros((2, 2, 1), dtype=np.float32)
    _write_layer_npz(model_dir / "layer_0.npz", W=W, V=V)
    with pytest.raises(CodecError, match="must be 2D"):
        BamCodec(_artifacts(model_path=model_dir.name), base_dir=tmp_path)


def test_load_layers_error_V_shape_mismatch(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    W = np.eye(2, dtype=np.float32)
    V = np.zeros((2, 3), dtype=np.float32)
    _write_layer_npz(model_dir / "layer_0.npz", W=W, V=V)
    with pytest.raises(CodecError, match="V shape mismatch"):
        BamCodec(_artifacts(model_path=model_dir.name), base_dir=tmp_path)


def test_load_layers_error_input_dim_mismatch_expected(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    W = np.zeros((2, 3), dtype=np.float32)
    V = np.zeros((3, 2), dtype=np.float32)
    _write_layer_npz(model_dir / "layer_0.npz", W=W, V=V)
    with pytest.raises(CodecError, match="does not match expected"):
        BamCodec(
            _artifacts(model_path=model_dir.name, input_dims=2, window_W=1, latent_dim=2),
            base_dir=tmp_path,
        )


def test_load_layers_error_input_dim_mismatch_previous(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    _write_layer_npz(
        model_dir / "layer_0.npz",
        W=np.eye(2, dtype=np.float32),
        V=np.eye(2, dtype=np.float32),
    )
    W1 = np.zeros((2, 3), dtype=np.float32)
    V1 = np.zeros((3, 2), dtype=np.float32)
    _write_layer_npz(model_dir / "layer_1.npz", W=W1, V=V1)
    with pytest.raises(CodecError, match="does not match previous"):
        BamCodec(
            _artifacts(model_path=model_dir.name, input_dims=2, window_W=1, latent_dim=2),
            base_dir=tmp_path,
        )


def test_load_layers_error_latent_dim_mismatch(tmp_path: Path) -> None:
    model_dir = _make_identity_model(tmp_path)
    with pytest.raises(CodecError, match="latent_dim"):
        BamCodec(_artifacts(model_path=model_dir.name, latent_dim=3), base_dir=tmp_path)


def test_load_norm_error_branches(tmp_path: Path) -> None:
    model_dir = _make_identity_model(tmp_path)

    with pytest.raises(CodecError, match="norm_path does not exist"):
        BamCodec(_artifacts(model_path=model_dir.name, norm_path="missing.json"), base_dir=tmp_path)

    norm_path = tmp_path / "norm.json"
    norm_path.write_text(json.dumps({"mean": [0.0]}), encoding="utf-8")
    with pytest.raises(CodecError, match="must contain mean and std"):
        BamCodec(_artifacts(model_path=model_dir.name, norm_path=norm_path.name), base_dir=tmp_path)

    norm_path.write_text(json.dumps({"mean": "x", "std": "y"}), encoding="utf-8")
    with pytest.raises(CodecError, match="must be lists"):
        BamCodec(_artifacts(model_path=model_dir.name, norm_path=norm_path.name), base_dir=tmp_path)

    norm_path.write_text(json.dumps({"mean": [0.0], "std": [1.0, 2.0]}), encoding="utf-8")
    with pytest.raises(CodecError, match="length does not match"):
        BamCodec(_artifacts(model_path=model_dir.name, norm_path=norm_path.name), base_dir=tmp_path)

    norm_path.write_text(json.dumps({"mean": [0.0, 0.0], "std": [-1.0, 1.0]}), encoding="utf-8")
    with pytest.raises(CodecError, match="non-negative"):
        BamCodec(_artifacts(model_path=model_dir.name, norm_path=norm_path.name), base_dir=tmp_path)


def test_norm_apply_and_invert_and_shape_mismatch(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    model_dir = _make_identity_model(tmp_path)
    norm_path = tmp_path / "norm.json"
    norm_path.write_text(json.dumps({"mean": [1.0, 2.0], "std": [0.0, 2.0]}), encoding="utf-8")
    codec = BamCodec(
        _artifacts(model_path=model_dir.name, norm_path=norm_path.name),
        base_dir=tmp_path,
    )

    vec = np.asarray([1.0, 6.0], dtype=np.float32)
    normed = codec._apply_norm(vec)
    assert normed.tolist() == [0.0, 2.0]
    inv = codec._invert_norm(normed)
    assert inv.tolist() == [1.0, 6.0]

    with pytest.raises(CodecError, match="norm input length mismatch"):
        codec._apply_norm(np.asarray([1.0], dtype=np.float32))
    with pytest.raises(CodecError, match="norm input length mismatch"):
        codec._invert_norm(np.asarray([1.0], dtype=np.float32))


def test_require_scale_missing_and_nonpositive(tmp_path: Path) -> None:
    model_dir = _make_identity_model(tmp_path)
    codec = BamCodec(_artifacts(model_path=model_dir.name, packing="int8"), base_dir=tmp_path)
    with pytest.raises(CodecError, match="requires scale"):
        codec.encode([0.0, 0.0])

    codec = BamCodec(
        _artifacts(model_path=model_dir.name, packing="int8", scale=0.0),
        base_dir=tmp_path,
    )
    with pytest.raises(CodecError, match="scale must be positive"):
        codec.encode([0.0, 0.0])


def test_pack_length_mismatch(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    model_dir = _make_identity_model(tmp_path)
    codec = BamCodec(
        _artifacts(model_path=model_dir.name, packing="int16", scale=10.0),
        base_dir=tmp_path,
    )
    with pytest.raises(CodecError, match="latent vector length"):
        codec._pack(np.asarray([0.0, 0.0, 0.0], dtype=np.float32))


@pytest.mark.parametrize(
    ("packing", "payload", "scale"),
    [
        ("int8", b"\x00", 1.0),
        ("int16", b"\x00\x00", 1.0),
        ("float16", b"\x00\x00", None),
        ("float32", b"\x00\x00\x00\x00", None),
    ],
)
def test_unpack_length_mismatch_per_dtype(
    tmp_path: Path, packing: str, payload: bytes, scale: float | None
) -> None:
    model_dir = _make_identity_model(tmp_path, name=f"model_{packing}")
    codec = BamCodec(
        _artifacts(model_path=model_dir.name, packing=packing, scale=scale),
        base_dir=tmp_path,
    )
    with pytest.raises(CodecError, match="payload latent length mismatch"):
        codec._unpack(payload)


def test_unknown_packing_encode_decode_and_payload_schema(tmp_path: Path) -> None:
    model_dir = _make_identity_model(tmp_path)
    codec = BamCodec(_artifacts(model_path=model_dir.name, packing="nope"), base_dir=tmp_path)
    with pytest.raises(CodecError, match="unsupported bam packing"):
        codec.encode([0.0, 0.0])
    with pytest.raises(CodecError, match="unsupported bam packing"):
        codec.decode(b"")
    assert "scale=none" in codec.payload_schema()


def test_float16_packing_roundtrip(tmp_path: Path) -> None:
    model_dir = _make_identity_model(tmp_path)
    codec = BamCodec(_artifacts(model_path=model_dir.name, packing="float16"), base_dir=tmp_path)
    payload = codec.encode([0.5, -0.25])
    assert len(payload) == 4
    decoded = codec.decode(payload)
    assert decoded == pytest.approx([0.5, -0.25], abs=1e-3)
