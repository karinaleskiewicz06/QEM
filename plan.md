# Characterizing the Limits of Zero-Noise Extrapolation under Routing-Induced Gate Overhead in Variational Quantum Classifiers

**Working title.** *When does error mitigation stop paying for routing? An empirical, cross-topology study of ZNE-recoverable accuracy in variational quantum classifiers.*

---

## 1. Primary Goal

To empirically map the operational regime in which Zero-Noise Extrapolation (ZNE) can recover the
performance of a Variational Quantum Classifier (VQC) as a function of **routing-induced two-qubit-gate
(SWAP) overhead**, across superconducting processors of increasing size and connectivity, and to relate the
breakdown of ZNE to the onset of noise-induced gradient flattening (convergence toward the maximally
mixed state).

The deliverable is a **relationship with quantified uncertainty** — recovered accuracy and output/gradient
variance versus transpiled two-qubit-gate cost, with error bands across device calibrations and topologies —
rather than a single universal threshold, yielding reproducible, hardware-aware compilation guidance.

---

## 2. Problem Background: Topological Constraints of NISQ Architectures

Noisy Intermediate-Scale Quantum (NISQ) processors are characterized by strictly defined, sparse
connectivity topologies. Implementing any useful algorithm, such as a VQC, requires mapping the
algorithm's logical qubits onto the physical qubits of the processor. When the algorithm requires
interactions (multi-qubit gates) between qubits that are not physically connected, the compiler must
insert a network of routing gates — primarily SWAP gates.

**Hardware used in this study.** We exploit three-tier device access with distinct connectivities:

| Tier | Device | Qubits | Topology | Access | Role in study |
|------|--------|--------|----------|--------|---------------|
| A | ODRA (IQM Spark-class) | 5 | **Star** (central hub + 4 outer) | Full / unlimited | Primary workhorse; forced-SWAP generator; fast iteration |
| B | **IQM Garnet** | 20 | **Square lattice** | Limited | Intermediate-scale validation |
| C | **IQM Emerald** | 54 | **Square lattice** | Limited | Large-scale validation |



The **star topology of Tier A is a deliberate methodological asset**: any interaction between two *outer*
qubits must route through the central hub, generating forced, cleanly-controllable SWAP overhead. This
lets us produce large routing costs on the machine we have unlimited access to, reserving scarce Tier B/C
time for confirming the frontier at selected points.

---

## 3. Core of the Problem: The Cost of SWAP Gates

SWAP gates are unavoidable on sparsely connected architectures, but incur a drastic operational cost.
A single SWAP is most commonly decomposed into three CNOT gates (or the native two-qubit equivalent).
This creates a twofold problem:

1. **Duration.** It extends circuit depth and runtime, amplifying decoherence (T1) and dephasing (T2) errors.
2. **Two-qubit error.** Two-qubit gates are the dominant source of coherent and incoherent operational
   error in superconducting circuits.

Together these produce a **cascading accumulation of two-qubit-gate and decoherence error** (topological
degradation): quantum information decays into noise before reaching measurement. We treat the
**transpiled two-qubit-gate count** — of which SWAP insertion is one controlled source — as the physically
meaningful cost variable, because "nominal SWAP count" alone conflates several distinct effects.

---

## 4. Research Gap: The Limits of Error Mitigation (ZNE)

Zero-Noise Extrapolation (ZNE) is a leading software-level error-mitigation technique that recovers
circuit expectation values without the qubit overhead of full quantum error correction. However, ZNE
assumes a degree of continuity and predictability in the physical noise model that its extrapolation is fitted
to. The open question:

> **At what transpiled two-qubit-gate cost does the noise accumulation from routing overhead push the
> device outside the regime ZNE's extrapolation assumes — causing recovered estimates to become
> unreliable — and how does this point relate to the onset of noise-induced gradient flattening?**

Note that the *existence* of such a breakdown is expected from theory: Wang et al. (2021) proved
*noise-induced barren plateaus*, i.e., exponential flattening of the cost landscape in circuit depth under
local noise. Our contribution is the **empirical, device- and topology-resolved location** of this onset
relative to the region in which ZNE remains useful.

