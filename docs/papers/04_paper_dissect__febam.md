# FEBAM (2007) - Paper Dissection for Lossy Sensor Compression over LoRa
**Source paper:** "FEBAM: A Feature-Extracting Bidirectional Associative Memory" (IJCNN 2007)  
**Goal of this note:** Not a summary; a structural teardown of the paper's internal logic so it can be used as a *design prior* for an IoT/LoRa "ML-based lossy compression" project.

---

## 0) Vocabulary & Notation (as used in the paper)
- **x**: input vector (original data in the "V layer" / x-layer)
- **y**: feature / compressed vector (representation in the "W layer" / y-layer)
- **W**: weight matrix mapping **x -> y**
- **V**: weight matrix mapping **y -> x**
- **N**: number of units in the y-layer (dimensionality of **y**)
- **M**: number of units in the x-layer (dimensionality of **x**)
- **delta (delta)**: output-function parameter controlling continuous-valued attractor behavior (must be < 0.5 for fixed-point behavior)
- **eta (eta)**: learning rate (must satisfy a convergence bound)
- **t**: number of network cycles/iterations before updating weights (the paper sets **t = 1**)
- **k**: learning trial index

**Interpretation in a sensor-compression project (paper-consistent mapping):**
- Treat a **sensor window** (multidimensional time-series segment) as **x(0)**.
- Treat the lower-dimensional representation as **y(0)**.
- Compression ratio is controlled by choosing the number of y-units relative to x-units.
- Recovery is performed through the recurrent x<->y dynamics and the learned (W, V).

---

## 1) Research Problem - How the paper formalizes it
### 1.1 The "unification target" the paper sets up
The paper sets up two model families and frames a gap between them:

1) **PCA / neural PCA family**
- Linear PCA network form: **y = W x**
- Reconstruction form: **x_hat = W^T y**
- Objective: minimize reconstruction error (norm of x - x_hat), extended to nonlinear PCA with a nonlinear output function **y = f(Wx)** and corresponding minimization objective.

2) **BAM (Bidirectional Associative Memory) family**
- Standard BAM stores associations between two vectors, with Hebbian learning and recurrent recall dynamics.
- BAMs exhibit **attractor-like behavior** (pattern completion, noise filtering) through recurrence, but in their standard framing they store **noise-free** patterns and are less aligned with "learning under noisy exemplars".

### 1.2 The core research question (paper-internal)
> Can a BAM-style recurrent, attractor-based architecture be modified so that it **performs feature extraction / dimensionality reduction (PCA-like)** while preserving BAM-like properties (bidirectional processing, recall under noise, attractor dynamics)?

So the "problem" is not framed as communications per se; it is framed as:
- **Learning a compact representation** (feature extraction / dimensionality reduction)
- While maintaining **recurrent attractor dynamics** enabling robust recall / reconstruction from noisy inputs.

---

## 2) Prior Approaches - What limitations/premises the paper assumes
### 2.1 Limits the paper assigns to PCA networks
- Feedforward by definition -> does **not** yield attractor-like ("categorical") behavior.
- Lack of explicitly depicted bidirectional connections -> supervised learning often requires an external teacher.
- Some PCA models are not online/local in learning.

### 2.2 Limits the paper assigns to BAM models
- Standard BAM stores information using **noise-free** versions of patterns (paper argues this is misaligned with real-world noisy exemplars).
- Standard BAM (classic form) uses nonlinearities (e.g., signum) that produce **bipolar** attractor behavior; this is limited when continuous/gray-level values matter.

### 2.3 Premise used to justify FEBAM
- A model that merges PCA-like compression objectives with BAM-like recurrent recall could support:
  - feature extraction
  - dimensionality reduction
  - attractor-like recall
  - robust processing of noisy inputs

---

## 3) Proposed Method - Pipeline structure (architecture -> output -> learning)
FEBAM is specified by:
1) **Architecture**
2) **Output function** (recurrent update rule)
3) **Learning function** (weight update rule)

### 3.1 Architecture: two interconnected Hopfield-like networks
- Two layers are connected "head-to-toe" to allow **bidirectional recurrent flow**:
  - A **V (x) layer**
  - A **W (y) layer**
- Unlike a standard BAM, FEBAM removes one set of external connections:
  - In standard BAM, both x(0) and y(0) can be provided externally.
  - In FEBAM, only **x(0)** is provided externally; **y(0)** is *not* externally injected.
  - Instead, **y(0)** is obtained by iterating once through the network (an explicit "one-cycle" process).

