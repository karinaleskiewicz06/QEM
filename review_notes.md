# Methodology review notes (Month 1, ODRA-only)

Living list of open methodological items. Priority: P0 = fix before noise
results mean anything; P1 = needed for a valid dry-run; P2 = do if time.

## Resolved / clarified

- **Dataset "real vs fallback":** `qml-benchmarks` is now installed
  (`pip install "git+https://github.com/XanaduAI/qml-benchmarks.git"`; also
  needs `numpyro`). The notebook **requires** the real
  `qml_benchmarks.data.generate_two_curves` (no silent fallback).
- **Triviality cause was `degree=2`, not the generator.** Classical map
  (n=300, d=8, seed=42, **real** generator):
  - degree 2, offset 0.15: logreg=1.00 / SVM=1.00 → **trivial** (do not use).
  - **degree 8, offset 0.3: logreg=0.87 / SVM=0.93 → chosen study target.**
  - degree 8, offset 0.1: SVM ceiling ~0.87 → too hard for ≥90% pre-flight.
- **Idle decoherence in sim:** added. `noisy_sim.build_noise_model` attaches
  thermal relaxation to `id`; `schedule_with_idle` pads ALAP delays and expands
  them to `id` sequences. On real ODRA idle decoherence is physical — no pad
  needed. Idle model is for **simulated DD** to have something to suppress.
- **Seed:** training uses `SEED=42`.

## P0 — scientific validity

- [x] **Re-locked** on `degree=8, offset=0.3, seed=42`. Swept `DEPTHS=[2,3,4,5]`.
      Locked **L=3** (test 0.911, fewest 2q among ties). `LOCKED.json` written.
- [x] **Ground-truth reference frozen** (`freeze_reference.py`): 30-pt balanced
      seeded eval subset, exact noiseless `ev_ideal`, threshold=0 frozen,
      CX→{r,cz} equivalence verified (Δ<O> ~1e-15). Reuse `eval_indices` +
      `threshold` for EVERY routing level / mitigation method.
- [x] **Selection by explicit tag**: `load_frozen_model` now reads `LOCKED.json`
      (not max test_acc, which grabbed the stale degree=2 model).
- [x] **Primary ZNE metric = mean |⟨O⟩_mitigated − ev_ideal|** implemented as the
      y-axis in `zne_dryrun.py` (accuracy secondary). In-repo ZNE (folding +
      linear/Richardson/exp), no mitiq dep (mitiq/mthree do not install on
      py3.13). Extrapolators clamped to |EV|<=1.25 (blow-up = breakdown signal).

### DD + REM + ZNE full pipeline — DONE (sim, live ODRA calibration)
- [x] **Live ODRA calibration wired in** (`calibrations/odra.json`, `unmapped=[]`):
      T1 15–21 µs, T2* 7–10 µs, T2echo 11–15 µs, 1q~0.002, CZ~0.019,
      readout 0.014–0.026, PRX 20 ns / CZ 60 ns; hub = QB3 → logical 0.
- [x] **REM**: exact per-qubit ⟨Z⟩/(1−2p) for Z observables (`rem_correct_z`).
- [x] **DD**: modelled as idle dephasing T2* → Hahn-echo T2 (both measured;
      a Markovian T2 channel can't be pulse-refocused in sim, so the echo value
      is the physical DD ceiling). DD gain 1.3–1.9× on ODRA.
- [x] **Full run** (4 patterns × 30 pts × reps=3), ablation raw→DD+REM→+ZNE,
      error bands over reps. Must run outside sandbox (Aer OpenMP SHM):
        star (12 CZ)       raw .193 -> DD+REM .163 -> ZNE .029 (exp .023)
        linear (27 CZ)     raw .410 -> DD+REM .380 -> ZNE .246 (exp .135)
        circular (36 CZ)   raw .404 -> DD+REM .381 -> ZNE .304 (exp .232)
        all_to_all (54 CZ) raw .451 -> DD+REM .431 -> ZNE .346 (exp .269)
      Monotonic ⟨O⟩-error vs transpiled CZ; ZNE recovery decays with routing
      (near shot-floor at star, only partial by all_to_all) = target breakdown.
      → `python zne_dryrun.py --calibration calibrations/odra.json --reps N`
- [x] (was) FULL per-pattern run done (sim, placeholder cal)
- [x] Pipeline runs end-to-end: routed -> idle-schedule -> fold[1,3,5] ->
      noisy exec -> extrapolate. Per-pattern classifiers, 30-pt frozen subset,
      4096 shots. Full ladder (⟨O⟩ err; unmit -> ZNE-exp):
        star (12 CZ)       0.158 -> 0.041
        linear (27 CZ)     0.362 -> 0.124
        circular (36 CZ)   0.369 -> 0.215
        all_to_all (54 CZ) 0.404 -> 0.195
      Unmit error rises monotonically with transpiled CZ; ZNE recovery decays
      with routing (star near shot-floor, all_to_all only partial) = the target
      breakdown trend. Extrapolator order exp < Richardson < linear throughout.
      NOTE: idealized sim + placeholder calibration → mechanism + qualitative
      trend only, NOT a hardware breakdown claim (that needs real ODRA cal).
      Must run outside sandbox (Aer OpenMP needs SHM): perms=all.
