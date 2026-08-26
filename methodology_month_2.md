# Month 2 — Methodology & Pipeline (control document)

**Purpose.** This is the spec you review *before/while* the code is written, so you stay in
control. Every component below is a contract: what it does, which files, the function
signatures, the scientific protocol, the exact commands (sim + hardware), the output schema,
and how it maps to the report. Nothing here runs itself — you run everything.

**Main goal:** real-hardware results on ODRA (star) + Garnet/Emerald (lattice). Simulation is
the *control* and the dry-run gate, never the headline.

---

## 0. Global conventions (inherited from Month 1 unless overridden)

| Thing | Value | Where to change |
|---|---|---|
| Shots | 4096 | `--shots` flag on every runner |
| ZNE noise scales | {1, 3, 5} (unitary folding) | `zne_dryrun.py` / runners |
| Repetitions (error bands) | R = 3 | `--reps` |
| Observable | mean-Z (two_curves) / single-Z on readout wire (Banknote) | frozen model config |
| Primary metric | mean \|⟨O⟩_noisy − ⟨O⟩_ideal\| vs **frozen** noiseless ideal | `freeze_reference.py` |
| Secondary metrics | accuracy (sign decision), macro-F1, mirror fidelity | — |
| Seed | 42 (training + transpiler) | `seed=` / `seed_transpiler=` |
| Cost x-axis | transpiled CZ count (+ SWAP, topo_dist, depth) | `routing_sweep.py` |
| Safety | every hardware script is **dry-run by default**; needs `--submit` | runner argparse |
| Resume | append-only CSV + `--resume` | runner |

**Credentials / environment**
- **ODRA** (Month 1): `iqm-client` + `IQM_SERVER_URL`, `IQM_TOKEN`.
- **Garnet / Emerald** (this month): **IQM Resonance via `qiskit-iqm`**. Env:
  `IQM_RESONANCE_URL` (per-device endpoint) + `IQM_TOKEN`. ⚠️ `qiskit-iqm` must be installed
  in the run environment (it failed on py3.13 in Month 1 — resolve there, e.g. a py3.11 venv).
- Placements on real devices are **hand-given** by you: fill `topology.HARDWARE_PLACEMENTS`
  with real physical-qubit lists after inspecting each backend; hardware transpile uses the
  **backend's live coupling map**, not the idealized grid.

**Pipeline shape (every method reuses this backbone):**
```
frozen model (weights, ideal ⟨O⟩)  ─┐
routing ladder (device, placement) ─┼─►  build circuits ─► [mitigation/QEC] ─►
noise-calibrated sim  OR  real QPU ─┘        execute (shots)     post-process
                                            ─► ⟨O⟩, error, accuracy, fidelity, cost ─► CSV ─► figures
```

---

## 1. Lattice sim-execution (`execute_expectation` + `initial_layout`)

**Goal.** Let the existing pipeline run a 5-qubit VQC on a 20/54-qubit device *in simulation*
by placing it with an explicit layout (optimal/adverse) and reading out the right wires.

**Files.** `noisy_sim.py` (edit), `test_noisy_sim_layout.py` (new).

**Contract.**
- `execute_expectation(..., initial_layout: list[int] | None = None)` — when the device is
  larger than the circuit, transpile onto `cal.coupling_map` with `initial_layout`, run on the
  device-sized sim, and read ⟨O⟩ from the logical qubits' **final** wires.
- New helper `logical_final_wires(transpiled, n_logical) -> list[int]` — derive each logical
  qubit's physical measurement wire from `transpiled.layout.final_index_layout()` (generalises
  the Month-1 Banknote readout-wire fix).
- New helper `perqubit_z_on_wires(counts, wires, device_width) -> np.ndarray`.

**Protocol.** Verify that running a 5-qubit circuit *embedded* on a 5-qubit device (identity
layout) reproduces the same-size path exactly; then that a 5-on-20 run returns finite ⟨O⟩ and
that adverse placement yields larger ⟨O⟩-error than optimal (routing costs quality).

