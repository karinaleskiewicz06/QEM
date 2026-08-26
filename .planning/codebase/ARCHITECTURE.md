<!-- refreshed: 2026-08-25 -->
# Architecture

**Analysis Date:** 2026-08-25

## System Overview

This is a quantum error mitigation (QEM) research pipeline for variational quantum classifiers (VQCs). The system trains parameterized quantum circuits on a classical two-curves classification task, then benchmarks three error-mitigation methods (ZNE, CDR, [[4,2,2]] detection) across device topologies and routing patterns.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TRAINING LAYER (Offline)                             │
├─────────────────────────────┬──────────────────────┬───────────────────────┤
│   train_patterns.py         │   train_vqc.py       │   train_hard.py       │
│   (per-entanglement)        │   (reference model)  │   (harder task)       │
│   `trained_models/`         │                      │   `trained_models_hard/`
└─────────────────────────────┴──────────────────────┴───────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FROZEN CLASSIFIER LAYER (Locked)                       │
│  load_frozen_model() -> (bound_circuit, observable, config)                 │
│  `trained_models/LOCKED.json` selects the locked model by tag               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ANSATZ LAYER (Circuit Construction)                      │
│                          `ansatz.py`                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  HardwareEfficientAnsatz(n_qubits, n_layers, entanglement, ...)             │
│  • Data re-uploading: x[feat % d] scaled by trainable weights               │
│  • Trainable rotations: RY/RZ per qubit per layer                           │
│  • Entanglement patterns: star (hub), all_to_all, linear, circular          │
│  Output: bare state-prep QuantumCircuit with x[...] features, w[...] weights
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
        ┌──────────────────────────────────────────────────────┐
        │              TOPOLOGY LAYER                          │
        │  `topology.py` — device-generic abstraction          │
        ├──────────────────────────────────────────────────────┤
        │  • ODRA (5-qubit star, hub=0)                        │
        │  • Garnet (20-qubit 4x5 grid)                        │
        │  • Emerald (54-qubit 6x9 grid)                       │
        │                                                      │
        │  Provides:                                           │
        │  • device_coupling_map(device) -> coupling_map       │
        │  • placement(device, n_logical, strategy) ->         │
        │    initial_layout for transpilation                  │
        │  • HARDWARE_PLACEMENTS for real devices              │
        └──────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌──────────────────────────┐   ┌──────────────────────────────┐
        │   SIM EXECUTION LAYER    │   │  HARDWARE SUBMISSION LAYER   │
        │   `noisy_sim.py`         │   │  `iqm_resonance.py`          │
        ├──────────────────────────┤   ├──────────────────────────────┤
        │ make_noisy_simulator()   │   │ get_backend(device)          │
        │ DeviceCalibration        │   │ transpile_for_backend()      │
        │ execute_expectation()    │   │ submit(circuits, shots)      │
        │                          │   │                              │
        │ Noise model:             │   │ Targets:                     │
        │ • 1q: thermal + depol    │   │ • IQM Resonance (Garnet,    │
        │ • 2q: depol + thermal    │   │   Emerald)                   │
        │ • Idle: T2*/echo T2      │   │ • qiskit-iqm provider        │
        │ • Readout: bit-flip      │   │ • Real coupling maps         │
        │                          │   │ • Hand-picked placements     │
        │ Idle scheduling:         │   │                              │
        │ schedule_with_idle()     │   │ No idle scheduling on        │
        │ -> id gates carry noise  │   │ real hardware                │
        └──────────────────────────┘   └──────────────────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
        ┌─────────────────────────────────────────────────────────────────────┐
        │               ERROR MITIGATION LAYER (Interchangeable)              │
        ├──────────────────┬──────────────────┬─────────────────────────────┤
        │  ZNE Pipeline    │   CDR Pipeline   │   [[4,2,2]] Detection       │
        │  `zne_dryrun.py` │   `cdr.py`       │   `qec422.py`               │
        ├──────────────────┼──────────────────┼─────────────────────────────┤
        │ fold_global()    │ near_clifford_   │ encode_422()                │
        │ -> U(U†U)^k at   │ training_        │ decode_422()                │
        │   scales [1,3,5] │ circuits()       │ postselect_z_parity()       │
        │                  │ fit_cdr(noisy,   │ logical_z_expval()          │
        │ execute_         │ ideal) -> a,b,r2 │ build_detection_            │
        │ expectation()    │ apply_cdr()      │ mirror()                    │
        │ @ each scale     │                  │                             │
        │                  │ For training:    │ For evaluation:             │
        │ extrapolate()    │ ideal via        │ • Mirror (exact U†U)        │
        │ -> linear,       │ Statevector      │ • Surrogate (Clifford)      │
        │   richardson,    │                  │ Both with post-selection    │
        │   exponential    │ For eval:        │                             │
        │                  │ apply to target's │ Cost factor:               │
        │ Ablations:       │ raw ⟨O⟩           │ shots / acceptance_rate    │
        │ • raw: no DD/REM │                  │                             │
        │ • ddrem: +DD/REM │ Cost factor:     │ Ref: arXiv:1705.08957      │
        │ • zne: full      │ shots*(n_train+1)│                             │
        │                  │                  │                             │
        │ Ref: arXiv:2005. │ Ref: arXiv:2005. │                             │
        │ 10921 (folding)  │ 10189 (CDR)      │                             │
        └──────────────────┴──────────────────┴─────────────────────────────┘
                                    │
                                    ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │                    METRICS & COST LAYER                         │
        │  `metrics.py`, `shots_to_target.py`                             │
        ├─────────────────────────────────────────────────────────────────┤
        │ Accuracy metrics:                                               │
        │ • accuracy(y_true, y_pred) — sign-agreement fraction            │
        │ • macro_f1(...) — unweighted per-class F1                       │
        │                                                                 │
        │ Error signal (primary):                                         │
        │ • mean |⟨O⟩_noisy - ⟨O⟩_ideal| over eval points                │
        │                                                                 │
        │ Cost currency (shots-to-target):                                │
        │ • zne_effective_shots(shots, n_scales, reps)                    │
        │ • cdr_effective_shots(shots, n_train, reps)                     │
        │ • qec_effective_shots(shots, acceptance_rate)                   │
        │ -> all methods on one comparable axis                           │
        └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │                    RUNNER SCRIPTS (Entry Points)                │
        │  Sim: run_cdr.py, run_qec422.py, zne_dryrun.py, ...            │
        │  Hardware: run_garnet.py, run_garnet_cdr.py, run_garnet_qec.py │
        └─────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| HardwareEfficientAnsatz | Build parameterized VQC circuits with configurable entanglement | `ansatz.py` |