- [x] **RESOLVED (methodology): retrain per pattern.** `train_patterns.py`
      trains one classifier per entanglement pattern (star/linear/circular/
      all_to_all) at the locked (n=5, L=3) on the *identical* data/split/seed=42.
      `num_weights` is pattern-independent ⇒ matched trainable capacity across the
      ladder (plan §8). Chosen over forced-LAYOUT because it keeps a *real*
      classifier (meaningful accuracy + non-degenerate ideal ⟨O⟩) at every level.
      `zne_dryrun.py` now loads per-pattern weights (`weights_for()`), records a
      `per_pattern_weights` column, and falls back to locked star weights only if
      a pattern's weights are missing.
- [ ] Run full: `python zne_dryrun.py` (30 pts x 4 patterns) — auto-launched by
      the chain watcher once `train_patterns.py` finishes.

### Decisions to lock before the dry-run
- [ ] **Stale model cleanup:** remove/archive `trained_models/two_curves_d8_q5_deg2_*`
      (trivial degree=2 run). LOCKED.json protects selection, but it's a trap.
- [ ] **Shot budget + repetitions — source of the numbers:**
      `N_shots=4096`: SE of a ⟨Z⟩ estimate is √((1−⟨Z⟩²)/N) ≤ 1/(2√N).
      N=4096 ⇒ worst-case SE ≈ 0.0078 (mean-Z over 5 qubits is tighter). This
      must be ≪ the ZNE effect size (~0.05–0.15 seen in sim), so shot noise does
      not masquerade as (un)mitigated signal. Also within IQM norms (~1k–20k).
      `R=5` repetitions: SEM = σ/√R → usable error band from the CLT; bump R if
      bands overlap. These are **statistical** choices, not device numbers.
- [ ] **ZNE scale factors + extrapolators:** e.g. folding [1,3,5] × {linear,
      Richardson, exponential}; record residuals to detect breakdown.
- [ ] **ODRA calibration numbers** (see collect_odra_calibration.py).

## P1 — noise-model correctness

- [x] Idle/delay decoherence in sim (see above).
- [ ] **Pull live ODRA calibration** → `python collect_odra_calibration.py`
      (set `IQM_SERVER_URL`, or fill the template by hand from the dashboard).
      Replace placeholders; re-run `noisy_sim.sanity_check`.
- [ ] **Simulated ZNE is idealized** (depolarizing+relaxation extrapolates too
      cleanly). For Month 1 go/no-go: run a **short real-ODRA ladder** (star +
      all_to_all, few points) so breakdown is observed on hardware noise, not
      only the toy sim. Pipeline still validated in sim first.

## P2 — analysis power / do if time

- [ ] **Depth confound:** transpiled depth co-varies with 2q count (e.g. 31→112
      as CZ 12→54). Decoherence tracks *time/depth*, not only CZ count. Mirror
      circuits (plan §7.6) give a task-agnostic fidelity yardstick to disentangle
      "2q error" from "idle decoherence". Denser ladder (also vary L) helps.
      Detail: a mirror circuit is U†U (or a compiled equivalent) so the ideal
      output is known (|0…0⟩). Fidelity vs 2q-count is independent of the VQC
      decision boundary and shows when the device leaves the extrapolatable
      regime. Do if time in Month 1; required for a clean paper figure later.
- [ ] **Statistics / error bands:** several shot-noise realizations × a few seeds
      so every curve has uncertainty bands (plan promise). **Do if time.**
- [ ] **Process hygiene:** one training run at a time (nbconvert races on the
      same `.ipynb`); select frozen model by **explicit tag**, not max test_acc.

## How to collect ODRA calibration (quick)

```bash
# API path (preferred) — token auth (ODRA / Resonance API token)
pip install iqm-client                       # DONE (v35); numpy bumped to 2.5.1, sim OK
export IQM_SERVER_URL="https://odra5.e-science.pl/"
export IQM_TOKEN="<your API token>"          # or set IQM_TOKENS_FILE from `cortex login`
python collect_odra_calibration.py --num-qubits 5
#   -> calibrations/odra.json      (mapped DeviceCalibration schema)
#   -> calibrations/odra_raw.json  (raw dump for audit)
# CHECK odra.json meta.unmapped_fields_kept_as_placeholder == []; if not,
# inspect odra_raw.json and tighten map_to_device_calibration().

# Hand path (dashboard)
python collect_odra_calibration.py   # no URL → writes TEMPLATE
# then paste T1,T2 (µs→s), 1q/2q error, readout error from ODRA UI
```
NOTE: qiskit-iqm NOT installed (its pinned qiskit-terra fails to build on
py3.13); the iqm-client path is the primary one and is enough.

