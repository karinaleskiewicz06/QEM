# Codebase Structure

**Analysis Date:** 2026-08-25

## Directory Layout

```
/Users/karinaleskiewicz/QEM/
├── ansatz.py                      # HardwareEfficientAnsatz circuit builder (data re-upload + entanglement patterns)
├── noisy_sim.py                   # DeviceCalibration, Aer noisy simulator, execute_expectation, frozen model loading
├── topology.py                    # Device coupling maps registry (ODRA/Garnet/Emerald), placement strategies
├── cdr.py                         # Clifford Data Regression: near-clifford training, fit_cdr, apply_cdr
├── qec422.py                      # [[4,2,2]] error detection: encode, decode, post-select, measure logical observable
├── zne_dryrun.py                  # ZNE with folding + DD/REM ablations; zero-noise extrapolation
├── metrics.py                     # Classifier metrics: accuracy, macro_f1
├── shots_to_target.py             # Cost currency: effective_shots for each method; cost comparison functions
├── iqm_resonance.py               # IQM Resonance adapter: get_backend, transpile_for_backend, submit
│
├── train_vqc.py                   # Train the reference classifier (Month-1 locked model)
├── train_patterns.py              # Train per-pattern classifiers (star, linear, circular, all_to_all)
├── train_hard.py                  # Train the harder task variant (trained_models_hard/)
├── freeze_reference.py            # Freeze the ideal expectation values on the eval subset (.npz)
│
├── run_cdr.py                     # SIM runner: CDR over the routing ladder (device-generic)
├── run_qec422.py                  # SIM runner: [[4,2,2]] detection over the routing ladder
├── zne_dryrun.py                  # SIM runner: ZNE with DD/REM ablations (main Month-1 baseline)
├── random_mirror_benchmark.py     # SIM runner: mirror-fidelity benchmark (mini study)
├── demo_hard_accuracy.py          # SIM runner: validate hard task with accuracy response
│
├── run_garnet.py                  # HARDWARE runner: Garnet ZNE (optimal vs adverse placement)
├── run_garnet_cdr.py              # HARDWARE runner: Garnet CDR
├── run_garnet_qec.py              # HARDWARE runner: Garnet [[4,2,2]] detection
├── run_garnet_mirror.py           # HARDWARE runner: Garnet mirror (exact U†U arm)
├── run_garnet_smoke.py            # HARDWARE runner: smoke test (single circuit, few shots)
├── run_hardware.py                # Older ODRA hardware runner (Month-1, via iqm-client; deprecated)
│
├── collect_odra_calibration.py    # Pull live T1/T2/readout error from ODRA; write calibration JSON
├── pull_garnet.py                 # Pull live coupling map from Garnet backend; write calibration JSON
├── make_figures.py                # Generate paper figures from CSV results
├── make_method_comparison.py      # Generate method-comparison plots (shots-to-target)
├── routing_sweep.py               # Sweep routing overhead across devices/patterns
├── mirror_fidelity_two_curves.py  # Measure mirror-fidelity (U†U identity survival)
│
├── test_ansatz.py                 # Unit tests: HardwareEfficientAnsatz
├── test_topology.py               # Unit tests: device coupling maps, placement derivation
├── test_cdr.py                    # Unit tests: CDR fitting, Clifford snapping
├── test_metrics.py                # Unit tests: accuracy, F1
├── test_qec422.py                 # Unit tests: [[4,2,2]] encoding, parity checks
│
├── trained_models/                # Month-1 locked reference model (LOCKED.json selects by tag)
│   ├── LOCKED.json                # {"locked_tag": "two_curves_d8_q5_deg8_star_mean_L3"}
│   ├── two_curves_d8_q5_deg8_star_mean_L3.json      # Model config: n_qubits, n_layers, weights_file, test_acc, ...
│   ├── two_curves_d8_q5_deg8_star_mean_L3_weights.npy        # Trained weights (frozen)
│   ├── two_curves_d8_q5_deg8_star_mean_L3_reference.npz      # Frozen eval subset: X_eval, y_eval, ideal_eval
│   ├── two_curves_d8_q5_deg8_linear_mean_L3.json              # Per-pattern models (alt patterns)
│   ├── two_curves_d8_q5_deg8_linear_mean_L3_weights.npy
│   ├── two_curves_d8_q5_deg8_circular_mean_L3.json
│   ├── two_curves_d8_q5_deg8_circular_mean_L3_weights.npy
│   ├── two_curves_d8_q5_deg8_all_to_all_mean_L3.json
│   ├── two_curves_d8_q5_deg8_all_to_all_mean_L3_weights.npy
│   └── ... (other configs, depth sweeps, etc.)
│
├── trained_models_hard/           # Month-2 harder task variant (same structure as trained_models/)
│   ├── LOCKED.json
│   ├── two_curves_d8_q5_deg8_star_mean_L3.json      # offset=0.1 (harder), N=300 samples, 100 eval pts
│   ├── two_curves_d8_q5_deg8_star_mean_L3_weights.npy
│   ├── two_curves_d8_q5_deg8_star_mean_L3_reference.npz
│   └── ... (per-pattern variants)
│
├── calibrations/                  # Device calibration JSONs (T1, T2, gate errors, coupling maps, p_ro)
│   ├── odra.json                  # Live ODRA calibration (from collect_odra_calibration.py)
│   ├── garnet.json                # Live Garnet calibration (from pull_garnet.py)
│   └── emerald.json               # Live Emerald calibration (if available)
│
├── figures/                       # Paper figures (matplotlib .png outputs)
│   ├── zne_ablation.png           # Error vs method + ablation (raw vs ddrem vs zne)
│   ├── method_comparison.png      # Shots-to-target curve (ZNE vs CDR vs [[4,2,2]])
│   ├── routing_overhead.png       # Transpiled CZ count vs pattern/placement/device
│   └── ...
│
├── banknote_study/                # Second study: banknote classification (simpler task, upstream comparison)
│   ├── run_cv_banknote.py         # Classical CV baseline
│   ├── run_zne_banknote.py        # ZNE on banknote
│   ├── run_hardware_banknote.py   # Hardware banknote (older iteration)
│   ├── noiseless_and_cost.py      # Noiseless sim + cost analysis
│   ├── mirror_fidelity.py         # Mirror-fidelity on banknote
│   └── upstream/                  # Dependency: qml-benchmarks library code
│       ├── tests/
│       └── scripts/
│
├── plan.md                        # Month-1 research plan (ansatz design, ZNE strategy, baselines)
├── plan_month_2.md                # Month-2 plan (cross-topology routing, CDR, [[4,2,2]], lattice devices)
├── methodology_month_2.md         # Detailed methodology for Month-2 (§1–§7 per runner)
├── qec422_design_justification.md # Rationale for [[4,2,2]] arm design (Vuillot-style encoding, mirror vs surrogate)
├── dataset_specification.md       # Two-curves dataset: generation, preprocessing, eval subset
├── hardware_runbook.md            # Operational guide: how to submit to ODRA/Garnet/Emerald
├── knowladge.md                   # Research notes + design decisions (informal)
│
├── raport_month_1.tex / .pdf      # Month-1 report (LaTeX + compiled PDF)
├── raport_month_2.tex / .pdf      # Month-2 report
│
├── cdr_results.csv                # CDR runner output: device, placement, pattern, err_raw, err_cdr, acc_raw, acc_cdr, r2, effective_shots
├── qec422_results.csv             # [[4,2,2]] runner output: device, placement, pattern, err_raw, err_detection, acc_raw, acc_detection, acceptance_rate, effective_shots
├── zne_dryrun_results.csv         # (implied) ZNE runner output: pattern, err_raw, err_ddrem, err_zne, acc_raw, acc_ddrem, acc_zne, effective_shots
├── garnet_gonogo_results.csv      # Garnet hardware (gonogo mode): placement, pattern, err_raw, err_zne, acc_raw, acc_zne, effective_shots, transpiled_cz
├── garnet_full_results.csv        # Garnet hardware (full mode): same columns, larger dataset
├── random_mirror_results.csv      # Mirror-fidelity benchmark: pattern, fidelity_perfect, fidelity_noisy, fidelity_hardware
├── hard_accuracy_results.csv      # Hard task accuracy: pattern, acc_raw, acc_zne
│
├── .planning/codebase/            # GSD codebase mapping (this directory)
│   ├── ARCHITECTURE.md            # (generated) Architecture, data flow, abstractions, entry points
│   └── STRUCTURE.md               # (generated) Directory layout, key locations, naming conventions
│
├── .claude/                       # Claude Code project metadata
├── .git/                          # Git history
└── __pycache__/, .pytest_cache/   # Build artifacts (gitignored)
```

