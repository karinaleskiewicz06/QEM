# Handoff — P7 in progress (2026-10-16)

Read together with `spec/PROMPT_claude_code_QEM_paper.md` (rules and tasks) and
`DATA_NOTES.md`. Branch `paper-odra-campaign`. Commits on it: P0, P1, P2, P3
(`f06fe0c`). **P7 is written and tested but not committed** — the user commits
(passphrase-signed key); show her the command, never commit yourself. No QPU, ever.

Order agreed with the user: P3 → P7 → P8 → P9; P4/P5/P6 after the first ODRA window.

## 1. Running when the session ended

A detached queue (`nohup`) writes into the repository, so it survives the session:

| step | output | status at handoff |
|---|---|---|
| CDR benchmark, reference points | `results_sim/bench_cdr/*_reference.csv` | done |
| CDR benchmark, uniform points | `results_sim/bench_cdr/*_uniform.csv` | done |
| ABC, spec grid, 3 draws | `results_sim/fit_coherence/spec_grid/` | running, ETA ~12:25 |
| ABC, theta 0.075/0.1/0.15, eps 0 | `results_sim/fit_coherence/extended_theta/` | queued, ETA ~12:31 |
| ABC, calibration 2026-07-30, eps 0 | `results_sim/fit_coherence/cal20260730/` | queued, ETA ~12:41 |

Finished when each directory has `grid.csv` and `predictive_check.csv`. Progress: count files
in `*/cache/`. Draws are cached, so a killed run resumes by re-running the same command:

    python -m sim.fit_coherence --sim-reps 3 --out-dir results_sim/fit_coherence/spec_grid
    python -m sim.fit_coherence --sim-reps 3 --thetas 0.075 0.1 0.15 --eps 0 --out-dir results_sim/fit_coherence/extended_theta
    python -m sim.fit_coherence --sim-reps 3 --calibration calibrations/odra_raw.json --eps 0 --out-dir results_sim/fit_coherence/cal20260730

(prefix `KMP_DUPLICATE_LIB_OK=TRUE`). The extended grid goes beyond the spec's grid; it is a
diagnostic for problem 1 below, the spec grid stays the primary fit.

## 2. To finish P7

1. Read the three ABC results. Write `results_sim/fit_coherence/README.md` (the old one was
   deleted with the stale cache; it described a single-draw run on the previous model). Key
   question: does any theta reproduce the hardware's routed rungs (r2_off 0.66 at all_to_all,
   0.74 at circular; log(err_on/err_off) -1.26 at all_to_all)? The earlier single-draw run on
   the old model said no for theta <= 0.05. Note RZZ(theta) infidelity ~ theta^2/5, CZ IRB
   error 0.008-0.010, so the budget allows theta up to ~0.2.
2. Run the full suite: `python -m pytest -q` (fast ~25 s, slow ~10 min). Last fast run:
   all pass after fixing `tests/test_zne_p3.py` (now passes `--out`).
3. Update the P7 commit message (below) with the ABC result, show the user the command.

## 3. What P7 contains (uncommitted)

- `sim/device_model.py`: ODRA from one calibration (raw dump preferred). Per-gate PRX RB /
  CZ IRB fidelities; depolarizing chosen so total fidelity = calibration for every theta
  (coherent inside the budget); echo T2 inside gates; idle relaxation from an ALAP/ASAP
  schedule with T2* (or echo with DD); asymmetric readout; coherent CZ error
  RZZ(theta)(RZ(phi) x RZ(phi)); relative PRX over-rotation by rewriting angles. Gates over
  budget are flagged with their cause.
- `--sim-device` (+ `--sim-theta/phi/eps/schedule/gate-t2`) in all five runners incl.
  `run_hardware.py` (user ran its smoke: `results_sim/hardware_sim_smoke.csv`, works, DD
  lowers error). Model + budget recorded in `manifest["extra"]` (new optional field).
- ODRA paths of all five runners now compile through `qem.compile.compile_native` on
  hardware and simulator; `--legacy-transpile` restores the archived path.
- `qem.provenance.guard_archive`: runners refuse to write a tracked file outside
  `runs/`/`results_sim/` (every default `--out` was an archived CSV);
  `--allow-archive-write` overrides.
