# CDR arms at an equal budget, device-calibrated model (P7)

**Produced by**

    python -m sim.bench_cdr_variants --patterns all_to_all --reps 8 --points reference
    python -m sim.bench_cdr_variants --patterns all_to_all --reps 8 --points uniform

File names carry the model tag (`DeviceModel.tag`): calibration
`odra_raw_20260803`, coherent CZ error theta = 0.05, phi = 0.03, no PRX over-rotation,
echo T2 inside gates, ALAP idle relaxation with Ramsey T2*, no DD. Every gate's total
fidelity equals its calibrated PRX RB / CZ IRB value; no gate is over budget.

Protocol: all_to_all rung (57 CZ on the fixed-layout path), 8 repetitions x 8 targets,
n_train = 10, M = 6, S = 8192; every arm spends `(n_train + 1) * M * S` shots per
target. One row per (rep, target, arm, training set, fit).

Targets:

- `reference` -- the classifier's frozen evaluation set (`X_eval`); repetition `r` uses
  points `8r .. 8r+7`, so no target repeats. **This is the primary result**: these are the
  circuits the campaign runs.
- `uniform` -- features uniform in [-pi, pi], as `spec/sim_cdr_variants_bench2.py` did.
  Kept to show what that choice changes.

## Result (OLS, mean |error| over 64 targets)

| targets | training set | off_copies | twirl_native | spread_off | spread |
|---|---|---|---|---|---|
| reference | near_target | 0.149 | 0.124 | **0.106** | 0.109 |
| reference | shared_random | 0.214 | 0.194 | 0.156 | 0.165 |
| uniform | near_target | 0.107 | 0.083 | 0.086 | **0.063** |
| uniform | shared_random | 0.132 | 0.115 | 0.097 | 0.089 |

Raw error: 0.236 on reference targets (mean |O_ideal| 0.357), 0.131 on uniform ones
(0.199). The hardware windows gave 0.165 (o1) and 0.150 (o2) at this rung, on the
first four reference points, so on the classifier's own points the model is if
anything pessimistic.

**The spec's comparison** -- spread + near_target against twirl_native + shared_random:

| targets | repetitions | targets better | Wilcoxon (one-sided) | sign test |
|---|---|---|---|---|
| reference | 7/8 | 44/64 | p = 5.4e-5 | p = 0.0018 |
| uniform | 6/8 | 43/64 | p = 5.2e-4 | p = 0.0041 |

It holds on both target sets. The slow regression test asserts the paired per-target
test (agreed 2026-10-15 in place of ">= 6/8 repetitions", which sits on the noise: the
reference arm has a heavy tail of degenerate fits).

**What the target set changes.** On uniform targets twirling helps inside the spread arm
(spread vs spread_off, near_target: 43/64, two-sided Wilcoxon p = 0.002). On the
classifier's targets it does not (30/64, p = 0.74; shared_random 28/64, p = 0.33): there
the gain of spread comes from the *number of distinct training circuits*, not from
twirling. Twirling still helps the non-spread arms (off_copies -> twirl_native) on both
sets. A claim that spread works *because* it combines both levers is therefore not
supported in this model; H6 should be phrased as "spread < twirl_native at equal
budget", which it is.

**Not comparable with the spec's 0.0190 / 0.0357.** That benchmark used a weaker model
(ODRA 23.07 constants, CZ depolarizing fixed at 0.003, no PRX depolarizing, no idle),
uniform targets and logical-level training circuits.