| DeviceCalibration | Hold per-qubit noise parameters (T1/T2, gate errors, readout) | `noisy_sim.py` |
| make_noisy_simulator | Assemble Aer NoiseModel + AerSimulator for a device | `noisy_sim.py` |
| execute_expectation | Run a circuit on sim/hardware, measure ⟨O⟩ from counts | `noisy_sim.py` |
| topology.device_coupling_map | Map device name → Qiskit coupling_map | `topology.py` |
| topology.placement | Map device name + strategy → initial_layout for transpilation | `topology.py` |
| topology.HARDWARE_PLACEMENTS | Hand-validated physical-qubit lists for real devices | `topology.py` |
| ZNE pipeline | Fold, execute at multiple noise scales, extrapolate to zero-noise limit | `zne_dryrun.py` |
| CDR pipeline | Build near-Clifford training set, learn linear correction, apply | `cdr.py` |
| QEC detection | Encode in [[4,2,2]], measure, post-select on parity | `qec422.py` |
| iqm_resonance adapter | Get live backend, transpile against real coupling map, submit | `iqm_resonance.py` |
| load_frozen_model | Rebuild trained circuit + observable from `trained_models/` JSON/NPZ | `noisy_sim.py` |
| Runners (SIM) | Per-method per-device driver scripts; output CSV results | `run_cdr.py`, `zne_dryrun.py`, `run_qec422.py` |
| Runners (HARDWARE) | Hardware submission; real QPU execution via iqm_resonance | `run_garnet.py`, `run_garnet_cdr.py`, `run_garnet_qec.py` |