## Directory Purposes

**Core Algorithm Modules:**
- Purpose: Core quantum + classical machine learning logic; reusable by all runners
- Contains: ansatz.py, noisy_sim.py, topology.py, cdr.py, qec422.py, zne_dryrun.py (ZNE primitives only), metrics.py, shots_to_target.py
- Key files: `ansatz.py` (circuit design), `noisy_sim.py` (simulation infrastructure), `topology.py` (device registry)

**Training & Model Freezing:**
- Purpose: Generate and lock trained models (one-time execution; results committed to git)
- Contains: train_vqc.py, train_patterns.py, train_hard.py, freeze_reference.py
- Output: trained_models/ and trained_models_hard/ directories (JSON configs + .npy weights + .npz eval sets)
- Frequency: Rarely run; train_patterns.py and train_hard.py take ~tens of minutes

**SIM Runners (Simulation-Based Experiments):**
- Purpose: Benchmark methods on noisy simulator; no QPU cost
- Contains: run_cdr.py, run_qec422.py, zne_dryrun.py, random_mirror_benchmark.py, demo_hard_accuracy.py
- Entry point: Each has main(); run as `python run_X.py --device ... --options ...`
- Output: CSV files (one row per device/placement/pattern combination)
- Frequency: Daily during development; outputs are not committed (results are ephemeral)