**Command (sim).**
```bash
python zne_dryrun.py --device garnet --placement optimal --calibration <lattice.json>
```

**Output.** Same CSV schema as Month-1 `zne_dryrun_results.csv`, plus `device`, `placement`.

**Report mapping.** Enables the *simulated* optimal-vs-adverse ⟨O⟩-error curves before any QPU
time (W2/W4 sim control).

**Caveats.** Idle scheduling now runs over the full device width; only the placed qubits carry
signal. This path is **sim-only**; hardware readout wires come from the backend layout (§7).

---

## 2. Placeholder lattice calibration (`synthesize_lattice_calibration`)

**Goal.** A stand-in `DeviceCalibration` for Garnet/Emerald so §1/§3/§4 sim runs work *before*
real lattice calibration exists.

**Files.** `noisy_sim.py` (add function).

**Contract.**
- `synthesize_lattice_calibration(device, *, seed=0, **overrides) -> DeviceCalibration` —
  Spark-class scalar error rates (T1 40 µs, T2\* 15 µs, p_1q 1e-3, p_2q 1e-2, p_ro 3e-2)
  broadcast onto the device, with the real grid coupling map; optional per-qubit jitter by
  `seed`; any field overridable.

**Protocol.** Clearly labelled PLACEHOLDER (like the ODRA default). Replaced by real
calibration (§7) before any quantitative lattice claim.

**Command.** Used internally by runners via `--device garnet` when no `--calibration` given.

**Report mapping.** None directly — infrastructure for sim controls.

---

## 3. Clifford Data Regression (CDR) — QEM method #2

