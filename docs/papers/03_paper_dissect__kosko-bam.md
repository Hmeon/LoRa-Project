# Paper Dissection (Project-Aligned): Kosko (1988) - *Bidirectional Associative Memories (BAM)*

## 0) Why this paper matters to *our* compression framing (without evaluating)
This paper defines a **two-layer bidirectional heteroassociative memory** that:
- stores **paired patterns** \((A_i, B_i)\) where \(A\) and \(B\) may have **different dimensionalities**
- performs recall by **iteratively propagating forward and backward** through the same inter-layer synaptic matrix \(M\) and its transpose \(M^T\)
- uses a **global stability / convergence argument** (energy/Lyapunov-style) to show the recall dynamics converge to a **bidirectional fixed point** under broad conditions

For our LoRa compression view, the paper's internal roles map cleanly:
- \(A\)-layer: "original high-dimensional pattern" (e.g., a sensor window vector)
- \(B\)-layer: "paired pattern on the other side" (e.g., compressed / latent code)
- Forward pass \(A \to B\): **compression**
- Backward pass \(B \to A\): **reconstruction**
- "Noise/corruption in cues": models **lossy/partial information** at recall time (not necessarily bit-level channel noise; conceptually "incomplete/perturbed cue")

> Important: the paper's BAM is not described as a modern trainable autoencoder. It is formulated as a bidirectional associative dynamical system with a specific convergence logic.

---

## 1) Research problem: how it is *formalized* inside the paper

### 1.1 Core object being defined
The paper defines a **Bidirectional Associative Memory (BAM)** as a **two-layer** network:
- layer \(F_A\) with state vector \(A\) (dimension \(n\))
- layer \(F_B\) with state vector \(B\) (dimension \(m\))
- **no intra-layer connections**; only inter-layer connections via matrix \(M \in \mathbb{R}^{n \times m}\)
- reverse-direction coupling is via \(M^T\)

So the "network state" is the ordered pair \((A, B)\).

### 1.2 What "successful recall" means (internal definition)
A **bidirectional fixed point / equilibrium** is a pair \((A^\*, B^\*)\) that is consistent in both directions:
- starting from \(A^\*\) you get \(B^\*\) after applying the forward rule
- starting from \(B^\*\) you get \(A^\*\) after applying the backward rule

In other words, \((A^\*, B^\*)\) is "self-consistent" under alternating forward/backward updates.  
This is the paper's internal formalization of "a stored association is recalled."

### 1.3 Dynamical recall procedure (what the paper treats as the *algorithm*)
The recall procedure is an **iteration**:
1) given \(A(t)\), compute \(B(t+1)\) from \(A(t)\) using \(M\)  
2) given \(B(t+1)\), compute \(A(t+1)\) from \(B(t+1)\) using \(M^T\)  
3) repeat until no longer changing (fixed point)

The update includes:
- a neuron "signal function" / threshold-like nonlinearity \(S(\cdot)\)
- optional thresholds per neuron (paper discusses threshold/bivalent/bipolar settings)

The paper emphasizes the relevance of **asynchronous** behavior: not all neurons must update simultaneously for convergence.

### 1.4 The stability target (the "theorem-shaped" problem)
The research target is not merely "it works on examples," but:
- define an **energy-like scalar function** over \((A,B)\)
- show that under the update rules, this energy **monotonically decreases (or does not increase)**
- conclude the dynamics converge to a **stable equilibrium** (a local minimum / fixed point)

So the "problem" is posed as:
> *Construct/define a two-layer bidirectional associative system and prove its recall dynamics converge to stable equilibria (bidirectional fixed points) under broad neuron models and update schedules.*

---

## 2) Prior approaches: limitations that the paper uses as setup

### 2.1 Autoassociative vs heteroassociative constraint
A key limitation motivating BAM is that classic autoassociative memories (e.g., Hopfield-style) naturally map:
- input pattern |-> **same-sized** output pattern

The BAM setup explicitly targets **heteroassociative recall**:
- \(A\) and \(B\) can be **different sizes**
- memory is about *pairing* patterns across two spaces