## Pattern Overview

**Overall:** Stratified QEM benchmark pipeline. The system is **device-generic** (single codebase handles ODRA star + Garnet/Emerald lattices) and **method-interchangeable** (ZNE, CDR, QEC are swapped by selecting a runner). Each runner orchestrates:

1. **Load** frozen classifier (weights + observable) from disk
2. **Build** circuits per data point (bind features x; keep weights w pre-bound)
3. **Transpile** to device topology; apply placement on lattices
4. **Execute** via simulator OR hardware, collect counts
5. **Measure** expectation value ⟨O⟩ and error vs ideal
6. **Mitigate** with method-specific post-processing
7. **Compute** accuracy + cost (effective shots)
8. **Report** as CSV row (one per routing level / pattern / placement)

**Key Characteristics:**

- **Frozen model architecture**: Train once (train_*.py), freeze weights + reference ideal values (LOCKED.json), reuse in all runners. Decouples training from evaluation.
- **Observable reuse**: All patterns + methods measure the same observable (Z on hub, or mean-Z); permits direct comparison.
- **Routing-ladder ablation**: Four entanglement patterns (star, linear, circular, all_to_all) on each device/placement, isolating the overhead effect.
- **Placement strategies**: optimal (compact cluster, zero routing on star) vs adverse (dispersed, max routing overhead). **Only** for lattices; star has identity layout.
- **Noise abstraction**: DeviceCalibration holds T1/T2/p_1q/p_2q/p_ro. Placeholder values for lattices; overridable with live calibration JSON (from IQM API).
- **Cost visibility**: Every result row carries effective shots (method-specific multiplier) so methods are compared at matched cost, not matched iterations.

## Layers

**Training Layer** (Offline, train_*.py):
- Purpose: Learn VQC weights on two_curves dataset via PyTorch + gradient descent
- Location: `train_vqc.py` (reference), `train_patterns.py` (per-pattern), `train_hard.py` (harder task)
- Contains: PyTorch QNN wraps the parameterized ansatz; trains weights via MSE loss
- Depends on: ansatz.HardwareEfficientAnsatz, qiskit.QuantumCircuit, torch
- Used by: Produces trained_models/ and trained_models_hard/ directories (LOCKED.json selects one)
- Output: Model config JSON + weights .npy file + reference .npz (ideal values on frozen eval subset)

**Ansatz Layer** (Circuit Construction):
- Purpose: Build parameterized quantum circuits with configurable entanglement
- Location: `ansatz.py` — HardwareEfficientAnsatz class
- Contains: Data re-uploading encoding, trainable rotations, entangling blocks (star / all_to_all / linear / circular)
- Depends on: qiskit.QuantumCircuit, qiskit.ParameterVector
- Used by: All runners; invoked for each (pattern, device) pair
- Characteristics: Fully parameterized until weight-bind; remains feature-free until data-bind

**Device/Simulation Layer**:
- Purpose: Provide device-aware simulation with calibrated noise
- Location: `noisy_sim.py` (simulation) + `topology.py` (topology registry)
- Contains: 
  - DeviceCalibration: per-qubit T1/T2, gate error rates, readout error, coupling map
  - make_noisy_simulator: Aer backend with NoiseModel
  - execute_expectation: transpile + noise schedule + execute + REM/ZNE post-proc
  - load_frozen_model: reconstruct trained circuit + observable from JSON/NPZ
  - Device registry (ODRA star, Garnet grid, Emerald grid); placement strategies
- Depends on: qiskit_aer, qiskit.transpile, topology registry
- Used by: SIM runners (zne_dryrun.py, run_cdr.py, run_qec422.py, ...)
- Characteristics: **Single source of truth** for coupling maps (topology.py); DeviceCalibration is mutable for live calibration (load_iqm_calibration)