---

## 5. Research Objective

The objective is **not** to identify a single universal threshold constant — physical error rates drift between
calibrations, so any such number would be device-, qubit-, and date-specific. Instead we **characterize the
region in which ZNE remains effective as a function of transpiled two-qubit-gate cost**, and convert that
characterization into a hardware-aware compilation guideline.

We answer three precise questions:

1. **Recoverability.** Up to what two-qubit-gate budget does ZNE recover the VQC's noiseless accuracy to
   within a stated tolerance, and with what variance across recalibrations?
2. **Breakdown.** Where do the ZNE fit residuals and recovered-accuracy error bars diverge, signalling that
   noise has left the regime the extrapolation assumes?
3. **Collapse.** Where does the output collapse toward the maximally mixed state (vanishing
   output/gradient variance)? We tie this endpoint explicitly to noise-induced barren-plateau theory.

**Methodological commitments.**
- ZNE mitigates **expectation values**, not accuracy directly; we mitigate each measured observable, then
  apply the classifier decision rule, reporting accuracy as a derived quantity.
- To keep hardware cost tractable, we **train the VQC in a noise-calibrated classical simulator** and execute
  **inference + ZNE on hardware** across the routing sweep. This separates trainability effects from the
  inference-time mitigation question that is the focus of the study.
- We report a **relationship with uncertainty** (error bands over calibrations and topologies), not a point estimate.

---

## 6. Model and Dataset Selection

**Ansatz.** A multi-qubit **Hardware-Efficient Ansatz (HEA) with layer-wise data re-uploading**:
per layer, (i) angle embedding of features scaled by trainable weights (re-uploaded each layer),
(ii) trainable single-qubit rotations, (iii) an entangling block. The entangling pattern is the primary
experimental knob:

- **Star-native pattern** (entangle outer qubits only via the hub) → minimal SWAP overhead (baseline).
- **All-to-all pattern** → maximal routing → SWAP count scales up.

This design uses re-uploading as the *encoding* (motivated by the better-performing quantum-neural-network
family in Bowles, Ahmed & Schuld, arXiv:2403.07059) while retaining genuine entanglement, which is the
*object of study* — the source of the two-qubit gates that become SWAPs. We do **not** claim a quantum
learning advantage; the VQC is a representative, well-characterized small model whose behavior under
routing noise we probe.

**Datasets.**
- **`two_curves`** (from `qml-benchmarks`, arXiv:2403.07059), d = 2–4: Fourier-embedded binary task with
  difficulty controlled by Fourier degree; pairs naturally with the Fourier structure of re-uploading.
  *Primary dataset.*
- **Iris**, binary subset (setosa vs. versicolor, 4 features → 4 qubits): real, universally reproducible
  known-answer sanity check (cite UCI / Fisher, **not** the benchmark paper).



---

## 7. Experimental Workflow and Pipeline

QEM is organized into two phases — **noise calibration** (measuring the strength of noise components) and
**response measurement** (measuring how the observable responds to controlled noise changes) — combined to
build an error-mitigated estimator.

**The VQC–ZNE pipeline (per routing level):**
1. **Compilation & routing.** Compile the fixed logical VQC under increasing routing constraints
   (star-native → forced-distant → all-to-all), recording the **transpiled two-qubit-gate count** and depth.
2. **Baseline hygiene.** Apply Readout Error Mitigation (REM) and Dynamical Decoupling (DD) to *every*
   circuit before ZNE, suppressing measurement error and idle decoherence.
3. **Noise amplification.** Boost noise controllably via unitary/gate folding (or pulse stretching where
   available), at several amplification factors.
4. **Execution.** Run primary and noise-boosted circuits for N_shots to estimate noisy expectation values.
5. **Post-processing.** Fit extrapolation models (linear / Richardson / exponential), record recovered
   estimates **and fit residuals/uncertainty**.
6. **Independent yardstick.** Run **mirror circuits** at each routing level to measure task-agnostic
   effective circuit fidelity.