Load: `cal = load_iqm_calibration("calibrations/odra.json")`.

## How to run on ODRA hardware (`run_hardware.py`)

Mirrors `zne_dryrun.py` but executes on the device via `iqm-client.submit_circuits`
(no qiskit-iqm needed). Only EXECUTION changes — same locked per-pattern classifier,
frozen 30-pt eval subset, exact noiseless ⟨O⟩ reference, folding, REM, extrapolation —
so hardware numbers are directly comparable to the simulator ablation.

Conversion: Qiskit native `{r, cz, barrier}` → IQM `{prx(angle,phase rad), cz, measure}`;
logical→physical map `PHYS=[QB3,QB1,QB2,QB4,QB5]` (hub QB3 = logical 0). Barriers kept
so folded U†U isn't compiled away. **DD is native on hardware** (`DDMode.ENABLED` +
`STANDARD_DD_STRATEGY`), NOT the sim's T2*→T2echo swap model; `--dd-ablation` runs each
batch DD-off and DD-on. REM uses `cal.p_ro`. Readout is mean-Z ⇒ ⟨O⟩ is robust to any
histogram bit-order ambiguity (confirm per-qubit order on the smoke test anyway).

```bash
export IQM_SERVER_URL="https://odra5.e-science.pl/"
export IQM_TOKEN="<API token>"
# 1) safe: build+validate every circuit locally, submit nothing
python run_hardware.py --dry-run --go-no-go --dd-ablation
# 2) smoke: ONE circuit end-to-end (prints raw counts to verify bit order)
python run_hardware.py --submit --smoke
# 3) go/no-go: star + all_to_all, 8 pts, scales [1,3,5]  (Month-1 test)
python run_hardware.py --submit --go-no-go --dd-ablation
# 4) full (only after go/no-go): 4 patterns × 30 pts → raise the guard
python run_hardware.py --submit --full --dd-ablation --max-circuits 720
```
`--max-circuits` (default 400) refuses oversized batches so allocation can't be
burned by accident. Output: `hardware_results.csv` (per pattern×DD: transpiled_cz,
unmit/ZNE errors ± std, accuracy, job_ids).

## Banknote ansatz study (second routing ladder)

The KN-Axion banknote classifier gives a *second, independent* cost ladder at
**fixed noiseless accuracy** — the confound-controlled comparison we wanted. All 3
ansatze reach ~0.88 noiseless (5-fold, `banknote_study/noiseless_and_cost.py`), but
transpiled CZ on the star differs 3× (depth 4: star 16 / odra 35 / simulator 52).

**Bug fixed (readout wire).** `native_transpile` uses a coupling map, so the
transpiler *permutes* qubits (SabreLayout). The banknote **star** ansatz reads a
single Z on its hub (logical qubit 2), which routing maps onto physical wire 0 — but
the noisy path was reading physical wire 2, i.e. the *wrong* qubit. Fixed in
`run_zne_banknote.py` / `run_hardware_banknote.py` by placing the readout observable
on `native.layout.final_index_layout()[mq]`. odra/simulator (logical 0 → physical 0)
were unaffected; two_curves uses **mean-Z** (permutation-invariant) so its hardware
results are unaffected. Always derive the readout wire from the transpiled layout for
single-qubit observables.

**Sim results** (`banknote_zne_d{2,4,6}.csv`, ODRA-calibrated, 50 pts): the ⟨O⟩-error
grows monotonically with CZ and ZNE recovery decays with CZ, exactly like two_curves.
The **accuracy gap** appears at the top of the ladder — depth-6 simulator (87 CZ):
raw acc 0.60 → +DD+REM 0.68 → +ZNE 0.80 (≈ ideal 0.78). At low CZ the sign decision
is robust so accuracy barely moves; the continuous ⟨O⟩-error is the sensitive signal.

Scripts (all reuse the two_curves pipeline; DRY-RUN-validated, ready for free QPU):
```bash
python banknote_study/noiseless_and_cost.py                 # noiseless acc + CZ ladder
python banknote_study/run_zne_banknote.py --depth 4         # sim ablation (raw/DD+REM/ZNE)
python banknote_study/mirror_fidelity.py                    # task-agnostic fidelity (sim)
python banknote_study/mirror_fidelity.py --submit --dry-run # validate HW mirror circuits
python banknote_study/run_hardware_banknote.py --dry-run --depth 4          # validate HW acc
python banknote_study/run_hardware_banknote.py --submit --depth 4 --dd-ablation  # real QPU
python make_figures.py   # figures/: two_curves QPU-vs-sim, banknote ladder, mirror fidelity
```