**Hardware Adapter Layer**:
- Purpose: Isolate IQM Resonance provider details; keep runners provider-agnostic
- Location: `iqm_resonance.py`
- Contains: get_backend, transpile_for_backend, submit, collect_calibration
- Depends on: qiskit-iqm (IQM Resonance API wrapper)
- Used by: Hardware runners (run_garnet.py, run_garnet_cdr.py, ...)
- Environment: IQM_RESONANCE_URL, IQM_TOKEN (from shell)
- Characteristics: **Thin adapter**; real coupling maps + transpilation happen here; HARDWARE_PLACEMENTS (hand-validated qubits) are validated at submit

**Mitigation Layer** (Interchangeable):
- **ZNE Pipeline** (`zne_dryrun.py`):
  - Purpose: Benchmark unitary-folding ZNE with optional DD + REM ablations
  - Data Flow: circuit → fold at scales [1,3,5] → execute at each scale → extrapolate (linear/richardson/exponential) → zero-noise estimate
  - Cost: shots × n_scales × reps (per zne_effective_shots)
  - Ablations: raw (no DD/REM), ddrem (baseline hygiene), zne (full mitigation)
  
- **CDR Pipeline** (`cdr.py`):
  - Purpose: Learn linear correction from near-Clifford training set
  - Data Flow: circuit → near-clifford training circuits (same structure, random Clifford angles) → ideal via Statevector → noisy via execute → fit ideal ≈ a·noisy + b → apply to target
  - Cost: shots × (n_train + 1) × reps (per cdr_effective_shots)
  - Unique: Does NOT amplify noise (no folding); trades training overhead for safety
  
- **QEC Detection** (`qec422.py`):
  - Purpose: Detect single-qubit errors via [[4,2,2]] code; discard flagged shots
  - Data Flow: encode 5 logical qubits in 4-data-qubit blocks → payload (mirror or surrogate) → measure → post-select on Z-parity → logical observable
  - Cost: shots / acceptance_rate (per qec_effective_shots)
  - Two arms: Mirror (exact U†U) vs Surrogate (near-Clifford)

**Metrics & Cost Layer**:
- Purpose: Unify accuracy + cost metrics across methods
- Location: `metrics.py` (accuracy, macro_f1), `shots_to_target.py` (effective shots, cost functions)
- Used by: All runners report accuracy, error, F1, and effective_shots per row
- Characteristics: Primary signal is mean |⟨O⟩ - ⟨O⟩_ideal| (continuous error); accuracy is secondary (sign decision)

## Data Flow

### Primary Request Path

1. **Load frozen model** (`noisy_sim.load_frozen_model`) — `noisy_sim.py:328`
   - Read LOCKED.json, load weights .npy, reconstruct circuit + observable
   - Return: bound_circuit (weights fixed, features free), observable, config dict
   
2. **Build ansatz per pattern** (`ansatz.HardwareEfficientAnsatz.build()`) — `ansatz.py:151`
   - For each entanglement pattern (star, linear, circular, all_to_all):
   - Construct bare QuantumCircuit with data re-uploading + trainable rotations + entanglers
   - Bind weights from the frozen model
   - Keep feature parameters x[...] free
   
3. **For each eval data point**:
   - Bind features to create fully-bound circuit
   - Compute ideal ⟨O⟩ via Statevector (no noise)
   - Execute on simulator/hardware (multiple times or scales depending on method)
   - Collect counts; measure ⟨O⟩_noisy from counts
   
4. **Apply mitigation**:
   - **ZNE**: fold at [1,3,5]; extrapolate to zero-noise
   - **CDR**: apply learned (a, b) correction
   - **QEC**: post-select on parity; measure logical observable
   
5. **Compute metrics**:
   - Error: |⟨O⟩_mitigated - ⟨O⟩_ideal|
   - Accuracy: sign(⟨O⟩) == sign(y_true)
   - F1: unweighted per-class F1
   - Effective shots: method-specific cost multiplier
   