7. **Collapse detector.** Track output/gradient variance vs. two-qubit-gate cost.

**Controlling confounds.** Where possible, keep the same logical circuit and the same target physical qubits,
varying only the router/layout so that two-qubit-gate count changes while the payload is fixed. Report all
results against transpiled two-qubit-gate count, not nominal SWAP count.

---

## 8. Planned Expansions (cross-topology contribution)

- **Topology-as-variable (headline).** Run the identical logical VQC on Tiers A/B/C and show how the
  ZNE-usable frontier shifts with size and connectivity.
- **Native vs. non-native entanglement.** Quantify the accuracy lost by ignoring native topology
  (star-native vs. all-to-all at matched expressivity) → direct design guideline.
- **Mitigation comparison.** ZNE vs. **Clifford Data Regression (CDR)** under identical routing sweeps;
  identify which degrades first and which ZNE extrapolation model breaks first.

---

## 9. Month 1 

### Preparation 
- **literature core.**  ZNE (folding + extrapolation models),
  CDR, noise-induced barren plateaus (Wang et al. 2021), topology-aware routing, REM/DD, and the
  benchmark paper (2403.07059). *Output:* 1-page annotated bibliography.
- **Implement ansatz.** Parameterized HEA-with-reuploading; both star-native and all-to-all
  entangling patterns; variable layers. *Output:* `ansatz.py` + unit test that circuit builds for n = 2..5.
- **Dataset loaders + pre-flight.** `two_curves` (d = 2, 3) and train VQC in
  noiseless simulator; **confirm above-chance accuracy** (target ≥ ~90% on the easy setting). Pick the
  dataset that passes. *Output:* baseline accuracy table + saved trained parameters.

### Noise model, mapping sweep, pipeline dry-run
- ** Noise-calibrated simulator.** Build a device-calibrated noisy simulator from Tier A
  calibration data. *Output:* `noisy_sim.py`; sanity check that simulated readout/2q errors match device specs.
- **Mapping/routing sweep script.** Emit circuits with a monotonic ladder of transpiled
  two-qubit-gate counts (via layout + entangling pattern); log gate count and depth per level.
  *Output:* `routing_sweep.py` + CSV of (level → 2q-gate count, depth).
- **Baseline hygiene integration.** Wire REM + DD into the compile pipeline. *Output:* pipeline
  produces REM+DD-protected circuits; before/after readout-fidelity check on simulator.
- **Full ZNE dry-run in simulation.** End-to-end: routed circuit → DD/REM → folding → execute
  (noisy sim) → extrapolate → recovered accuracy + fit residuals, across the routing ladder.
  *Output:* first *simulated* "accuracy vs. 2q-gate cost" curve; go/no-go review.
- **[Extra] CDR preparation.** Scaffold near-Clifford training-circuit generation and the CDR regression fit.

**End-of-Month-1 deliverables (definition of done):**
- Working ansatz + confirmed noiseless classifier (pre-flight passed).
- Noise-calibrated simulator reproducing Tier A error rates.
- Routing sweep emitting a documented ladder of two-qubit-gate costs.
- REM + DD + ZNE pipeline validated end-to-end **in simulation**.


---

## 10. Month 2 — Hardware Execution & Analysis (strict)

### Tier A (5-qubit star) hardware campaign
- Calibrate/verify against live device; run the full routing ladder on the star device with DD + REM + ZNE.
- Collect **mirror-circuit** fidelities and **gradient/output variance** at each routing level.
- Repeat the sweep across **≥3 separate calibration windows** to quantify drift. *Output:* raw Tier A dataset (or pilot study - idea to check).

### Analysis & threshold characterization (Tier A)
- Correlate transpiled 2q-gate count ↔ mirror-circuit fidelity ↔ ZNE-recovered accuracy.
- Identify the **breakdown region** (where fit residuals / error bars diverge) and the **collapse point**
  (variance → 0). Fit and compare extrapolation models (linear / Richardson / exponential).
- *Output:* Tier A "recovered accuracy & variance vs. 2q-gate cost" curves with error bands; documented
  breakdown/collapse regions.

