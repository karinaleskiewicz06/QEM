# Pre-registration: window w03dd — CDR with and without dynamical decoupling (interleaved)

**Registered:** before any circuit of w03dd is executed. Frozen by the git tag `prereg-dd1`
on the commit that adds this file and `campaign/dd_window.py` (whose `analyse()` is the
confirmatory analysis). Any deviation is reported as a deviation.

## Motivation and prior evidence (exploratory, not part of the test)

- P5 night (w01P5): raw error grows with circuit duration at a fixed CZ count (matched-idle
  rungs), so idle-time noise matters on ODRA. Suppressing idle noise is what DD is for.
- Month 1 (banknote study): IQM's default DD on ODRA made raw error 30-40 % worse; run order
  may explain part of it. So the sign of the effect is open, and the test is two-sided.
- No power analysis: the ODRA device model has no DD, so a simulated effect size would be
  made up. The simulated rehearsal (`runs/dd_sim/`) only checks the pipeline.

## Design

| item | value |
|---|---|
| device | IQM ODRA 5 (star, hub QB3) |
| workloads | frozen star L3 (12 CZ) and circular L3 (39 CZ) classifiers, `trained_models_hard` |
| evaluation points | 8 per rung: point set 0 of `campaign/eval_points.json` |
| training set | n_train = 20 near-Clifford circuits per point (`near_target`, native circuit) |
| arms | DD off; DD on (IQM server-side DD, `STANDARD_DD_STRATEGY`); identical circuits |
| copies | M = 6, S = 8192 shots: 1,032,192 shots per point per arm (as night A) |
| blocking | one block = one (rung, point); each job holds one copy of all 21 circuits for one arm; arms alternate copy by copy (off, DD / DD, off ...); block order shuffled with the window seed |
| calibration | set ID read before and after every block; full dump at start and end |

## Hypothesis and test

**H_dd (primary, the only confirmatory test):** at an equal shot budget, CDR with DD has a
different error from CDR without DD.

- CDR: OLS line ideal ≈ a·noisy + b on the 20 training circuits, all 6 copies, per arm.
- Error: ε = |Ô − O_ideal|, floored at 1e-3 before logs.
- Test: two-sided Wilcoxon signed-rank on log ε (DD − off), 16 pairs (both rungs pooled).
- **Outcome:** p < 0.05 and geometric-mean ratio < 1 → "DD helps CDR"; p < 0.05 and ratio > 1
  → "DD hurts CDR"; otherwise "no difference detected".

## Secondary (reported, no claims)

Per rung: CDR DD vs off; raw DD vs off; mean CDR slope a and fit r² per arm.

## Exclusions and edge cases

- A point with any missing circuit is excluded and listed; n is reduced accordingly.
- A block whose calibration set ID changes is kept; a sensitivity analysis drops it.
- Circuits re-measured after a failed job via `--resume` use the same IDs and are used as
  recorded. No point is excluded for its value.

## Freezing

1. Commit this file and `campaign/dd_window.py`.
2. `git tag prereg-dd1` (by the author).
3. Run the window (`bash campaign/run_dd.sh`); the analysis runs at its end.