6. **Output CSV row**:
   - One row per (device, placement, pattern), aggregating all eval points
   - Columns: device, placement, pattern, transpiled_cz, err_raw, err_mitigated, acc_raw, acc_mitigated, effective_shots, ...

### Simulator (zne_dryrun.py) Data Flow

```
load_frozen_model() [fixed circuit + observable]
  ├─ for each pattern in [star, linear, circular, all_to_all]:
  │   ├─ HardwareEfficientAnsatz.build() [bare circuit]
  │   ├─ bind weights
  │   ├─ make_noisy_simulator(DeviceCalibration) [Aer backend]
  │   └─ for each eval point x in X_eval:
  │       ├─ bind features -> bound_circuit
  │       ├─ ideal = Statevector.expectation_value(observable)
  │       ├─ for each scale in [1, 3, 5]:
  │       │   ├─ fold_global(bound_circuit, scale)
  │       │   ├─ schedule_with_idle() [if DD enabled]
  │       │   ├─ execute_expectation(..., rem=True/False) [simulator]
  │       │   ├─ collect noisy_val
  │       ├─ extrapolate([1,3,5], noisy_vals) -> zne_estimate
  │       ├─ accuracy += (sign(zne_estimate) == sign(y))
  │       ├─ error += |zne_estimate - ideal|
  │       └─ append row
  └─ write CSV
```

### Hardware (run_garnet.py) Data Flow

```
load_frozen_model() [fixed circuit + observable]
  ├─ iqm_resonance.get_backend(device) [live backend from Resonance]
  ├─ for each placement in [optimal, adverse]:
  │   ├─ topology.hardware_placement(device, placement) -> layout
  │   ├─ for each pattern in [star, linear, circular, all_to_all]:
  │   │   ├─ HardwareEfficientAnsatz.build() [bare circuit]
  │   │   ├─ bind weights
  │   │   └─ for each eval point x in X_eval:
  │   │       ├─ bind features -> bound_circuit
  │   │       ├─ ideal = Statevector.expectation_value(observable)
  │   │       ├─ for each scale in [1, 3, 5]:
  │   │       │   ├─ fold_global(bound_circuit, scale)
  │   │       │   ├─ measure_all() [classical measurement]
  │   │       │   ├─ transpile_for_backend(..., initial_layout=layout) [real topology]
  │   │       │   └─ batch.append(transpiled_circuit)
  │   │       ├─ backend.run(batch, shots=shots) [submit to hardware]
  │   │       ├─ for each counts in result:
  │   │       │   ├─ perqubit_z_from_counts(counts)
  │   │       │   ├─ [optional] rem_correct_z(...) [REM]
  │   │       │   ├─ extrapolate([1,3,5], vals) -> zne_estimate
  │   │       │   ├─ accuracy += (sign(estimate) == sign(y))
  │   │       │   ├─ error += |estimate - ideal|
  │   │       │   └─ append row
  │   └─ write CSV
```

**State Management:**
- **Frozen model state**: Held in memory (bound_circuit, weights, config) for the entire run; never modified
- **Device state**: DeviceCalibration is immutable once loaded; passed to make_noisy_simulator or used for transpilation
- **Per-circuit state**: Ansatz + features rebound for each eval point; scales/mitigation applied inline
- **Per-method state**: ZNE stores extrapolation parameters (scale factors); CDR stores (a, b, r2); QEC stores (acceptance_rate)

## Key Abstractions

**HardwareEfficientAnsatz:**
- Purpose: Encapsulate the ansatz design space (entanglement patterns, layer count, feature encoding)
- Example: `ansatz.py:78–232` — class with build(), feature_parameters(), weight_parameters()
- Pattern: Dataclass with validation; build() returns a bare QuantumCircuit; no side effects