**Pipeline viewpoint (paper-consistent):**
1) Inject **x(0)** at the x-layer
2) Compute **y(0)** internally by one network iteration
3) Continue x<->y recurrence as needed (the paper's learning update uses t cycles; in this paper t=1)

### 3.2 Compression knob: dimensionality of the y-layer
- Feature extraction is performed in the y-layer.
- Degree of compression is directly controlled by the number of y-units:
  - More y-units -> less compression
  - If dim(y) >= dim(x) -> no compression; the network behaves like an autoassociative memory.

This is the paper's explicit "design lever" for dimensionality reduction.

### 3.3 Output function: continuous-valued attractor behavior
FEBAM replaces a purely bipolar signum-style recall with a continuous-valued output function parameterized by **delta**.

- There are two coupled update equations (one for y(t+1) from x(t), one for x(t+1) from y(t)).
- The output nonlinearity is piecewise and supports continuous ("gray-level") attractor behavior.
- **delta must be fixed at a value lower than 0.5 to ensure fixed-point behavior.**

**Pipeline implication (paper-consistent):**
- Recurrence is used not only for "association" but also as a stabilizing mechanism: the network state flows toward an attractor under the output function.

### 3.4 Learning function: time-difference Hebbian association
FEBAM uses time-difference Hebbian learning:
- Two matrices are learned/updated: **W** and **V** (not only a single correlation matrix).
- Weight updates are proportional to the difference between the initial patterns and the patterns after t cycles:
  - Update W using terms involving (x(0) - x(t)) and (y(0) - y(t))
  - Update V similarly

**Important internal condition the paper states:**
- Weights converge only when "feedback" equals the initial inputs:
  - y(t) = y(0) and x(t) = x(0)
- Learning is linked to network outputs (states), not just raw activations.

### 3.5 Learning loop used in the paper (operational pipeline)
The paper's training procedure is:
1) Randomly select an input vector x(0)
2) Iterate through the network for one cycle (t = 1 in this paper)
3) Update weights (W and V)
4) Repeat until:
   - desired number of trials is reached, or
   - squared error between y(0) and y(t) is sufficiently small (paper uses a threshold like < 0.03 in simulations)

### 3.6 "Objective function view": why the paper claims this is nonlinear PCA-like
The paper provides an explicit link between its learning rule and minimizing reconstruction-like error functions at multiple times (t = 0, 1, 2). It shows:
- Two error functions (one for y-space, one for x-space) are minimized by the learning rules.
- An expanded form resembles the nonlinear PCA minimization form.

This is the paper's internal argument for "FEBAM behaves like a nonlinear PCA" while being BAM-inspired and recurrent.

---

## 4) Assumptions required for FEBAM to "hold" (paper-internal)
### 4.1 Output stability assumption
- **delta < 0.5** is required for fixed-point behavior.
- The attractor behavior depends on this stability property.

### 4.2 Learning-rate convergence assumption
- **eta must satisfy a bound** for convergence (depends on delta and the larger of N, M).

### 4.3 Learning schedule assumption
- The paper chooses **t = 1** (update weights after one cycle).
- This makes the method closer to a "one-step" nonlinear PCA-like update, but still grounded in recurrent architecture.

### 4.4 Data domain / scaling assumption (implicit in simulations)
- Inputs are treated as continuous values within a bounded range (in image experiments they rescale to [-1, 1]).
- Continuous-valued output function assumes numeric ranges compatible with the piecewise nonlinearity.

### 4.5 Model-scope assumptions introduced by the chosen simulation tasks
- For blind source separation, the paper assumes sources are:
  - non-Gaussian
  - mutually independent
- Whitening (sphering) is applied before learning.

(These are assumptions of that experiment, not necessarily of "compression" use.)

---

## 5) Experimental Design Logic - What is fixed, what is measured, and why
The paper demonstrates "nonlinear PCA-like" behavior using two canonical tasks:
1) **Image reconstruction** (PCA-style)
2) **Blind source separation** (ICA-style)

### 5.1 Image reconstruction experiment
**Design intent:**
- Learn a compact set of statistical features from an image, then reconstruct it to quantify information loss.
- Test generalization by reconstructing a *different* image using the learned features.

**Fixed conditions (as specified):**
- Image: 128x128 grayscale (8-bit 0..255)
- Rescaled to range [-1, 1]
- Construct input vectors by sliding an overlapping 5x5 window -> 15376 vectors of dimension 25
- Weight initialization: random in [-1, 1]
- Parameters: eta = 0.005, delta = 0.1
- Training procedure: random input selection -> one-cycle iteration -> weight update -> repeat
- Stopping/quality: squared error threshold and/or fixed number of learning trials
- Metric: **PSNR** used to quantify reconstruction quality

**Baseline usage (paper design, not an evaluation claim here):**
- The paper compares against representative linear PCA NN, nonlinear PCA NN, and an ICA algorithm.

### 5.2 Blind source separation experiment
**Design intent:**
- Recover independent sources from observed linear mixtures.

**Fixed conditions (as specified):**
- Two sources (one sinusoid, one uniform white noise)
- Mixing: x = A s with a specific 2x2 mixing matrix
- Whitening applied by eigen-decomposition so observed mixtures become uncorrelated with unit variance
- Parameters: eta = 0.05, delta = 0.1
- Weight initialization: random in [-1, 1]
- Training procedure mirrors the image task
- Stopping/quality: squared error threshold and learning trials (paper notes ~12000 trials and error < 0.03)

**Baseline usage (paper design, not an evaluation claim here):**
- fastICA is used as a reference algorithm for the BSS task.

---

