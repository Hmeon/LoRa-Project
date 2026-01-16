# BAM ML Implementation Review (Qualitative + Quantitative)

This document provides an objective review of the BAM-based ML lossy-compression implementation
in this repo, with a focus on:
- paper-alignment risks (what matches vs what deviates),
- quantitative reconstruction behavior on a small in-repo dataset,
- concrete improvement actions.

It is **not** a claim that the model is already optimal for field data. The repo ships a baseline
trainer and an inference codec; model quality depends on dataset size/stationarity and tuning.

## 1) What is implemented (today)

### Inference codec (runtime)
- `loralink_mllc/codecs/bam.py`
  - Multi-layer linear encode/decode with optional cubic transmission (`delta`).
  - Optional per-layer recurrent refinement (`encode_cycles`, `decode_cycles`) for paper-style
    attractor dynamics (off by default).
  - Optional z-score normalization via `norm.json`.
  - Payload packing: `int8/int16/float16/float32`.
  - Payload contract + schema: `docs/bam_codec_artifacts.md`.

### Offline training (baseline)
- `scripts/phase2_train_bam.py`
  - FEBAM-style online update rule (time-difference Hebbian update), trained layer-wise.
  - Writes `layer_*.npz`, `norm.json`, `bam_manifest.json`, optional `artifacts.json`.
  - Deterministic train/holdout split by `window_id` hash (`--train-ratio`, `--split-seed`).

### Evaluation tooling
- `scripts/eval_bam_dataset.py`
  - Computes MAE/MSE (overall + sensor-group splits for 12D).

## 2) Paper-alignment (qualitative assessment)

### What aligns well (paper-consistent)
- **Reconstruction objective** is central (MAE/MSE are first-class metrics).
- **Normalization** is treated as mandatory for mixed-scale sensors.
- **Layer-wise training** matches the staged-learning framing in the LLN BAM paper (at a high level).
- The baseline trainer’s **time-difference update structure** is consistent with the FEBAM-style
  formulation described in `docs/papers/04_paper_dissect__febam.md`.

### Main deviations / gaps (not “paper-faithful”)
- **LLN BAM paper**: describes an auto-correlation BAM framing (`W = Σ X X^T`) and a FE/DC pipeline.
  The in-repo trainer is FEBAM-style, not a literal autocorrelation implementation.
- **Inference recurrence**: the runtime codec is single-step forward/backward (no “iterate to fixed
  point” recall), matching the legacy ChirpChirp approach, but not the full dynamical BAM recall
  story.
- **Convergence constraints**: paper conditions (e.g., delta regime, eta bounds, stopping rules based
  on squared error thresholds) are not enforced by the baseline trainer; it uses fixed epochs.
- **Quantization regime**: runtime can pack `int8/int16`, but training is not quantization-aware; the
  optimal `scale` depends on latent range and should be validated per dataset.
- **Baselines**: PCA/autoencoder comparisons and the “compression rate × hidden units” sweep are not
  reproduced in-repo (tools exist to add this, but results are not shipped yet).

## 3) Quantitative sanity check (objective)

This repo includes a small example dataset: `out/dataset_raw.jsonl` (20 windows, 2 repeating
patterns). This dataset is **not** representative of field data, but it is useful as a
deterministic sanity check and to highlight training sensitivity.

### Holdout protocol
- Split: `--train-ratio 0.8 --split-seed 0` (same rule used by the Phase 2 trainer/evaluator).
- Metric: MAE/MSE on the holdout windows.

### Results summary (reproducible)
- **Mean baseline** (reconstruct train mean): MAE ≈ `0.035784`, MSE ≈ `0.002027`.
- **BAM (default trainer settings)** (`epochs=1`, `learning_rate=1e-4`, `latent_dim=2`, `int16`):
  MAE ≈ `0.035704`, MSE ≈ `0.002018` → effectively “mean reconstruction” on this dataset.
- **BAM (tuned for this toy dataset)** (`epochs=200`, `learning_rate=0.01`, `weight_clip=5`,
  `latent_dim=2`, `float32`): MAE ≈ `0.011175`, MSE ≈ `0.000198`.
- **PCA baseline** (`k=2` on the same z-scored split): MAE ≈ `~0`, MSE ≈ `~0` on this toy dataset
  (because the data lies in a very low-dimensional subspace).

Interpretation:
- The baseline trainer can be **very sensitive** to dataset size and training budget; with a tiny
  dataset it may converge to “mean reconstruction”.
- This does **not** prove BAM is inferior on real data, but it does show we must:
  - run a Phase 2 sweep on the real dataset,
  - compare against simple baselines (at least PCA),
  - and tune training hyperparameters and packing/scale.

## 4) Improvements (prioritized)

### Implemented fixes (already applied)
- `int8` packing `scale` default fixed in `scripts/phase2_train_bam.py` (`127` for int8).
- Added `int8` roundtrip unit test.
- Documented recommended `scale` defaults in the artifacts/training docs.
 - Added optional recurrent refinement in the BAM codec (`encode_cycles`, `decode_cycles`) and
   documented it in the artifacts contract.

### High-impact next steps
1) Add a Phase 2 sweep runner (latent_dim × packing × scale) that writes a single JSON report
   (MAE/MSE + payload bytes) for reproducible model selection.
2) Add at least one baseline comparator (PCA with numpy) to make results objective.
3) Add training progress metrics and optional early stopping (track reconstruction error
   periodically, not only “epochs”).
4) Decide the “delta + clipping” regime (paper assumes bounded activations). If `int8/int16`
   packing is used, explicitly validate that latent ranges do not saturate.

## 5) Reproduce (commands)

Install:
```bash
python -m pip install -e .[bam]
```

Train a small model:
```bash
python scripts/phase2_train_bam.py \
  --dataset out/dataset_raw.jsonl \
  --out-dir out/models/review_lat2 \
  --latent-dim 2 \
  --packing int16 \
  --train-ratio 0.8 \
  --split-seed 0 \
  --force
```

Evaluate holdout:
```bash
python scripts/eval_bam_dataset.py \
  --dataset out/dataset_raw.jsonl \
  --bam-manifest out/models/review_lat2/bam_manifest.json \
  --subset holdout \
  --train-ratio 0.8 \
  --split-seed 0
```