**DeviceCalibration:**
- Purpose: Unified noise parameters for any device size + topology
- Example: `noisy_sim.py:58–105` — dataclass with scalar→array broadcasting
- Pattern: Holds T1/T2/p_1q/p_2q/p_ro per qubit; coupling_map is set per device; defaults to star
- Mutation: load_iqm_calibration() parses JSON; synthesize_lattice_calibration() generates placeholder

**Coupling Map Registry:**
- Purpose: Single source of truth for device topologies
- Location: `topology.py:21–86` — functions star_coupling_map, grid_coupling_map, device_coupling_map
- Pattern: Named devices → metadata (rows, cols, topology type) → coupling_map on demand
- Extension: DEVICES dict; HARDWARE_PLACEMENTS for real devices (hand-filled)

**Placement Strategy:**
- Purpose: Map logical qubits to physical qubits on lattice devices
- Location: `topology.py:89–172` — PLACEMENTS dict + placement() function + hardware_placement()
- Pattern: (device, strategy) → list[int] (initial_layout for transpile)
- Constraint: Only n_logical == 5 placements hand-picked; raises if unsupported

**Frozen Model Reconstruction:**
- Purpose: Rebuild trained circuit from disk without re-training
- Location: `noisy_sim.py:328–372` — load_frozen_model()
- Pattern: JSON config → HardwareEfficientAnsatz parameters → circ.assign_parameters(weights)
- Invariant: Circuit is **fully weight-bound** but **feature-free** (x[...] remain)

**Observable Construction:**
- Purpose: Unified readout observable (hub Z or mean Z)
- Location: `noisy_sim.py:375–387` — readout_observable()
- Pattern: Diagonal (Z/I only) SparsePauliOp; used by all methods for ⟨O⟩ measurement

**Effective Shots Currency:**
- Purpose: Normalize cost across methods
- Location: `shots_to_target.py:64–76` — zne_effective_shots, cdr_effective_shots, qec_effective_shots
- Pattern: Simple multiplier (no_method cost = 1×, ZNE = n_scales×, CDR = (n_train+1)×, QEC = 1/acceptance×)

## Entry Points

**SIM Runners** (execute on noisy simulator):

1. **zne_dryrun.py** (`zne_dryrun.py:172–250+`):
   - Entry: main() parses --quick, --shots, --reps, --calibration, --dd, --rem, --models-dir
   - Loads frozen model + simulator
   - For each pattern: build circuit, fold at [1,3,5], execute, extrapolate
   - Outputs: zne_dryrun_results.csv (one row per pattern, with error ablations)

2. **run_cdr.py** (`run_cdr.py:73–203`):
   - Entry: main() parses --device, --placement, --n-train, --shots, --quick, --calibration
   - Device-aware: ODRA/star vs Garnet/Emerald with placement
   - For each pattern: fit CDR on training set, apply to eval points
   - Outputs: cdr_results.csv (one row per pattern per device per placement)

3. **run_qec422.py** (implied):
   - Not fully shown in reads; follows run_cdr.py structure
   - For each pattern: encode → payload (mirror or surrogate) → post-select → measure
   - Outputs: qec422_results.csv

4. **random_mirror_benchmark.py** (implied):
   - One-off benchmark of mirror-fidelity across patterns

5. **demo_hard_accuracy.py** (`demo_hard_accuracy.py`):
   - Validates the harder task (trained_models_hard/) shows accuracy response

**HARDWARE Runners** (submit to real device via IQM Resonance):

1. **run_garnet.py** (`run_garnet.py:47–150+`):
   - Entry: main() parses --mode (gonogo|full), --device, --placements, --patterns
   - Loads frozen model; gets live backend (qiskit-iqm)
   - For each placement × pattern: build folded circuits, transpile against real map, batch submit
   - Batching: one job per (placement, pattern) block; amortises per-job cost
   - Outputs: garnet_gonogo_results.csv or garnet_full_results.csv

2. **run_garnet_cdr.py** (implied):
   - run_garnet.py + CDR mitigation

3. **run_garnet_qec.py**, **run_garnet_mirror.py**, **run_garnet_smoke.py** (implied):
   - Variants for other methods + smoke test

