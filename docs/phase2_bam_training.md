# Phase 2 (Offline): BAM Training and Artifacts

This document defines the Phase 2 offline training pipeline for BAM-family models.
This repo includes a baseline FEBAM-style trainer script that produces inference
artifacts compatible with the runtime. External training pipelines are also valid
as long as they follow the artifact contract.

## Goal
- Train a BAM-family model on `dataset_raw.jsonl`.
- Export inference artifacts (`layer_*.npz`, `norm.json`, `bam_manifest.json`).
- Ensure payload size obeys `max_payload_bytes` in RunSpec.

## Inputs
- `dataset_raw.jsonl` from Phase 1 (TX dataset logger).
- RunSpec window settings:
  - `window.dims` (must be 12)
  - `window.W`
  - `window.stride`
  - `window.sample_hz`
- Optional preprocessing spec (normalization rules).

## Output layout (recommended)
```
models/<model_id>/
  layer_0.npz
  layer_1.npz
  ...
  norm.json
  bam_manifest.json
  artifacts.json
```

## Artifact contract (must follow)
See `docs/bam_codec_artifacts.md` for the required schema.

Required files:
- `layer_*.npz`: each layer contains `W` and `V`.
- `norm.json`: mean/std for z-score normalization (optional but recommended).
- `bam_manifest.json`: model format, packing, latent_dim, window settings.

## Payload size rule
Payload size is determined by packing and latent dimension:
- int8: payload_bytes = latent_dim * 1
- int16: payload_bytes = latent_dim * 2
- float16: payload_bytes = latent_dim * 2
- float32: payload_bytes = latent_dim * 4

Ensure:
```
payload_bytes <= max_payload_bytes
```

## Training procedure (in-repo baseline)
Install numpy first:
```bash
python -m pip install -e .[bam]
```

Train and export artifacts:
```bash
python scripts/phase2_train_bam.py \
  --dataset out/dataset_raw.jsonl \
  --out-dir models/<model_id> \
  --hidden-dims 24,16 \
  --latent-dim 16 \
  --packing int16 \
  --train-ratio 0.8 \
  --split-seed 0
```

Notes:
- `--train-ratio` uses a deterministic `window_id` hash split; holdout is `(1-ratio)`.
- The trainer writes `layer_*.npz`, `norm.json`, `bam_manifest.json`, and an `artifacts.json`
  manifest (for `--manifest` in the runtime).
- `--scale` is only used for `int8`/`int16` packing. Defaults are chosen to match the dtype
  range when latent values are expected to stay within `[-1, 1]` (`127` for int8, `32767` for int16).
- Optional: enable per-layer recurrent refinement at inference time by setting `--encode-cycles`
  and `--decode-cycles` (written into `bam_manifest.json`). When enabled, keep `delta < 0.5`.
- Optional: improve training stability on large datasets using `--shuffle-buffer` and early stopping
  (`--min-epochs`, `--early-stop-patience`, `--early-stop-min-delta`, `--target-mse-x`).
- Optional: if using `int8/int16`, enable `--auto-scale` to tune packing scale from latent stats.

Evaluate reconstruction on the holdout split:
```bash
python scripts/eval_bam_dataset.py \
  --dataset out/dataset_raw.jsonl \
  --bam-manifest models/<model_id>/bam_manifest.json \
  --subset holdout \
  --train-ratio 0.8 \
  --split-seed 0 \
  --out out/phase2/eval_<model_id>.json
```

If you want a different split rule or optimizer/hyperparameters, use an external
trainer and export artifacts that follow `docs/bam_codec_artifacts.md`.

## Model selection sweep (recommended)
To pick an "optimal" model for a payload budget, run a sweep and compare against baselines:
- mean baseline (reconstruct train mean)
- PCA baseline (z-scored)

Example:
```bash
python scripts/phase2_sweep_bam.py \
  --dataset out/dataset_raw.jsonl \
  --out-dir out/phase2/sweep \
  --latent-dims 2,4,8,16 \
  --hidden-dims 24,16 \
  --packings int16,int8 \
  --deltas 0.1 \
  --encode-cycles 0,1 \
  --decode-cycles 0,1 \
  --train-ratio 0.8 \
  --split-seed 0 \
  --auto-scale \
  --force
```

The sweep writes a single report JSON (including a Pareto frontier) under:
- `out/phase2/sweep/sweep_report.json`

## RunSpec wiring (TX/RX)
Example RunSpec snippet:
```
codec:
  id: bam
  version: "0"
  params:
    manifest_path: models/<model_id>/bam_manifest.json
```

## Validation (local)
After artifacts are created, run a local mock check:
```bash
python -m loralink_mllc.cli tx \
  --runspec configs/examples/tx_bam.yaml \
  --manifest models/<model_id>/artifacts.json \
  --radio mock

python -m loralink_mllc.cli rx \
  --runspec configs/examples/rx_bam.yaml \
  --manifest models/<model_id>/artifacts.json \
  --radio mock
```

Make sure the RunSpecs point to your trained manifest:
- In your TX/RX YAML, set `codec.params.manifest_path: models/<model_id>/bam_manifest.json`.
  The default examples (`configs/examples/tx_bam.yaml`, `configs/examples/rx_bam.yaml`) point
  to the toy identity model under `configs/examples/`.

## Record template
Use `configs/examples/phase2_record.yaml` to log training settings, artifacts, and
validation results.

## Open items (TBD)
- The baseline trainer is a simple FEBAM-style online update rule; it is not
  guaranteed to be optimal for your field dataset.
- Phase 3 on-air validation procedure is defined in `docs/01_design_doc_experiment_plan.md`
  and `docs/project_execution_plan.md`.