## QPU vs simulator (two_curves)

`figures/fig_two_curves_qpu_vs_sim.png` overlays `zne_dryrun_results.csv` (sim) and
`hardware_results.csv` (real ODRA). Same monotone error-vs-CZ trend on both; the ODRA
calibration is a *slightly pessimistic* proxy (real raw error < sim raw error) and QPU
ZNE recovers a bit more at high CZ. At the low-CZ star point both reach the shot-noise
floor. Conclusion: the sim is a faithful, conservative stand-in for methodology dev.

## two_curves status (Month 1) — COMPLETE

Hardware experiment is finished; nothing more is *required* on the QPU for two_curves:
- trained + locked (`LOCKED.json`, L=3 star mean-Z), noiseless reference frozen;
- sim ablation over 4 patterns (`zne_dryrun_results.csv`);
- full hardware ladder 4 patterns x DD{off,on}, raw/REM/ZNE, reps=3 error bands
  (`hardware_results.csv`, 8/8 rows);
- QPU-vs-sim figure.
Remaining two_curves items are optional/offline or multi-session: output-variance-vs-CZ
collapse plot (offline), mirror fidelity on QPU (optional submission), >=3 calibration
windows for drift (future sessions), annotated bibliography (writing).

## DD is a NEGATIVE result on ODRA — report it as such

On hardware, IQM's `STANDARD_DD_STRATEGY` (`DDMode.ENABLED`) **lowers** every metric we
measured. This is consistent across three independent experiments, so it is a finding,
not a fluke:

| experiment | DD off | DD on |
|---|---|---|
| banknote mirror fidelity, star d2 | 0.619 | 0.425 |
| banknote mirror fidelity, odra d6 | 0.102 | 0.043 |
| banknote accuracy, star d6 | 0.733 | 0.517 |
| two_curves ⟨O⟩ error, star (12 CZ) | 0.1115 | 0.1591 |

Mechanism: DD only pays off when *idle dephasing* dominates. On Spark the budget is
dominated by 2q gate error and crosstalk, and the inserted pulses add coherent error of
their own, so DD is net-negative. **No extra ODRA time is needed to document this** — the
mirror-fidelity CSV already contains a DD on/off pair at every depth for all three
ansätze, the banknote d6 accuracy CSV has one, and `hardware_results.csv` has one for all
four two_curves patterns.

Important asymmetry to state explicitly in the report: **in our simulator DD always
helps** (two_curves mirror: star 0.333 → 0.362), because we model DD as an idle-dephasing
improvement T2\* → T2-echo, which by construction can only improve things. The simulator
therefore *cannot* reproduce the hardware's DD penalty. Consequence for the write-up: the
pipeline is **REM+ZNE**, with DD demoted from a pipeline stage to a measured negative
result — and an example of a mitigation whose sim model is structurally optimistic.

## two_curves mirror fidelity

`mirror_fidelity_two_curves.py` — the two_curves analogue of the banknote script. Mirror
CZ is exactly 2x the forward ladder (star 24, linear 54, circular 72, all_to_all 108).
Simulator reference (5 inputs, 8192 shots):

| pattern | mirror CZ | F (DD off) | F (DD on) |
|---|---|---|---|
| star | 24 | 0.3328 | 0.3623 |
| linear | 54 | 0.0859 | 0.1050 |
| circular | 72 | 0.0493 | 0.0580 |
| all_to_all | 108 | 0.0565 | 0.0582 |

Note circular/all_to_all have both reached the 5-qubit depolarized floor (2^-5 = 0.031),
so the ladder only *resolves* star > linear; beyond that the mirror has no signal left.
QPU cost is trivial (20 circuits), so this is worth submitting.

## Ansatz naming

Use the paper's names in the report — **baseline** (our `simulator`, CRX/CRY ring),
**native** (our `odra`, native-CZ ring), **topology** (our `star`, hub-and-spoke). Code
and CSVs keep the repo names; only the write-up is renamed.

## Month 2 (planned)

- **Error detection + post-selection** (small codes, e.g. `[[4,2,2]]`) as a *near-term*
  "logical-ish" protection layer for 1-2 qubits: detect (not correct) errors, discard
  flagged shots. Chosen over full QEC because 5 logical x ~13 physical = 65 > 54 (Emerald),
  device 2q error (~1-2%) sits near the surface-code threshold, VQC needs non-Clifford
  rotations (magic-state overhead), and no fast feed-forward on the IQM NISQ tiers.
- Extend the physical routing ladder to Garnet (20q) / Emerald (54q) square lattices.