**Training** (generate frozen model):

1. **train_vqc.py** (reference, Month-1 locked model)
2. **train_patterns.py** (per-pattern classifiers)
3. **train_hard.py** (harder task, Month-2)

## Architectural Constraints

- **Threading**: Single-threaded event loop. PyTorch (train_*.py) uses thread pools for parallelism; Aer simulator is serial per circuit.
- **Global state**: DeviceCalibration is immutable once loaded (no in-flight mutations). DEVICES registry is read-only. HARDWARE_PLACEMENTS must be pre-filled before submit (no auto-derivation at runtime).
- **Circular imports**: None detected; dependencies flow: ansatz ← noisy_sim ← topology ← (runners); bidirectional imports via re-exports (e.g., noisy_sim re-exports star_coupling_map from topology).
- **Device size mismatch**: execute_expectation handles embedding (n_logical < n_device) via initial_layout + logical_final_wires for readout mapping. Raises if embedding is attempted on pre-transpiled circuits.
- **Frozen model assumption**: All runners assume LOCKED.json exists and selects a valid tag in trained_models/ or trained_models_hard/. No fallback to train-on-the-fly.
- **Coupling map bidirectionality**: All coupling_map lists are bidirectional (both [a,b] and [b,a]). Qiskit's transpile tolerates one-directional input; our lists are defensive.

## Anti-Patterns

### Placeholder Calibration Silently Used in Quantitative Claims

**What happens:** DeviceCalibration() with no args returns Spark-class order-of-magnitude placeholder numbers (T1=40µs, T2=15µs, p_1q=1e-3, p_2q=1e-2, p_ro=3e-2). Lattice devices (Garnet/Emerald) get these broadcast to their grid qubits via synthesize_lattice_calibration(). If live calibration is not loaded (--calibration flag not provided), the sim uses placeholders, but the results may look quantitatively plausible to a user who does not read the code comments.

**Why it's wrong:** Results derived from placeholder noise are not representative of real device performance. Researchers may quote error rates or mitigation speedups without realizing the noise model is synthetic.

**Do this instead:** `load_iqm_calibration(path)` must be called explicitly when quantitative results are needed. The runner should log "Using placeholder calibration" to stderr if --calibration is omitted. Consider raising an error (not a warning) if --calibration is missing and --submit is False but the device is not the default ODRA.

**Reference:** `noisy_sim.py:137–168` (synthesize_lattice_calibration is a stand-in); `run_cdr.py:59–64` (_calibration_for uses placeholder fallback).

### Manual HARDWARE_PLACEMENTS Not Validated at Submit

**What happens:** Hand-picked physical qubits in HARDWARE_PLACEMENTS (e.g., "garnet": [3,0,2,4,8]) are used as initial_layout in transpile_for_backend. If the live backend has disconnected components or these qubits have changed status, transpile may fail silently or produce wrong circuits. The placement is assumed to be validated once by the researcher; no runtime check occurs.

**Why it's wrong:** Device connectivity changes over time. A placement that worked last month may be stale. A typo in the list (e.g., qubit 50 on a 20-qubit device) could slip through if the error is not a hard failure.

**Do this instead:** At submit time, call topology.topological_distance (or backend.configuration().coupling_map) to validate that all qubits in the placement are connected and within device bounds. Log the validated placement. Raise an error if any qubit is out of range or connectivity fails.

**Reference:** `topology.py:154–171` (hardware_placement raises if None; does not validate qubits). `iqm_resonance.py:109–114` (transpile_for_backend does not check layout validity).

### Frozen Model Observable Not Documented at Load

**What happens:** load_frozen_model returns (bound_circuit, observable, config). The observable is reconstructed from config["readout"] (either "hub" or "mean") by readout_observable(). If a runner expects mean-Z but the config specifies hub-Z, or vice versa, the metric comparison is apples-to-oranges. The config is not checked against the runner's assumptions.