### 2.2 Directionality limitation
A common limitation in simpler associators is effectively "one-way" mapping:
- present an input, get an output
- but not necessarily invertible / not naturally used in reverse

BAM is built so that:
- presenting a cue on either side can recover the paired pattern on the other side
- and the system evolves via reverberation between the two layers

### 2.3 Stability / convergence not guaranteed by default
The paper treats stability as central:
- recurrent feedback systems can oscillate or fail to settle depending on dynamics
- therefore, a **Lyapunov/energy** mechanism is used to guarantee convergence

So the limitation is not "insufficient accuracy," but:
> *lack of a general convergence guarantee for bidirectional recall dynamics across broad neuron types and asynchronous updates.*

---

## 3) Proposed method: pipeline structure inside the paper

### 3.1 Pipeline overview (paper's internal modules)
The paper's structure can be expressed as the following pipeline:

**(A) Representation choice**
- Choose neuron model / signal function:
  - bivalent/binary, bipolar, or continuous-valued neurons
- Choose thresholds (possibly 0 for bipolar simplification, or explicit \(\theta\))

**(B) Storage / encoding of paired patterns**
- Given training pairs \(\{(A_i, B_i)\}_{i=1..P}\)
- Construct the inter-layer matrix \(M\) using a correlation/outer-product style encoding:
  - (paper's core idea) "sum of correlation matrices" for paired patterns

**(C) Recall / reconstruction as bidirectional dynamics**
- Start from a cue pattern on one side (possibly corrupted / partial)
- Alternate forward/backward activation:
  - \(A \to B\) through \(M\)
  - \(B \to A\) through \(M^T\)
- Continue until a stable pair \((A^\*, B^\*)\) is reached

**(D) Convergence certificate**
- Define energy \(E(A,B)\) (Lyapunov-like)
- Show each update step decreases \(E\) (or does not increase)
- Conclude convergence to a fixed point

### 3.2 The convergence core (what makes it "BAM" rather than just "two mappings")
The paper's distinctive element is the **energy argument**:
- The bidirectional recurrence is not arbitrary; it is structured so that there exists a scalar energy surface.
- Recall is interpreted as moving "downhill" to a local minimum.

This is the internal reason the paper can claim global stability behavior under broad conditions:
- the energy decreases even under **asynchronous** neuron updates (under the paper's conditions)

### 3.3 Noise/perturbation handling (internal framing)
The paper discusses that cues may be corrupted, and analyzes how the bidirectional process can:
- correct errors / recover the intended associated pair
- depending on encoding, pattern similarity, and capacity-like effects

This appears as:
- relationships to Hamming distance (for discrete/bipolar)
- "noise amplification / correction" coefficients in the algebraic analysis

---

## 4) Assumptions required for the method to *hold as stated*

This section is intentionally strict: these are the assumptions the BAM logic relies on.

### 4.1 Architectural assumptions
- Exactly **two layers** in the core model
- **No within-layer** synaptic connections (only cross-layer)
- Reverse direction uses \(M^T\) (paired symmetric coupling across layers)

### 4.2 Timescale separation (implied/used in reasoning)
- Synaptic matrix \(M\) is treated as **fixed during recall**
- Neuron activations evolve "fast," while learning (if any) evolves "slow"
  - the convergence proof treats \(M\) as constant during state evolution

### 4.3 Neuron / signal function assumptions (for stability arguments)
- Neurons use threshold or threshold-like, monotone signal functions \(S(\cdot)\)
- For discrete cases:
  - state space is finite => monotone energy descent implies eventual convergence
- For continuous cases:
  - the paper uses conditions that preserve energy descent under the chosen continuous activation model

### 4.4 Update schedule assumptions
- Asynchronous update is allowed, but:
  - the update rule must be consistent with the energy-decrease proof
  - "how and when neurons fire" matters only to the extent required by the stability argument

### 4.5 Pattern encoding assumptions
- Paired patterns \((A_i,B_i)\) must be representable in the neuron state model:
  - bipolar \(\{-1,+1\}\), bivalent \(\{0,1\}\), or bounded continuous ranges
- The correlation/outer-product construction assumes consistent scaling/coding across stored pairs

---

## 5) Experimental / demonstration logic and fixed conditions (paper-internal)

The paper's "experimental logic" is primarily **demonstration-by-analysis + illustrative recalls**, rather than a modern benchmark suite.

### 5.1 What is treated as "evidence"
- Algebraic derivations showing:
  - energy decreases after neuron updates
  - convergence to fixed points follows
- Illustrative recall behavior:
  - present a cue \(A\) (or \(B\)), often perturbed
  - observe convergence to some stored pair (or a spurious/incorrect equilibrium when overloaded)

### 5.2 Fixed conditions that underpin the demonstrations
- \(M\) constructed by the stated encoding rule (correlation/outer products)
- Recall uses the defined bidirectional iteration through \(M\) and \(M^T\)
- Pattern corruption is modeled as perturbation in the cue pattern (e.g., bit flips / partial mismatch in discrete cases)
- Distances/similarity are interpreted via:
  - Hamming distance in bipolar/bivalent cases
  - analogous measures in continuous cases

### 5.3 The paper's implicit control variables
Even when not listed as "controls," the paper's logic treats these as fixed when analyzing outcomes:
- dimensionalities \((n, m)\)
- number of stored pairs \(P\)
- coding choice (bipolar vs bivalent vs continuous)
- threshold values
- update scheme (synchronous vs asynchronous variant consistent with stability proof)
- degree/type of cue corruption

---

## 6) Extension axes that the paper itself exposes (design degrees of freedom)

This section lists what the paper's framework naturally allows you to vary *without breaking the BAM definition*.

### 6.1 Neuron model axis
- bivalent / bipolar discrete neurons
- continuous-valued neurons (bounded), with threshold-like nonlinearity

**Design knob:** choose \(S(\cdot)\) and state range to match the signal type.

### 6.2 Coding / representation axis
- bipolar encoding often simplifies algebra and distance measures
- bivalent encoding requires threshold/offset handling
- continuous encoding requires bounded activation and careful scaling

**Design knob:** preprocessing/coding of data into the state variables that the BAM dynamics assume.

### 6.3 Storage rule axis (within "correlation style" family)
The paper's core storage is a sum of correlation/outer-product contributions from each pair.

**Design knob:** how you weight/scale each pair's contribution, normalization choices, and whether you store raw or transformed features (so long as the BAM dynamics remain the same type).

### 6.4 Recall dynamics axis
- synchronous vs asynchronous schedules (subject to stability conditions)
- stopping criteria (fixed point detection)
- threshold handling during recall

**Design knob:** the "runtime policy" of neuron firing and convergence checks.

### 6.5 Capacity / interference axis (paper's own warning surface)
The paper indicates that as \(P\) grows and/or as patterns become less separable, recall becomes unreliable and spurious equilibria appear.

**Design knob:** choose \(P\), dimensionality, and coding to manage interference.

### 6.6 Temporal encoding axis (paper's internal direction)
The paper discusses temporal aspects as a way to interpret recall as a reverberation process across two layers.

**Design knob:** how time-structured data is turned into a pattern pair (e.g., windowing/stacking), while keeping the BAM formalism intact.

---

## 7) Assumptions likely to break in a real LoRa sensor-compression deployment (high-risk points)

This section is written as "what breaks first" when you apply the BAM assumptions to field IoT data and lossy links.

### 7.1 Discrete pattern assumption vs continuous multivariate sensors
BAM's cleanest analysis often assumes bipolar/bivalent patterns.  
Real sensors (GPS/IMU/attitude) are continuous, correlated, and scale-drifting.

**Break mode:** without strict coding/normalization, the assumed threshold-like dynamics may not preserve the energy descent behavior in practice (or may converge to unintended equilibria).

### 7.2 "Cue corruption" model mismatch
The paper's perturbation framing naturally matches "bit flips / partial mismatch in a cue pattern."
LoRa impairments often show up as:
- packet drop (missing entire payload)
- burst loss / long fades
- truncated frames / CRC failures (data not delivered at all)

**Break mode:** BAM assumes a *present cue* exists (even if corrupted). With packet loss, you may have *no cue* at a given step unless you design buffering/interpolation strategies.

### 7.3 Fixed \(M\) during recall vs online drift
The stability proof treats \(M\) as fixed during state evolution.
In deployment, you may want online updates (concept drift, new motion regimes).

**Break mode:** updating \(M\) during active recall can violate the timescale separation implied in the convergence reasoning.

### 7.4 Capacity and multi-pattern interference under realistic motion regimes
The paper recognizes that overload and similarity cause spurious equilibria and unreliable recall.

In field data:
- "patterns" are not random; they cluster (walking/running/vehicle)
- many windows may be similar => higher interference

**Break mode:** the network may converge consistently, but to the *wrong* stored association (stable but incorrect equilibrium).

### 7.5 Threshold sensitivity
BAM behavior can depend strongly on thresholds and scaling.

**Break mode:** sensor scaling differences (GPS meters vs IMU units) can dominate dot-products unless features are normalized; thresholds tuned on one environment may fail elsewhere.

### 7.6 Asynchrony vs embedded scheduling realities
The paper's convergence allows broad asynchronous firing, but assumes the update rule aligns with the proof.

**Break mode:** if implementation shortcuts alter the update order or apply partial updates inconsistently (e.g., truncated vector, mixed precision overflow, UART framing artifacts), the realized dynamics may not match the theoretical update sequence.

### 7.7 "Pattern pair availability" assumption
BAM recall presumes you can iteratively compute \(A \to B \to A\) steps. In a split TX/RX design:
- TX computes \(B\) from \(A\)
- RX computes \(\hat{A}\) from received \(B\)

**Break mode:** the iterative reverberation across layers may not exist across the air link unless you explicitly engineer feedback/ACK-based iterations. If you run only one forward pass at TX and one backward pass at RX, you are implementing a *single-step* BAM mapping, not the full bidirectional dynamical recall described in the paper.

---

# "Project-Fit" Extraction (still within BAM logic)

## A) Minimal BAM-as-compression interpretation
To stay faithful to the paper's structure:
- treat a sensor window vector as \(A\)
- treat a compact code as \(B\)
- store or learn \(M\) such that:
  - forward mapping yields a stable \(B\) for each \(A\)
  - backward mapping reconstructs the paired \(A\) from \(B\)
- runtime:
  - TX runs \(A \to B\)
  - RX runs \(B \to \hat{A}\)

**Key constraint from the paper:** the more you deviate from "paired fixed points under the defined dynamics," the less the energy/convergence guarantees apply.

## B) What you must decide (paper-forced design decisions)
These are not "extra features"; they are required choices implied by the paper:
1) **state coding**: bipolar/bivalent/continuous and scaling rules  
2) **threshold policy**: fixed vs learned; per-neuron vs global  
3) **storage rule**: exact correlation sum form and normalization  
4) **recall schedule**: single-step vs iterative reverberation (and if iterative, where it runs)  
5) **capacity management**: what counts as a stored "pair," and how many pairs are feasible before interference dominates

---

# Checklist: what to verify against our LoRa constraints (UART payload + loss)
This checklist is intentionally operational, but it does not add new theory beyond the paper's knobs.

- [ ] Can we define \(A\) and \(B\) so that \(B\) fits the payload budget while still being a valid BAM-side pattern?
- [ ] Are we implementing **iterative** BAM recall (energy descent through repeated forward/backward) or only a **single forward + single backward** mapping?
- [ ] How do we handle "no cue arrives" (packet loss), given the paper's recall assumes a cue exists?
- [ ] What is our capacity control: what is \(P\), and how similar are stored pairs in real motion data?
- [ ] What normalization ensures dot-products are not dominated by one sensor modality?

---

# Notes on language alignment
The paper's terminology that matters most for our design doc:
- "bidirectional" = forward/backward propagation through \(M\) and \(M^T\)
- "heteroassociative" = \(A\) and \(B\) can have different sizes and represent different patterns
- "stable equilibrium / fixed point" = convergence target of recall dynamics
- "energy / Lyapunov function" = internal guarantee mechanism for convergence
- "spurious states / interference" = stable but undesired equilibria due to overload/similarity
