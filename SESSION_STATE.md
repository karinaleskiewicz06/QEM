# Session Handoff — QEM Month-2 (resume on a fresh context)

**Purpose:** everything a new session needs to continue without re-deriving. Read this +
`hardware_runbook.md` + `plan_month_2.md` first. Working branch: `month2-topology-port`.

## Budget (IQM Resonance — the one number kept only in chat)

- Total: **3700.50 credits**. Spent: **~312** (smoke 0.5 + go/no-go 11.5 + full ladder ~300).
- **Remaining: ~3388 cr.**
- Cost model (calibrated from 2 points): **~0.0002 cr/shot + ~0.33 cr/job** (batching amortises).
- Time-billed: Garnet 0.50 cr/s, Emerald 0.75 cr/s.

## Done

- **Code** (all on disk, mostly uncommitted): topology.py, noisy_sim.py, cdr.py, qec422.py,
  metrics.py, shots_to_target.py, routing_sweep.py + runners (sim: zne_dryrun, run_cdr,
  run_qec422, random_mirror_benchmark, demo_hard_accuracy; hardware: run_garnet, run_garnet_cdr,
  run_garnet_qec, run_garnet_mirror, run_garnet_smoke; adapter: iqm_resonance.py). 73 tests pass.
- **Hard model** trained → `trained_models_hard/` (offset 0.1, 4 patterns, 100-pt frozen ref).
  Runners use it via `--models-dir trained_models_hard`.
- **Sim campaigns** (free): easy (zne/cdr/qec/mirror CSVs) + hard (`zne_hard_results.csv`,
  `cdr_hard_results.csv`). Method-comparison figure: `figures/fig_method_comparison.png`.
- **Garnet hardware**: smoke ✓, go/no-go ✓, **full ladder ✓** (`garnet_full_results.csv`).
- **Docs**: plan_month_2.md, methodology_month_2.md, hardware_runbook.md,
  qec422_design_justification.md, raport_month_2.tex (§1 CDR intro, §2 CV, §3 method comparison).
- **GSD onboarding**: `.planning/codebase/` (7-doc map) + `.planning/PROJECT.md` (staged, not
  committed). config/REQUIREMENTS/ROADMAP skipped — resume with `/gsd-new-project` or `/gsd-onboard`.

## Key results so far (Garnet, hard model, 15 pts)

- Routing thesis CONFIRMED on real hardware: ⟨O⟩-error rises with transpiled CZ; optimal &
  adverse fall on ONE error-vs-CZ curve; adverse all_to_all reaches **96 CZ** (sim max was 54).
- ZNE works and decays with cost: 3.2× at optimal star (12 CZ) → 1.16× at adverse all_to_all (96 CZ).
- Hardware beats the pessimistic sim (Garnet raw < ODRA-sim raw), as in Month 1.
- Accuracy flat/noisy at 15 pts (expected) — the accuracy story rides on the 100-pt point below.

## Remaining commands (run in YOUR terminal; REM is OFF on Garnet — backend has no readout cal)

```bash
# 3 cheap method arms (~150 cr total):
python run_garnet_mirror.py --device garnet --models-dir trained_models_hard        # ~20 cr
python run_garnet_cdr.py --device garnet --models-dir trained_models_hard --n-train 40   # ~90 cr
python run_garnet_qec.py --device garnet                                            # ~39 cr
# Targeted accuracy point — tests "recovery visible only at real high cost" (96 CZ):
python run_garnet.py --mode full --models-dir trained_models_hard --placements adverse --patterns all_to_all --eval-points 100 --out garnet_acc100_results.csv   # ~246 cr
# Then: 2 drift windows (bracketing star+all_to_all, ~150 cr each) for error bands.
# Then: Emerald — pull placements + campaign:
python pull_garnet.py --device emerald    # paste optimal/adverse back to lock in topology.HARDWARE_PLACEMENTS['emerald']
```
Results write to `garnet_*_results.csv` / `emerald_*` — a fresh session can read them directly and analyse.

## Decisions & gotchas

- **Everything on the HARD config** (offset 0.1) for a coherent narrative. Easy accuracy saturated.
- **15 pts hardware** (⟨O⟩-error robust; NOT 30 — no real gain). Accuracy only from the 1×100-pt point.
- **REM OFF on Garnet** — Resonance backend exposes no per-qubit readout error (raw==rem). Honest limitation.
- **Emerald (54q) is unsimulable** (2^54) — cross-topology validation is hardware-only.
- **Commits**: git signs with a passphrase SSH key → non-interactive commits fail. User commits manually.
- **torch+aer**: set `KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1` (train_hard/demo already bake it in).
- `[[4,2,2]]` is dataset-agnostic (random Clifford payloads) — run once, no `--models-dir` needed.

## How to resume

1. New session: read this file + `hardware_runbook.md` + `plan_month_2.md`.
2. Continue the campaign: run the 3 method arms, paste/expose the CSVs, analyse ZNE-vs-CDR-vs-[[4,2,2]].
3. Then the 100-pt accuracy point, drift windows, Emerald.
4. Finish: extend `make_figures.py`, write results into `raport_month_2.tex`, publication plan.