**HARDWARE Runners (Real Device Submission):**
- Purpose: Submit to Garnet/Emerald via IQM Resonance API; costly (credits)
- Contains: run_garnet.py, run_garnet_cdr.py, run_garnet_qec.py, run_garnet_mirror.py, run_garnet_smoke.py
- Environment: Requires IQM_RESONANCE_URL + IQM_TOKEN in shell
- Entry point: Each has main(); run as `python run_garnet.py --mode gonogo`
- Output: CSV files; typically committed as Appendix in reports
- Frequency: Weekly or per campaign; gated behind --mode and credit budget

**Utility & Analysis Scripts:**
- Purpose: One-off calibration pulls, figure generation, sweeps, validation
- Contains: collect_odra_calibration.py, pull_garnet.py, make_figures.py, make_method_comparison.py, routing_sweep.py, mirror_fidelity_two_curves.py
- Output: calibrations/*.json (committed), figures/*.png (not committed), sweep CSVs (ephemeral)

**Unit Tests:**
- Purpose: Validate core logic (ansatz parameters, topology lookups, CDR fitting, metrics)
- Contains: test_*.py files (pytest convention)
- Run: `pytest` or `pytest test_cdr.py -v`
- Frequency: Before commits; should pass on every version

**Model Storage (trained_models/, trained_models_hard/):**
- Purpose: Persist trained weights + configs + frozen reference values
- Key files per model: {tag}.json (config), {tag}_weights.npy (trained parameters), {tag}_reference.npz (frozen eval data)
- LOCKED.json: Points to the canonical model tag (e.g., "two_curves_d8_q5_deg8_star_mean_L3") used by all runners
- Invariants: Weights are immutable (read-only .npy); configs are static; no model retraining at runtime
- Structure: Flat directory (no subdirs); names encode hyperparameters (dataset, d, q, degree, pattern, readout, L)

**Calibration Storage (calibrations/):**
- Purpose: Persist live device calibrations (T1, T2, gate errors, coupling maps, readout errors)
- Format: JSON (load via load_iqm_calibration in noisy_sim.py)
- Sources: collect_odra_calibration.py (ODRA), pull_garnet.py (Garnet backend)
- Invariants: Stale calibrations can silently break results; update before quantitative runs
- Use: Passed to --calibration flag in SIM runners; hardware runners pull live properties from backend

**Figures (figures/):**
- Purpose: Store matplotlib .png outputs for papers + presentations
- Source: make_figures.py (reads CSV results, generates plots)
- Contents: Error curves (ZNE vs CDR vs [[4,2,2]]), routing overhead, mirror fidelity, shots-to-target
- Frequency: Regenerated weekly; not version-controlled (results vary with code)

**Secondary Study (banknote_study/):**
- Purpose: Independent reproduction on simpler task; upstream qml-benchmarks library comparison
- Contains: run_*.py (CV baseline, ZNE, hardware), noiseless_and_cost.py, mirror_fidelity.py
- Output: Separate CSV results; used to validate methodology on a different dataset
- Status: Month-2 addition; not essential to main pipeline

**Documentation:**
- plan.md: Research plan (Month-1) — ansatz design, ZNE strategy, Month-1 baselines
- plan_month_2.md: Month-2 extended plan (routing study, lattice devices, new methods)
- methodology_month_2.md: Detailed methodology per runner (§1–§7); the authoritative reference for what each runner does
- qec422_design_justification.md: Encoding design rationale (why Vuillot-style, why mirror vs surrogate)
- dataset_specification.md: Two-curves generation, preprocessing, eval subset size/composition
- hardware_runbook.md: Operational guide (how to set IQM_RESONANCE_URL, how to read backend properties, credit budgeting)
- knowladge.md: Research notes + informal decisions (not a spec; for context)

**Reports:**
- raport_month_1.tex / .pdf: Month-1 report (compiled LaTeX with results + figures)
- raport_month_2.tex / .pdf: Month-2 report (extended methodology + new results on Garnet/Emerald)

**Result CSVs:**
- cdr_results.csv: CDR error, accuracy, fit quality (r2)
- qec422_results.csv: [[4,2,2]] error, acceptance rate after post-selection
- zne_dryrun_results.csv: ZNE error (implied; typically saved to disk by zne_dryrun.py)
- garnet_gonogo_results.csv: Garnet hardware results, gonogo mode (2 patterns, 5 pts, cheap)
- garnet_full_results.csv: Garnet hardware results, full mode (4 patterns, 15 pts, higher cost)
- random_mirror_results.csv: Mirror-fidelity benchmark
- hard_accuracy_results.csv: Hard task accuracy validation
- Status: Ephemeral during development (not in git); final results committed to Appendix

## Key File Locations

**Circuit & Ansatz:**
- `ansatz.py`: HardwareEfficientAnsatz class, entangling_pairs(), build_ansatz() function
  - Key methods: build() (returns QuantumCircuit), feature_parameters(), weight_parameters()
  - Constants: ENTANGLEMENT_PATTERNS, ENTANGLING_GATES

**Device/Simulation Infrastructure:**
- `noisy_sim.py`: DeviceCalibration, make_noisy_simulator(), execute_expectation(), load_frozen_model()
  - Key functions: execute_expectation (the executor for all methods)
  - load_frozen_model: entry point to reconstruct model from disk
  - Noise model: build_noise_model() (1q, 2q, idle, readout channels)
  - Idle scheduling: schedule_with_idle() (expand delays to id gates)
  
- `topology.py`: device_coupling_map(), placement(), HARDWARE_PLACEMENTS
  - Registry: DEVICES (odra, garnet, emerald)
  - Functions: star_coupling_map(), grid_coupling_map(), derive_placements(), topological_distance()
  - PLACEMENTS: ideal-grid (simulator), HARDWARE_PLACEMENTS: hand-validated (real devices)

**Mitigation Methods:**
- `cdr.py`: near_clifford_training_circuits(), fit_cdr(), apply_cdr()
  - Key function: clifford_ideal_expval() (Statevector for exact ideal)
  - Angle snapping: _snap_nearest(), CLIFFORD_ANGLES

- `qec422.py`: encode_422(), decode_422(), postselect_z_parity(), logical_z_expval()
  - Building: build_detection_mirror(), build_encoded_surrogate()
  - Constants: Z_LOGICAL1, Z_LOGICAL2 (weights for readout)

- `zne_dryrun.py`: fold_global(), extrapolate()
  - ZNE primitives: fold_global (U(U†U)^k at odd scales)
  - Extrapolation: linear, richardson, exponential (with clamping for breakdown)

**Metrics & Cost:**
- `metrics.py`: accuracy(), macro_f1()
  - Simple functions; used by all runners for result rows

- `shots_to_target.py`: zne_effective_shots(), cdr_effective_shots(), qec_effective_shots()
  - Cost multipliers: method-specific overhead
  - Utilities: compare_methods(), shots_to_target_curve() (interpolation for crossing)

**Hardware Submission:**
- `iqm_resonance.py`: get_backend(), transpile_for_backend(), submit()
  - Thin adapter; all qiskit-iqm calls isolated here
  - collect_calibration(): pull live properties and write JSON

**Training:**
- `train_vqc.py`: Reference model training (Month-1 locked)
- `train_patterns.py`: Per-pattern classifiers
- `train_hard.py`: Harder task (offset=0.1)
  - Each defines build_qnn(), train() (PyTorch loop), acc() (evaluation)
  - Frozen output: trained_models/ or trained_models_hard/

**SIM Runners (Entry Points):**
- `run_cdr.py:main()` — SIM CDR runner; --device, --placement, --n-train, --calibration
- `zne_dryrun.py:main()` — SIM ZNE runner; --quick, --shots, --reps, --dd, --rem
- `run_qec422.py` (implied): SIM [[4,2,2]] runner
- `demo_hard_accuracy.py`: Validate hard task accuracy response

**HARDWARE Runners (Entry Points):**
- `run_garnet.py:main()` — HARDWARE Garnet; --mode (gonogo|full), --placements, --patterns
- `run_garnet_cdr.py`, `run_garnet_qec.py`, `run_garnet_mirror.py`, `run_garnet_smoke.py` (implied)

**Tests:**
- `test_ansatz.py`: HardwareEfficientAnsatz construction + parameters
- `test_topology.py`: Coupling map registry, placement lookup, distance computation
- `test_cdr.py`: CDR fitting, Clifford angle snapping
- `test_metrics.py`: Accuracy, F1 computation

## Naming Conventions

**Python Files:**
- `ansatz.py`, `noisy_sim.py` — core algorithm modules (snake_case, full words)
- `run_*.py` — runner scripts (run_ prefix)
  - `run_cdr.py`, `run_qec422.py` (method name in suffix)
  - `run_garnet.py`, `run_garnet_cdr.py` (device + method)
- `train_*.py` — training scripts (train_ prefix)
- `test_*.py` — unit tests (test_ prefix, pytest convention)
- Utilities: `make_*.py`, `collect_*.py`, `pull_*.py` (verb + object)

**Classes/Functions:**
- Classes: PascalCase (e.g., HardwareEfficientAnsatz, DeviceCalibration)
- Functions: snake_case (e.g., build_ansatz, execute_expectation, near_clifford_training_circuits)
- Constants: UPPER_CASE (e.g., ENTANGLEMENT_PATTERNS, LADDER_PATTERNS, SCALE_FACTORS, IQM_BASIS_GATES)

**Model/Result Files:**
- Model configs: `two_curves_d{d}_q{n}_deg{degree}_{pattern}_{readout}_L{L}.json`
  - Example: `two_curves_d8_q5_deg8_star_mean_L3.json`
  - Fields: dataset, d, n_qubits, degree, pattern, readout, n_layers
  
- Weights: `{tag}_weights.npy` (numpy array, shape (num_weights,))
  - Example: `two_curves_d8_q5_deg8_star_mean_L3_weights.npy`
  
- Frozen eval: `{tag}_reference.npz` (numpy archive with X_eval, y_eval, ideal_eval)
  - Example: `two_curves_d8_q5_deg8_star_mean_L3_reference.npz`
  - Keys: X_eval (n_eval, n_features), y_eval (n_eval,), ideal_eval (n_eval,)

- Result CSVs: `{method}_{device}_{variant}_results.csv`
  - Examples: `cdr_results.csv`, `garnet_gonogo_results.csv`, `zne_dryrun_results.csv`
  - Columns: device, placement, pattern, err_raw, err_{method}, acc_raw, acc_{method}, effective_shots, transpiled_cz, ...

**Directories:**
- `trained_models/`, `trained_models_hard/` — frozen model storage
- `calibrations/` — device calibration JSONs
- `figures/` — output plots
- `banknote_study/` — secondary study

## Where to Add New Code

**New Mitigation Method:**
1. Create `{method}.py` in root (e.g., `ddec.py` for Dynamical Decoupling Error Correction)
2. Implement method primitives: build-/apply functions (follow cdr.py or qec422.py pattern)
3. Create `run_{method}.py` SIM runner (copy run_cdr.py, substitute method calls)
4. Create `run_garnet_{method}.py` HARDWARE runner (copy run_garnet.py, substitute method calls)
5. Update `metrics.py` or `shots_to_target.py` if method has a new cost model
6. Add unit tests: `test_{method}.py`

**New Device Support:**
1. Add entry to `topology.DEVICES` (e.g., "ibm_heron": {num_qubits: 156, topology: "grid", ...})
2. Add coupling_map function (use grid_coupling_map or custom)
3. Add hand-picked PLACEMENTS[device] (optimal + adverse) for the simulator
4. Add HARDWARE_PLACEMENTS[device] (optimal + adverse) with real qubits (initially None)
5. Once live device is available, run topology.derive_placements(live_coupling_map) to auto-suggest; hand-validate and fill
6. No changes to runners needed; they are device-generic

**New Entanglement Pattern:**
1. Add pattern name to `ansatz.ENTANGLEMENT_PATTERNS`
2. Add case to `entangling_pairs()` function in ansatz.py
3. Runners will auto-discover the new pattern (LADDER_PATTERNS looks up patterns at runtime)

**New Analysis Script:**
- Create `analyze_{topic}.py` (e.g., `analyze_breakdown_regions.py`)
- Read CSVs (cdr_results.csv, garnet_full_results.csv, etc.) via pandas or numpy
- Output: plots (make_figures.py style) or updated CSVs

**New Benchmark Dataset:**
- Add to `train_vqc.py` (if replacing two_curves):
  - new generate_* function (or use qml_benchmarks)
  - retrain with train_vqc.py
  - freeze reference with freeze_reference.py
  - point runners to --models-dir (or new default)
- Keep two_curves tests/configs as regression check

## Special Directories

**trained_models/ & trained_models_hard/:**
- Purpose: Persist trained weights + frozen reference ideal values (no re-training at runtime)
- Generated: By train_vqc.py, train_patterns.py, train_hard.py (one-time)
- Consumed: By load_frozen_model() in all runners
- LOCKED.json: Selects canonical tag; all runners use it unless --models-dir overridden
- Committed: Yes (immutable once locked; part of reproducibility)

**calibrations/:**
- Purpose: Cache live device calibrations (T1, T2, coupling maps, readout errors)
- Generated: By collect_odra_calibration.py (ODRA), pull_garnet.py (Garnet)
- Consumed: By load_iqm_calibration() in noisy_sim.py (via --calibration flag)
- Format: JSON (loadable by load_iqm_calibration)
- Committed: Yes (makes quantitative results reproducible)
- Staleness: Can become stale; check backend properties before quantitative runs

**figures/:**
- Purpose: Store matplotlib .png outputs
- Generated: By make_figures.py (reads CSV results)
- Committed: No (plots regenerated on each figure run; results vary slightly with noise)
- Workflow: Run make_figures.py, check outputs, commit .tex report (not .png)

**banknote_study/:**
- Purpose: Secondary study on simpler dataset; upstream library validation
- Status: Month-2 addition; logically separate from main pipeline
- Committed: Yes (reproducibility)

**.planning/codebase/:**
- Purpose: GSD codebase mapping (this directory)
- Generated: By /gsd-map-codebase skill
- Committed: Yes (informs future Claude instances)
- Refresh: After significant refactors or new architecture layers

---

*Structure analysis: 2026-08-25*
