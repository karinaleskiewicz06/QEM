# Codebase Concerns

**Analysis Date:** 2026-08-25

## Tech Debt

**Dependency pinning absent:**
- Issue: No `requirements.txt`, `setup.py`, `pyproject.toml`, or lockfile exists; all dependencies are unpinned.
- Files: Project root lacks manifests
- Impact: Dependency drift across environments; reproducing results becomes fragile. `qiskit-aer`, `torch`, `qiskit-iqm` versions can silently change, breaking experiments or altering noise characteristics.
- Fix approach: Create `requirements.txt` with pinned versions (or `pyproject.toml` with `poetry.lock`), document Python version constraints (e.g., py3.11 for `qiskit-iqm`).

**Tag-format string duplication across runners:**
- Issue: The model tag-building logic is repeated verbatim in 6+ files:
  - `run_garnet.py`: lines ~68-69 (tag) + ~76-78 (ptag)
  - `run_garnet_cdr.py`: lines ~48-49, ~56-58
  - `run_cdr.py`: lines ~96-97, ~104-106
  - `run_garnet_smoke.py`: lines ~35-36
  - `run_hardware.py`: lines ~281-282, ~304-306
  - `zne_dryrun.py`: lines ~188-189, ~197-199
- Files: `run_garnet.py`, `run_garnet_cdr.py`, `run_cdr.py`, `run_garnet_smoke.py`, `run_hardware.py`, `zne_dryrun.py`
- Impact: Code maintenance burden; a change to tag format requires edits in 6+ places. Risk of inconsistency if one runner is updated and others are not.
- Fix approach: Extract a helper function (e.g., `model_tag(cfg, pattern=None)` in `noisy_sim.py`) and import it in all runners.

**qiskit-iqm Python version constraint not documented:**
- Issue: `iqm_resonance.py` lines 8-9 note that `qiskit-iqm` "failed to build on py3.13 in Month 1 — use a py3.11 venv", but this constraint is not recorded in a central location (e.g., README, `pyproject.toml` `python_requires`, or `requirements.txt`).
- Files: `iqm_resonance.py` (lines 8-10, comment only)
- Impact: Users attempting to run on py3.13 will encounter a cryptic build failure during `pip install qiskit-iqm`.
- Fix approach: Document the constraint in a top-level `ENVIRONMENT.md` or add to `pyproject.toml`: `python_requires = ">=3.11,<3.13"`.

---

## Known Issues & Limitations

**REM (Readout Error Mitigation) falls back to OFF on Garnet/Emerald:**
- Symptoms: When `backend_readout_errors(backend)` returns `None` (backend does not expose per-qubit readout errors), REM cannot apply mitigation; circuits are executed raw.
- Files: `iqm_resonance.py` lines 69–106; `pull_garnet.py` lines 34–40
- Current state: Documented in `pull_garnet.py` output: "readout errors: NOT exposed by backend -> REM will fall back (pass p_ro by hand, or run REM-off)"
- Impact: On Garnet and Emerald, if the qiskit-iqm backend's API shape does not include per-qubit readout error metadata, classical REM post-processing is disabled even if noise is present.
- Workaround: Manually supply per-qubit readout error rates to the calibration file (hand-filled `calibrations/garnet.json`), or disable REM in analysis (`--no-rem` flag in runners).

**OpenMP conflict: torch + qiskit-aer dual OpenMP runtimes:**
- Symptoms: OMP Error #179 (duplicate library) crash when both `torch` and `qiskit-aer` are imported (each ships its own OpenMP runtime).
- Files: Documented in:
  - `train_hard.py` lines 16–18
  - `demo_hard_accuracy.py` lines 17–20
  - `banknote_study/run_cv_banknote.py` (inferred)
- Current mitigation: Both files set environment variables BEFORE importing:
  ```python
  os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
  os.environ.setdefault("OMP_NUM_THREADS", "1")
  ```
- Impact: Any script mixing `torch` and `qiskit-aer` without these env vars set will crash at import time.
- Lasting fix: None (library conflict is external). Workaround is stable but must be applied in every entry point. Consider documenting in `ENVIRONMENT.md` with a shell alias or wrapper script.