**Why it's wrong:** Each runner may implicitly assume a particular observable (e.g., CDR trains on the same observable as the eval). If an older frozen model used a different observable, results silently become incommensurable.

**Do this instead:** runners should assert config["readout"] == expected_readout before using the loaded model. Add a logged summary: "Loaded model {tag} with observable {readout}." Raise an error if there's a mismatch.

**Reference:** `noisy_sim.py:328–372` (load_frozen_model does not validate observable). `run_cdr.py:96–100` (loads model and config but does not assert readout type).

### Routing Cost (transpiled_cz) Not Budgeted in effective_shots

**What happens:** Runners report transpiled_cz (count of CZ gates after routing) but do NOT fold it into effective_shots. Each method has its own cost multiplier (ZNE = n_scales, CDR = n_train+1, QEC = 1/acceptance), but those are the QPU overhead multipliers, not gate counts. On a device where routing is expensive, a "cheap" method (e.g., 3-scale ZNE) might become expensive after routing overhead is accounted for.

**Why it's wrong:** Comparing effective_shots across placements or patterns is incomplete if routing overhead is not normalized. A method that looks cheap on optimal placement may look expensive on adverse placement because the transpiled circuit is much larger.

**Do this instead:** Fold routing overhead into cost. Options:
1. Report both transpiled_cz and effective_shots; let users compute effective_shots_adjusted = effective_shots × (transpiled_cz / baseline_cz).
2. Compute a proxy: assume the device charges per gate; effective_shots_adjusted = effective_shots × transpiled_cz.
3. Measure real QPU time (methodology_month_2.md §5 mentions time-based billing on Resonance); report credits.

**Reference:** `run_cdr.py:142`, `run_garnet.py:122` (transpiled_cz is computed and logged but not folded into effective_shots). `shots_to_target.py` (cost model is method-only, not topology-aware).

## Error Handling

**Strategy:** Fail early with clear messages; do not silently degrade.

**Patterns:**

1. **Missing Files** (frozen model, calibration):
   - load_frozen_model raises FileNotFoundError if no model found in models_dir
   - load_iqm_calibration uses json.loads; propagates JSONDecodeError
   - Both are caught and logged by runners; user is prompted to check paths

2. **Invalid Device Names**:
   - topology._resolve raises ValueError with a list of valid devices
   - Caught by runners; printed to stderr

3. **Incompatible Placement**:
   - topology.placement raises if strategy not in [optimal, adverse]
   - topology.hardware_placement raises if placement is None (not yet filled)
   - Caught by runners; fail before submitting

4. **Embedding Errors**:
   - execute_expectation raises if circuit has n qubits but device has fewer
   - Raises if embedding + pre_transpiled=True (incompatible)
   - Runner authors must not set both

5. **Extrapolation Breakdown**:
   - zne_dryrun.extrapolate clamps non-linear fits to |1.25|; falls back to linear if blown up
   - Logs a fallback; does not raise (graceful degradation)

6. **QisKit-IQM Import**:
   - iqm_resonance._require_qiskit_iqm raises ImportError with install instructions if qiskit-iqm is missing
   - Caught at runner startup; does not fail silently

## Cross-Cutting Concerns

**Logging:** No logging framework (print/stderr only). Runners print progress to stdout; errors to stderr. CSV output is the primary artifact.

**Validation:** Input validation occurs at entry points (argparse). Circuit validation (parameter binding, qubit counts) is deferred to Qiskit (transpile, execute).

**Authentication:** Hardware submission requires IQM_RESONANCE_URL + IQM_TOKEN in environment (iqm_resonance.py:51–60). No credential file; shell env vars only.

**Reproducibility:** Seed control:
- train_*.py: np.random.seed(SEED), torch.manual_seed(SEED)
- zne_dryrun.py: seed_transpiler=42 in transpile calls
- cdr.py: seed param in near_clifford_training_circuits (default 42)
- topology.derive_placements: no seed (deterministic algorithm)

---

*Architecture analysis: 2026-08-25*