## 6) Expandable Design Axes (what the paper implies can be tuned/extended)
These are not "my ideas"; they are the degrees of freedom the paper itself exposes or flags as future work.

### 6.1 Representation size (compression ratio)
- Dim(y) is the explicit knob:
  - fewer y-units -> stronger compression
  - more y-units -> weaker compression / closer to autoassociative memory

### 6.2 Output-function regime (delta)
- delta governs the continuous-valued attractor behavior and fixed-point property.
- Different delta values reshape the output nonlinearity.

### 6.3 Learning-rate regime (eta) under a convergence constraint
- eta must remain under a bound to ensure weight convergence.

### 6.4 Iterations before update (t)
- The paper sets t = 1, but the formulation is written for general t.
- Changing t changes how far the recurrent dynamics progresses before weight updates.

### 6.5 Decorrelation / redundancy handling (explicitly mentioned in Discussion)
- The paper notes that different weights can converge to the same component.
- It suggests a possible decorrelation procedure (as used in ICA/PCA methods) as an enhancement direction.

### 6.6 Model-level extensions (explicitly mentioned in Discussion)
- Establish computational complexity.
- Evaluate capacity to learn environmental biases.
- Explore evolutive architecture tied to clustering development.
- Evaluate prototype extraction in noisy environments (a difficulty the paper highlights for standard RAM/BAMs).

---

## 7) Assumptions likely to break in a real LoRa sensor-compression deployment (risk list)
This section is *still paper-grounded*: it only flags where the paper's assumptions/experimental framing are tight, and where real deployment conditions can violate them.

### 7.1 Range/normalization stability (continuous-valued attractor requirement)
- The paper's continuous output function and its experiments rely on bounded continuous inputs (e.g., rescaling to [-1, 1]).
- Real sensor streams (GPS, IMU) have drifting ranges, different units, and outliers.
- If input scaling is not stable, the output function regime (and the meaning of delta thresholds) may no longer match the assumed attractor behavior.

### 7.2 Training cost vs. embedded constraints (many trials, recurrent updates)
- The paper's experiments use thousands to tens of thousands of learning trials with recurrence and weight updates.
- If training is attempted on constrained devices, this assumption becomes fragile unless training is performed offline and only inference is embedded.

### 7.3 "Noise" vs. "missingness"
- The paper's robustness argument is framed around *noisy inputs* processed through recurrence toward attractors.
- Packet loss in LoRa can cause *missing windows/segments*, not just noisy values.
- If entire x(0) segments are missing (not degraded), the model's recall dynamics may not have enough cue to converge to the intended attractor.

### 7.4 Sender/receiver symmetry (two matrices W and V)
- FEBAM learns/uses both W (x->y) and V (y->x).
- A deployment that splits encoding on sender and decoding on receiver must ensure both sides have consistent parameters (W and V) and consistent preprocessing; otherwise the "feedback equals initial input" convergence logic is violated.

### 7.5 Fixed-point and convergence constraints under quantization
- The paper's stability condition (delta < 0.5) and learning-rate bound are derived in a real-valued setting.
- If a deployment quantizes weights/activations aggressively, fixed-point dynamics and convergence conditions may not match the assumptions used to justify stability.

### 7.6 Windowing assumption (input vectorization)
- The paper's core method works on vectors x(0); in experiments, those vectors come from a specific windowing process (5x5 image patches).
- A sensor deployment must define an equivalent windowing/packing rule; if the chosen windowing destroys key correlations, the "feature extraction" premise becomes misaligned with the paper's learning logic.

---

## 8) What the paper gives you vs. what it does NOT specify (for Design Doc completeness)
### 8.1 The paper specifies clearly
- Architecture change: remove external y(0) input; compute y(0) internally by one iteration
- Two coupled output equations with delta controlling continuous-valued attractors
- Two learning updates (W and V) using time-difference Hebbian association
- A convergence bound on eta and a fixed-point requirement on delta
- A concrete training loop (random sample -> one-cycle -> update -> repeat)
- Canonical experiments and metrics (PSNR; BSS with whitening)

### 8.2 The paper does NOT specify (must be decided in the project Design Doc)
(These are "unspecified by the paper," not criticisms.)
- How to packetize y(0) (latent vector) into a constrained payload
- Quantization / numeric format strategy for y, W, V (float vs fixed-point)
- How to handle variable-length sequences, missing packets, resynchronization
- Online adaptation strategy under non-stationary sensor distributions
- Exact stopping criteria for training in a streaming sensor context (beyond "squared error sufficiently small")

---

## 9) Paper-to-Project Alignment Summary (one paragraph, no evaluation)
FEBAM's internal logic can be read as a recurrent, bidirectional "encoder-decoder" where compression is achieved by choosing a smaller y-layer, robustness is tied to attractor-like recurrence under a continuous-valued nonlinearity (delta-controlled), and learning is driven by time-difference Hebbian updates that converge under an eta bound when the network's feedback reproduces its initial states. The paper demonstrates this logic on canonical PCA/ICA-style tasks using explicit preprocessing (vectorization, scaling, whitening), fixed hyperparameters (eta, delta), and stopping via squared-error thresholds.