**Goal.** A learning-based mitigator that does *not* amplify noise, compared head-to-head with
ZNE along the routing-cost axis (the report's §1 introduction already motivates it).

**Files.** `cdr.py` (new), `run_cdr.py` (new, mirrors `zne_dryrun.py`/`run_hardware.py`),
`test_cdr.py` (new).

**Contract (`cdr.py`).**
- `near_clifford_training_circuits(circuit, n_train=100, n_nonclifford=0, seed=42) -> list` —
  copy the target's structure/routing; snap each rotation angle to the nearest multiple of
  π/2 (optionally leave `n_nonclifford` gates free for a low-stabilizer-rank variant).
- `clifford_ideal_expval(training_circuit, observable) -> float` — exact ⟨O⟩ via
  `qiskit.quantum_info.Clifford` / `StabilizerState` (Gottesman–Knill; no statevector cost).
- `fit_cdr(noisy_vals, ideal_vals) -> (a, b, r2)` — least-squares `ideal ≈ a·noisy + b`.
- `apply_cdr(noisy_target, a, b) -> float`.

**Protocol.** Per ladder rung: build `n_train` near-Clifford circuits → run noisy (sim or QPU)
→ collect (noisy, ideal) pairs → fit (a,b) → apply to the target's raw ⟨O⟩. Run training +
target in the **same job/window** (drift is CDR's Achilles heel). Score on ⟨O⟩-error, accuracy,
and the shots-to-target currency (§5); CDR cost = `n_train × shots` + the target run.

**Commands.**
```bash
python run_cdr.py --device odra   --dry-run                 # validate
python run_cdr.py --device odra   --submit --n-train 100    # ODRA full ladder
python run_cdr.py --device garnet --submit --n-train 100 --placement optimal
```

**Output** `cdr_results.csv`: device, placement, pattern, transpiled_cz, err_raw, err_cdr,
acc_raw, acc_cdr, a, b, r2, n_train, shots, effective_shots.

**Report mapping.** The ZNE-vs-CDR resilience comparison (which breaks first with routing).

**Caveats.** Fully-Clifford training set first (exact, simplest); `n_nonclifford>0` needs a
near-Clifford simulator and is a later refinement. Linear fit first; polynomial optional.

---

## 4. `[[4,2,2]]` error detection — QEC-lite (logical-ish) layer

**Goal.** A near-term "logical" arm: detect (not correct) single-qubit errors and post-select,
comparing encoded vs physical along the routing-cost axis and at optimal vs adverse placement.

**⚠️ Pending your choice** of how it runs the VQC (Options A/B/C/D in chat). Files/contract
below are common; the runner specialises to the chosen option.

**Files.** `qec422.py` (new: encoder, logical ops, parity post-selection),
`run_qec422.py` (new), `test_qec422.py` (new).

**Contract (`qec422.py`).**
- `encode_422() -> QuantumCircuit` — prepare a `[[4,2,2]]` logical basis state on 4 data qubits.
- `logical_ops()` — the available transversal logical gates (Paulis, CNOT₁₂, H⊗H).
- `postselect_parity(counts) -> (kept_counts, acceptance_rate)` — compute XXXX/ZZZZ parity from
  the destructive 4-qubit readout; drop flagged shots (ancilla-free, Vuillot-style).
- Option-specific builder (A: near-Clifford surrogate; C: detection-wrapped mirror; etc.).

**Protocol.** Three arms — bare (physical) / encoded-optimal / encoded-adverse — at matched
logical operation. Metrics: ⟨O⟩-error or fidelity **plus acceptance rate** (kept/raw shots) as
the cost → shots-to-target. A clean negative (overhead > benefit) is a valid result.

**Commands.**
```bash
python run_qec422.py --device garnet --placement optimal --dry-run
python run_qec422.py --device garnet --placement optimal --submit
python run_qec422.py --device garnet --placement adverse --submit
```

**Output** `qec422_results.csv`: device, placement, arm, cost, metric_raw, metric_detected,
acceptance_rate, effective_shots.

**Report mapping.** Encoded-vs-physical comparison (research question 2), fused with mapping.

**Caveats.** Prototype in sim first (can dry-run on ODRA using the hub as a weight-4 ancilla).
`Ry(x)` non-transversal → the chosen option defines exactly what "runs the VQC" means.

---

## 5. Shots-to-target — the common cost currency

**Goal.** Put ZNE, CDR, and `[[4,2,2]]` on one comparable cost axis.

**Files.** `shots_to_target.py` (new), used by §7 figures.

**Contract.**
- `shots_to_target(method, per_rung_result, target_tol) -> float` — effective QPU shots to
  reach a fixed ⟨O⟩-error (or accuracy) tolerance, folding each method's real overhead:
  - ZNE: shots × (#noise-scaled copies) × reps;
  - CDR: shots × (n_train + 1);
  - `[[4,2,2]]`: shots ÷ acceptance_rate (post-selection discards).

**Protocol.** One helper, applied uniformly so no method is compared at unequal cost.

**Report mapping.** The headline "which method pays, up to what 2q budget" figure axis.

---

## 6. Task-agnostic mirror benchmark (methodology strengthener)

**Goal.** Show the routing frontier is a *device* property, not a VQC artifact, using
classifier-independent random/Clifford mirror circuits at matched 2q cost.

**Files.** extend `mirror_fidelity_two_curves.py` **or** new `random_mirror_benchmark.py`.

**Contract.**
- `random_mirror_circuit(n, target_cz, seed) -> QuantumCircuit` — random (Clifford) `U` then
  `U†`, ideal output `|0…0⟩`, transpiled to a chosen 2q-cost.
- Run per device/placement; report survival fidelity `P(|0…0⟩)` vs transpiled CZ.

**Report mapping.** Generality panel next to the VQC mirror-fidelity results.

**Caveats.** Optional but recommended; reuses the mirror-fidelity machinery.

---

## 7. Hardware generalization (ODRA + Garnet/Emerald)

**Goal.** Run the real experiments. Two submit paths: ODRA (`iqm-client`, Month-1 code) and
Garnet/Emerald (**`qiskit-iqm` / IQM Resonance**).

**Files.** `run_hardware.py` (generalise), new `iqm_resonance.py` (Resonance adapter),
`collect_iqm_calibration.py` (or parameterise the ODRA collector),
`topology.py` (add `HARDWARE_PLACEMENTS`).

**Contract.**
- `topology.HARDWARE_PLACEMENTS[device][strategy] = [physical qubit indices]` — **you fill**
  these from the real devices; validated against the backend coupling at runtime.
- `iqm_resonance.submit(circuits, device, shots) -> counts` — qiskit-iqm `IQMProvider`
  targeting the Resonance endpoint; transpile against the **backend's real coupling map**;
  native-gate conversion via the backend's target.
- `run_hardware.py --device {odra|garnet|emerald} --placement {optimal|adverse}` — dispatches
  to the right submit path; `--dry-run` builds/validates locally and submits nothing.

**Protocol.** Smoke test (1 circuit, print raw counts, confirm bit order/readout wire) →
go/no-go (2 patterns, few points) → full ladder. `--max-circuits` guard as in Month 1.

**Commands.**
```bash
# ODRA (unchanged path)
python run_hardware.py --device odra --submit --full --dd-ablation
# Garnet / Emerald (Resonance)
export IQM_RESONANCE_URL="<garnet endpoint>"; export IQM_TOKEN="<resonance token>"
python run_hardware.py --device garnet --placement optimal --submit --smoke
python run_hardware.py --device garnet --placement optimal --submit --go-no-go
python run_hardware.py --device garnet --placement adverse --submit --go-no-go
```

**Output.** `hardware_results_<device>_<placement>.csv` (Month-1 schema + device/placement).

**Report mapping.** All real optimal-vs-adverse, CDR, and encoded-vs-physical hardware results.

**Caveats.** `qiskit-iqm` install (py version); real coupling ≠ idealized grid → placements are
validated against live connectivity; Tier B/C queue is the scheduling risk (full ladders on
ODRA, bracketing points on Garnet/Emerald).

---

## 8. Drift & threshold campaign + synthesis (W4 + W7)

**Goal.** Turn single runs into drift-aware bands and publication figures.

**Files.** extend `make_figures.py`; small `aggregate_windows.py` (mean ± inter-window std).

**Protocol.** Repeat the ODRA ladder over ≥3 calibration windows; locate the breakdown region
(ZNE residuals / error bars diverge) and collapse (output variance → 0, barren-plateau link);
compare linear/Richardson/exponential extrapolators.

**Figures.** per-device accuracy vs 2q cost; optimal-vs-adverse panels; topo_dist ↔ SWAP ↔
degradation correlation; method comparison (ZNE/CDR/[[4,2,2]]) on the shots-to-target axis;
variance-collapse plot.

**Report mapping.** Final results sections + the hardware-aware compilation guideline.

---

## Suggested run order

1. **Sim controls (no credentials):** §1 → §2 → §3 (CDR) / §4 ([[4,2,2]]) dry-runs → §5.
2. **Hardware bring-up:** §7 smoke → go/no-go on ODRA, then Garnet, then Emerald bracketing.
3. **Campaigns:** optimal-vs-adverse ladders; CDR; encoded-vs-physical; ≥3 ODRA windows (§8).
4. **Synthesis:** §6 mirror benchmark + §8 figures + report.

## Definition of done (per the plan)

Cross-topology ladders (≥2 topologies) with drift bands; optimal-vs-adverse with SWAP/depth/
mean-value/fidelity; topo-distance↔SWAP↔degradation correlation; ZNE-vs-CDR-vs-[[4,2,2]] on the
shots-to-target axis; encoded-vs-physical (incl. a clean negative if that's the result);
publication figures + final report + reproducible release.