- `sim/bench_cdr_variants.py` (on the classifier's reference points by default),
  `sim/fit_coherence.py` (kernel ABC, sim noise in the distance, archived protocol via
  `--legacy-transpile`), `sim/schedule_sensitivity.py`.
- Results + READMEs: `results_sim/bench_cdr/`, `results_sim/device_model/`,
  `results_sim/wneg_null/README.md` (note added), `DATA_NOTES.md` (§1 compile path, §6
  per-Clifford calibration, archive defaults).
- Tests: `tests/test_device_model_p7.py`, `tests/test_device_model_p7_sim.py`.

## 4. Decisions taken with the user in this session

- Device model physics: per-gate IRB/RB; coherent error inside the fidelity budget;
  relative PRX over-rotation; idle relaxation from a schedule.
- P7 regression test: one-sided paired Wilcoxon over 64 (rep, target) pairs, p < 0.05, plus
  lower mean — instead of the spec's ">= 6/8 repetitions" (sits on the noise).
- "Resolve all problems": the user's list of nine problems from the P7 review is binding,
  together with the spec. All addressed except (1), which the ABC runs answer.

## 5. Results so far worth knowing

- Benchmark (theta 0.05, 57 CZ, reference points): spread+near_target 0.109 vs
  twirl_native+shared_random 0.194; 7/8 reps, 44/64 targets, Wilcoxon p = 5e-5. But
  twirling does **not** help inside spread on reference points (spread 0.109 vs spread_off
  0.106, p = 0.74); it did on uniform points. Phrase H6 as "spread < twirl_native", not "because
  of twirling".
- Calibration mapping overstated CZ error ~2.5x (Clifford RB vs IRB).
- ALAP vs ASAP: ~shot noise except circular (0.021); idle relaxation itself is large.
- 2026-07-30 calibration is internally inconsistent (thermal alone exceeds RB on hub PRX and
  hub-QB5 CZ).

## 6. Open, waiting on the user

- Flaky P1 test `test_legacy_path_loses_the_skeleton_regression[linear]` (unseeded router;
  fails ~1/3 runs on committed code). Proposed: average several draws, separate P1 fix.
- `spec/odra_cal_example.json` (needed by P8's definition of done) is missing; proposed copy
  of `calibrations/odra_raw_20260803.json`.
- Offered: draft v0.2 of `spec/draft_artykul_QEM_ODRA.md` (fix ladder 12/27/36/54 vs
  12/30/39/57, mark tainted numbers from DATA_NOTES, add spread, soften "precondition" and the
  coherent-mechanism claim).
- Commands the environment blocks for the assistant: executing `run_hardware.py` (even
  `--sim-device`). Ask the user to run it.

## 7. P7 commit (update the last paragraph with the ABC outcome)

    git add sim/device_model.py sim/bench_cdr_variants.py sim/fit_coherence.py sim/schedule_sensitivity.py tests/test_device_model_p7.py tests/test_device_model_p7_sim.py tests/test_zne_p3.py results_sim/bench_cdr results_sim/fit_coherence results_sim/device_model results_sim/wneg_null/README.md qem/provenance.py run_garnet_twirl.py run_odra_cdr.py zne_shot_boundary.py random_mirror_benchmark.py run_hardware.py DATA_NOTES.md

Message draft (ends with the attribution line):

    P7: device-calibrated simulator, one ODRA compile path, archive guard, CDR benchmark, ABC fit

    sim/device_model.py builds ODRA from one calibration: per-gate fidelities (PRX RB, CZ IRB)
    met exactly for any coherent angle, echo T2 inside gates, idle relaxation from a schedule
    (T2*, or echo with DD), asymmetric readout, coherent CZ error and relative PRX
    over-rotation. The mapped calibration's p_2q is two-qubit Clifford RB, ~2.5x the CZ's own
    error (DATA_NOTES).

    All five runners take --sim-device and compile ODRA through compile_native on hardware and
    simulator (--legacy-transpile for the archive), and refuse to overwrite archived CSVs
    (every default --out was one).

    sim/bench_cdr_variants.py on the classifier's points: spread+near_target beats
    twirl_native+shared_random (44/64 targets, paired Wilcoxon p=5e-5), but twirling adds
    nothing inside spread. sim/fit_coherence.py: <ABC OUTCOME>.

    Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

`HANDOFF_P7.md` itself is not meant to be committed; delete it once P7 is in.
