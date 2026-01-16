# BAM Codec Artifacts

This document defines the artifact contract for BAM inference in this repo.
It does not describe training. Model weights must be supplied out-of-tree.

## Supported model formats

### layer_npz_v1
- `model_path` points to a directory containing `layer_0.npz`, `layer_1.npz`, ...
- Each layer file must contain:
  - `W`: float array, shape `(out_dim, in_dim)` for forward mapping
  - `V`: float array, shape `(in_dim, out_dim)` for reverse mapping
- Layer chaining rules:
  - `layer_0.W.shape[1] == input_dims * window_W`
  - `layer_i.W.shape[1] == layer_(i-1).W.shape[0]`
  - `latent_dim == last_layer.W.shape[0]`
- Paths in the manifest are resolved relative to the manifest location.

## Transmission function
If `delta` is provided in the manifest, inference applies the cubic transmission:
```
f(a) = (delta + 1) * a - delta * a^3
```
after each matrix multiply. The output is clipped to `[-1, 1]` to match the bounded
continuous-valued regime used in the reference implementation and paper notes.

If `delta` is omitted (or `delta` is `0`), inference is linear.

## Normalization (optional)
`norm_path` points to a JSON file:
```json
{
  "mean": [0.0, 0.0],
  "std": [1.0, 1.0]
}
```
Lengths must match `input_dims * window_W`.
Encoding uses z-score normalization; decoding applies the inverse.
If a `std` entry is 0, the encoder emits 0 for that dimension and the decoder returns `mean`.

## Packing
`packing` must be one of `int8`, `int16`, `float16`, `float32`.
`scale` is required for `int8` and `int16`. Values are scaled, rounded, and clipped
to the dtype range before packing.
Recommended defaults when your latent values are expected to stay within `[-1, 1]`:
- `int8`: `scale = 127`
- `int16`: `scale = 32767`
If your latent range is wider, choose a smaller `scale` (or bound the latent values) to avoid
clipping/saturation.

## bam_manifest.json
Required keys:
- `manifest_version` (string)
- `model_format` (string; must be `layer_npz_v1`)
- `model_path` (string; directory path)
- `latent_dim` (int)
- `packing` (string; one of: int8, int16, float16, float32)
- `input_dims` (int; sensor dims)
- `window_W` (int)
- `window_stride` (int)

Optional keys:
- `scale` (float; required for int8/int16)
- `delta` (float; enables cubic transmission)
- `encode_cycles` (int; default `0`). If >0, run per-layer recurrent refinement during encoding.
- `decode_cycles` (int; default `0`). If >0, run per-layer recurrent refinement during decoding.
- `norm_path` (string; path to norm.json)
- `notes` (string)

## RunSpec codec params
```
codec:
  id: bam
  version: "0"
  params:
    manifest_path: models/<model_version>/bam_manifest.json
```

## Payload schema rule
The BAM codec payload schema is derived from the manifest:
```
bam:latent_dim=<k>:packing=<packing>:scale=<scale-or-none>
```

## Example manifest
```json
{
  "manifest_version": "1",
  "model_format": "layer_npz_v1",
  "model_path": "models/bam_identity",
  "latent_dim": 8,
  "packing": "int16",
  "scale": 32767,
  "delta": 0.0,
  "input_dims": 12,
  "window_W": 1,
  "window_stride": 1,
  "norm_path": "models/bam_identity/norm.json",
  "notes": "example manifest; generate toy weights via scripts/make_bam_identity.py"
}
```

## Notes
- Default inference is single-step forward for encode and single-step backward for decode.
- If `encode_cycles`/`decode_cycles` are enabled, `delta` should stay in the paper-safe regime
  (`delta < 0.5`) to avoid unstable dynamics.
- If you change windowing or packing, update both the RunSpec and the manifest.
- A toy identity/truncation model can be generated from a manifest via:
  `python scripts/make_bam_identity.py --manifest configs/examples/bam_manifest.json`
- Phase 2 training and artifact workflow is described in
  `docs/phase2_bam_training.md`.