**Emerald (54-qubit) cannot be simulated classically:**
- Symptoms: Noisy simulation requires exponential state-vector storage (2^54 ≈ 1.8 × 10^16 states); AerSimulator memory/time usage becomes prohibitive.
- Files: `hardware_runbook.md` line 117 (explicit): "Emeralda nie symulujemy ($2^{54}$) — cross-topology tylko ze sprzętu."
- Impact: Only Tier A (ODRA, 5q star) and Tier B (Garnet, 20q) can be validated in simulation before committing hardware time/budget on Tier C (Emerald).
- Workaround: Prototype on Garnet, then run Emerald experiments directly on hardware (more risk, but unavoidable).

**Garnet idle-scheduled noisy simulation is slow:**
- Symptoms: Running a full routing sweep (4 patterns × 2 placements × 15+ eval points × 3 folding scales) in noisy sim with idle scheduling takes hours.
- Files: Not explicitly logged; inferred from `noisy_sim.py` schedule_with_idle (lines 238–298) and `zne_dryrun.py` (full-sweep timing not reported).
- Impact: Development cycle on Garnet (20q) is much slower than ODRA (5q) due to circuit depth and idle-gate insertion overhead. Limits rapid iteration.
- Workaround: Use `--quick` mode (subset of points) or run overnight; parallelize across hardware if possible.

---

## Security Considerations

**Hardware runner submission is gated behind a deny-list, not an allow-list:**
- Risk: `.claude/settings.local.json` lines 29–47 use a **deny-list** strategy: specific runners are blocked, but any new runner added to the codebase without an explicit deny entry could be executed by Claude without permission.
- Files: `.claude/settings.local.json` (deny-list for runners starting line 29)
- Current mitigation: Explicit deny entries exist for all known hardware runners:
  - `run_garnet.py`, `run_garnet_smoke.py`, `run_garnet_mirror.py`, `run_garnet_cdr.py`, `run_garnet_qec.py`
  - `run_hardware.py`
  - `run_cdr.py`
  - `banknote_study/run_hardware_banknote.py`, `banknote_study/run_cv_banknote.py`
- Recommendation: Switch to an allow-list strategy for safety. Explicitly allow only safe runners (simulators, plotting, etc.) and deny everything else by default.

**Hardware credit budget is manually tracked:**
- Risk: Budget (~3700 credits, cost ~0.0005 credits/shot) is documented in `hardware_runbook.md` but not programmatically enforced. A misconfigured `--shots` parameter or unintended re-run could exhaust credits.
- Files: `hardware_runbook.md` lines 4–5 (budget); runners lack built-in per-job credit estimation.
- Current mitigation: Staged rollout (§0 of runbook) with go/no-go gates (§3); dry-run modes (`--dry-run` in runners).
- Recommendation: Add a `--estimate-cost` flag to all hardware runners that prints predicted credit spend and requires explicit `--approve-cost` to submit; implement a hard fail if a runner estimates overspend.

---

## Performance Bottlenecks

**Accuracy is high-variance on two_curves under noise:**
- Problem: The easy two_curves task (default) is saturated at ~0.90 noiseless accuracy; noise cannot degrade it further, so ZNE cannot recover a lost signal.
- Files: `demo_hard_accuracy.py` lines 6–8; `methodology_month_2.md` (inferred from architecture)
- Cause: Easy task leaves no margin; decision boundary is far from data.
- Improvement path: Use the harder variant (`offset=0.1`, generated in `demo_hard_accuracy.py`) where noise pushes accuracy down and ZNE can recover it. Alternatively, use a balanced 50/50 split of easy/hard calibration points.

**Classifiers trained per-pattern, not shared:**
- Problem: `train_patterns.py` trains separate VQCs for each entangling pattern (star, linear, circular, all_to_all), doubling training time compared to a single frozen model with pattern-agnostic entanglement.
- Files: `train_patterns.py` (generates one model per pattern); all runners load pattern-specific weights via `weights_for(pattern)`.
- Cause: Methodological choice (each pattern may have different trainability; separate models let us isolate pattern effects).
- Trade-off: Accurate per-pattern analysis at the cost of 4× longer training; justified if pattern significantly affects convergence.

---

## Fragile Areas