### Tier B & C validation (20- and 54-qubit)
- Confirm whether the frontier shifts with size/connectivity as predicted. *Output:* cross-topology comparison dataset.
- **[Extra] Method comparison.** Run CDR under identical routing on Tier A (and one Tier B point) to compare
  resilience against ZNE.

### Synthesis & final deliverables
- Assemble publication-ready figures: accuracy vs. 2q-gate cost per tier, cross-topology overlay, ZNE-vs-CDR
  comparison, variance-collapse plot annotated with the barren-plateau connection.
- Write up methodology, confound controls, and the **hardware-aware compilation guideline** (the practical
  takeaway: recommended two-qubit-gate budget per topology for ZNE to remain worthwhile).
- *Output:* draft report/paper section + reproducible code release + archived datasets.

**End-of-Month-2 deliverables (definition of done):**
- ZNE-recoverable frontier characterized on Tier A with uncertainty over ≥3 calibrations.
- Cross-topology validation on Tiers B/C at bracketing routing levels.
- Publication-ready curves marking the breakdown and collapse regions.
- (Extra) ZNE-vs-CDR resilience comparison.
- A concrete, defensible hardware-aware compilation guideline.

---

## 11. Success Criteria & Risks

**Success criteria.**
- A statistically meaningful, drift-aware relationship between two-qubit-gate cost and ZNE-recovered
  accuracy on real hardware.
- A clearly identified breakdown region, corroborated by an independent fidelity yardstick (mirror circuits).
- Consistency (or a characterized difference) across at least two topologies.

**Risks & mitigations.**
| Risk | Mitigation |
|------|-----------|
| Noiseless VQC fails to learn the dataset | Mandatory pre-flight gate; Iris fallback |
| Limited Tier B/C queue access | Do full sweeps on Tier A; use B/C only for bracketing points |
| Calibration drift confounds threshold | Repeat sweeps over ≥3 windows; report error bands, not a constant |
| SWAP-count confounded by qubit choice/depth | Fix payload + target qubits; vary only routing; report transpiled 2q count |
| Hardware training too expensive | Train in calibrated simulator; run only inference + ZNE on hardware |
| ZNE model choice biases result | Compare linear/Richardson/exponential; report which breaks first |

---

## 12. Introduction

The primary goal of quantum error mitigation (QEM) is to translate continuous progress in quantum
hardware into immediate improvements for quantum information processing [1]. Accepting that hardware
imperfections limit algorithmic complexity, every hardware advance should push this boundary further [1].

QEM schemes reduce the noise-induced bias in expectation values by post-processing outputs from an
ensemble of circuit runs, using circuits at the same noise level as the original or above [1]. QEM reduces
the effective damage of noise across the ensemble via post-processing; the noise level of any individual
circuit run remains unchanged or increases [1].

In contrast to Quantum Error Correction (QEC), there is no specific error threshold that must be surpassed
before QEM is useful; different qubit-operation error rates simply lead to different circuit sizes for which
QEM is practical [1]. As hardware advances, QEM applies to ever-larger circuits for more challenging
applications [1]. This work asks the complementary, practical question: for a fixed device and a routing-
heavy variational workload, **how large a two-qubit-gate budget can ZNE actually absorb before it stops
being worthwhile?**

---

## References

- [1] Quantum error mitigation review — *(insert full citation, e.g., Cai et al., Rev. Mod. Phys. 2023)*.
- Bowles, Ahmed & Schuld, *Better than classical? The subtle art of benchmarking quantum machine learning models*, arXiv:2403.07059 (2024).
- Wang et al., *Noise-induced barren plateaus in variational quantum algorithms*, Nature Communications 12, 6961 (2021).
- Temme, Bravyi & Gambetta, *Error mitigation for short-depth quantum circuits* (ZNE), PRL 119, 180509 (2017).
- Czarnik et al., *Error mitigation with Clifford quantum-circuit data* (CDR), Quantum 5, 592 (2021).
- Fisher, R.A., *Iris* dataset (UCI Machine Learning Repository).
