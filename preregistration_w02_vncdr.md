# Pre-registration: window w02vn — two-axis variable-noise CDR (interleaved)

**Registered:** before any circuit of w02vn is executed. Frozen by the git tag `prereg-vn1`
on the commit that adds this file and `campaign/vncdr_window.py` (whose `analyse()` is the
confirmatory analysis). Any deviation is reported as a deviation.

## Motivation and prior evidence (exploratory, not part of the test)

- P5 night (w01P5): vnCDR at equal budget was not better than CDR in the pre-specified
  variant (k=36, 2 axes: geo ratio 1.12, 2/8). The noise levels were measured in different
  blocks hours apart, which violates vnCDR's assumption that all levels see the same device.
- Simulation with the ODRA device model (`nicdr/sim_budget_scan.py`): on the star rung,
  2-axis vnCDR beats CDR from ~0.5 M shots per point; with a coherent ZZ term the gain is
  ~3x at 1 M shots. The simulated CDR error is ~3x below the hardware's.
- Power (`nicdr/power_vn.py`, 300 replays of shot noise, this window's training sets): at
  4.1 M shots per point and 8 points, power 0.84 without coherent error and 1.00 with a
  coherent ZZ term (theta = 0.05); at 1.0 M shots and 16 points only 0.18 / 0.98. Single
  dress rehearsals with other training-set seeds (`runs/vncdr_sim/simvn*`) did not reach
  significance, so the outcome also depends on the training-set draw. The simulated CDR
  error is ~3x below the hardware's; hardware power is unknown.

## Design

| item | value |
|---|---|
| device | IQM ODRA 5 (star, hub QB3) |
| workload | frozen star L3 classifier (12 CZ), `trained_models_hard` |
| evaluation points | 8: point set 0 of `campaign/eval_points.json` (2 per margin quartile) |
| training set | n_train = 20 near-Clifford circuits per point (`near_target`, native circuit) |
| noise levels | base; + 12 CZ.CZ pairs (36 CZ); + matched idle (12 CZ, same duration as + pairs) |
| copies | M = 6 of every circuit at every level, S = 32768 shots: 4.1 M shots per point per method |
| blocking | one block = one evaluation point; within a block every executor job mixes all three levels copy by copy; block order shuffled with the window seed |
| calibration | set ID read before and after every block; full calibration dump at start and end |

## Hypothesis and test

**H_vn (primary, the only confirmatory test):** at an equal shot budget, 2-axis vnCDR has a
lower error than plain CDR on the star rung.

- CDR: OLS line on the 20 training circuits, all 6 base copies of each circuit.
- 2-axis vnCDR: least squares with intercept of the ideal value on the noisy values at
  (base, + pairs, + idle), 2 copies of each circuit at each level (the same total shots as
  CDR). The error of a point is the mean over 200 random choices of the 2 copies
  (seed 20261104).
- Error: ε = |Ô − O_ideal|, floored at 1e-3 before logs.
- Test: one-sided Wilcoxon signed-rank on log ε (vnCDR − CDR), 8 pairs.
- **Success:** p < 0.05 and geometric-mean ratio < 1. Otherwise: "not supported".

## Secondary (reported, no claims)

1-axis vnCDR (time axis, CZ axis; 3 copies per level), deterministic first-copies draws,
fits without intercept, vnCDR at 3x the budget (all copies of all levels), raw vs CDR.

## Exclusions and edge cases

- A point with any missing circuit is excluded and listed; n is reduced accordingly.
- A block whose calibration set ID changes is kept in the primary analysis; a sensitivity
  analysis drops those points.
- Circuits re-measured after a failed job via `--resume` use the same IDs and are used as
  recorded.
- No point is excluded for its value.

## Freezing

1. Commit this file and `campaign/vncdr_window.py`.
2. `git tag prereg-vn1` (by the author).
3. Then run the window; then `python campaign/vncdr_window.py --analyse runs/odra_campaign/w02vn`.