**HARDWARE_PLACEMENTS must be hand-filled from live devices:**
- Files: `topology.py` lines 142–171 (HARDWARE_PLACEMENTS dict + hardware_placement function)
- Why fragile: 
  - Emerald and QEC placements are set to `None` (lines 147–150); calling `hardware_placement("emerald", "optimal")` raises `ValueError`.
  - Placements are hand-checked from live backend coupling maps (see `pull_garnet.py` output at line 49–50).
  - If the live device's connectivity changes (qubits go offline, new calibration window), the stored placements become stale.
- Safe modification: 
  1. Run `python pull_garnet.py --device emerald` to derive fresh placements from the live backend.
  2. Copy the printed optimal/adverse lines into `topology.HARDWARE_PLACEMENTS["emerald"]`.
  3. Test against the current live coupling map before submitting any circuit.
- Test coverage: `test_topology.py` validates the structure (present/not None) but not correctness against a live device; gaps exist for cross-device validation.

**ZNE folding barriers must survive transpilation:**
- Files: `zne_dryrun.py` lines 72–88 (fold_global); relies on barrier preservation.
- Why fragile: If transpilation passes `optimization_level=2+`, barriers may be optimized away, collapsing the U†U structure into U (defeating the folding noise amplification).
- Current implementation: Uses `optimization_level=1` (lines 148, native_transpile) or `pre_transpiled=True` (execute_expectation) to preserve barriers after folding.
- Risk: A future refactor (e.g., bumping optimization level for speed) could silently break ZNE's folding strategy.
- Safe modification: Always pair `fold_global()` output with `pre_transpiled=True` in execute_expectation; add an integration test that verifies barriers are present in the final circuit.

**Idle scheduling relies on internal gate duration assumptions:**
- Files: `noisy_sim.py` lines 238–298 (schedule_with_idle); assumes `cal.t_1q` and `cal.t_2q` are the true gate durations.
- Why fragile: If gate durations change (e.g., re-calibration), idle padding code will not auto-update unless `cal` is re-loaded.
- Safe modification: Ensure calibration is always freshly loaded (not cached) before scheduling; add a warning if durations seem stale.

---

## Scaling Limits

**Noisy simulator memory ceiling at ~20 qubits:**
- Current capacity: ODRA (5q) ✓, Garnet (20q) ✓ with slowdown, Emerald (54q) ✗ (exponential memory).
- Limit: State-vector storage scales as 2^N; Garnet (~2^20 ≈ 10^6) is at practical comfort level; Emerald (2^54 ≈ 10^16) is infeasible.
- Scaling path: Adopt a tensor-network simulator (e.g., qiskit-aer with stabilizer mode for subset circuits) or use matrix-product-state (MPS) techniques to trade memory for runtime.

**Hardware credit budget consumed linearly with circuit count:**
- Current capacity: ~3700 credits; cost ~0.0005 credits/shot.
- Limit: Full routing sweep on Garnet (4 patterns × 2 placements × 15 points × 3 scales × 4096 shots) ≈ 1.47M shots ≈ 737 credits (not yet consumed in production). Emerald cross-topology validation at 1.5× cost factor would consume ~900 more, leaving ~1050 credit buffer.
- Scaling path: Parallelize experiments across multiple devices or time windows; use fewer scale factors (e.g., {1, 3} instead of {1, 3, 5}) to halve folding overhead.

---

## Dependencies at Risk

**qiskit-aer + qiskit-iqm version mismatch:**
- Risk: `qiskit-iqm` (IQM Resonance backend) may lag behind `qiskit-aer` releases. Incompatible API shapes (BackendV1 vs V2) can cause runtime errors.
- Impact: Hardware runners (`run_garnet.py`, etc.) depend on `iqm_resonance.py` calling `backend.coupling_map()`, `backend.properties()`, and `backend.target`. If the qiskit-iqm version changes API, code breaks.
- Files: `iqm_resonance.py` lines 44–66 (backend interactions); imports show version adaptation attempts (lines 30–35).
- Migration plan: Pin `qiskit-iqm` to a known-compatible version in `requirements.txt` once created. Test against both BackendV1 and V2 API shapes in CI.

**torch pinning for reproducibility:**
- Risk: `torch.manual_seed()` behavior differs across versions; weight initialization and gradient updates may not reproduce exactly.
- Impact: Model training scripts (`train_hard.py`, `train_patterns.py`, `demo_hard_accuracy.py`) rely on deterministic seeding; a torch version bump could invalidate saved weights.
- Mitigation: `train_hard.py` line 60 and `demo_hard_accuracy.py` line 98 both set seeds; however, without a pinned torch version, determinism is not guaranteed.
- Migration plan: Pin `torch` in `requirements.txt` to the version used during Month 1 training; document this in `ENVIRONMENT.md`.

---

## Missing Critical Features

**No cost estimation/budgeting built into hardware runners:**
- Problem: All hardware runners accept `--shots` and `--mode` but do not predict total credit cost before submission. Users must manually calculate cost from the runbook and argue/justify each step.
- Blocks: Cannot programmatically enforce budget caps or stage rollout without manual approval gates.
- Recommendation: Add a dry-run reporting function that estimates credit spend based on (device, pattern, placement, shots, folding scales) and prints the total; require explicit `--approve-cost <budget>` flag to submit.

**No automated drift detection for hardware calibration:**
- Problem: HARDWARE_PLACEMENTS are static (set once from `pull_garnet.py`); if the live device's coupling map or qubit connectivity drifts between calibration windows, placements may become invalid silently.
- Blocks: Cross-window studies (W4 in runbook) may unknowingly use stale placements.
- Recommendation: Add a pre-submission validation function that queries the live backend and checks if stored placements still satisfy the current coupling map; warn if drift is detected.

**No explicit test coverage for ZNE extrapolation breakdown:**
- Problem: `extrapolate()` in `zne_dryrun.py` uses a clamping heuristic (`_clamped`, lines 96–100) to detect blow-up, but the condition (|estimate| > 1.25) is arbitrary and not validated against known failure regimes.
- Files: `zne_dryrun.py` lines 96–128
- Recommendation: Add a test that intentionally triggers extrapolation failure (high noise, few data points) and verifies that the fallback to linear extrapolation is chosen.

---

## Test Coverage Gaps

**Barrier survival under transpilation not tested:**
- Untested area: The claim that `fold_global()` output preserves barriers through transpilation (pre_transpiled=True path).
- Files: `zne_dryrun.py` (fold_global, execute_expectation with pre_transpiled=True); no direct test.
- Risk: A refactor of transpilation settings could silently break ZNE folding; the error would only manifest as ZNE producing biased estimates (hard to detect).
- Recommendation: Add a unit test in `test_zne_dryrun.py` (not present) that builds a folded circuit, counts barriers before/after, and asserts barriers ≥ expected count.

**Hardware placement validation not tested against live backends:**
- Untested area: `topology.hardware_placement()` raises if a placement is `None`, but does not validate that the placement is valid against the live device's coupling map.
- Files: `topology.py` lines 154–171; used in `run_garnet.py`, `run_hardware.py`, etc. but only tested locally.
- Risk: If `HARDWARE_PLACEMENTS` is accidentally edited and contains qubits outside the device range or disconnected pairs, the error only manifests at submit time (wasted hardware execution).
- Recommendation: Add a pre-submit validation function that queries the backend and checks if all physical qubits in the placement are within range and form a connected subgraph.

**Noisy simulation idle-schedule model not compared to hardware:**
- Untested area: `schedule_with_idle()` and `build_noise_model()` assume specific T1/T2/p_1q/p_ro values; the model is validated against ODRA but not against Garnet/Emerald.
- Files: `noisy_sim.py` (all calibration and noise model building).
- Risk: Garnet/Emerald simulations using the placeholder `synthesize_lattice_calibration()` (lines 137–168) may not reflect real noise; any sim-vs-hardware comparison is suspect.
- Recommendation: Once Garnet/Emerald calibration is available, create `test_noisy_sim_lattice.py` to compare simulated noise profiles against hardware-measured mirror-circuit fidelity.

**Tag-format consistency not tested:**
- Untested area: The tag format used in all runners (e.g., `f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_{pattern}_{cfg['readout']}_L{cfg['n_layers']}"`) is not validated; typos or reordering can cause weights to load from wrong file.
- Files: `run_garnet.py`, `run_cdr.py`, `zne_dryrun.py`, etc. (tag construction not centralized).
- Risk: A runner accidentally loads star weights for an all_to_all model (silent mismatch) if the tag/file naming is inconsistent.
- Recommendation: Extract tag construction to a helper function, test it once, and use it everywhere; add a filename-integrity check (e.g., `tag + "_weights.npy" must exist before loading`).

---

*Concerns audit: 2026-08-25*
