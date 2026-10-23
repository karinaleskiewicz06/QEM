# W_neg null distribution (P3)

The shot-noise floor of `W_neg` for a *valid* Richardson extrapolation, at the campaign's
shot count, and how the three matched-cost fold variants sit relative to it. Input for
the W_neg threshold that P9 fixes before the first ODRA window.

**Produced by** `python -m sim.calibrate_wneg_null` (commit of P3), two runs:

| file stem | noise |
|---|---|
| `depol_p2q1e-02_S8192_lam1-3-5` | depolarizing only, p_1q = 1e-3, p_2q = 1e-2 |
| `depol_odra20260803_S8192_lam1-3-5` | depolarizing only, ODRA 2026-08-03 rates: p_1q = 2.0e-3 (mean), p_2q = 2.03e-2 |

The "ODRA rates" are those of the *mapped* calibration, i.e. per-Clifford RB; the CZ's
own IRB error is about 2.5x smaller (`DATA_NOTES.md` §6). That run is therefore a
pessimistic noise level, not ODRA's.

Both: frozen `trained_models_hard` classifier, ladder star / linear / circular / all_to_all
(12 / 30 / 39 / 57 CZ on the fixed-layout path), first 24 reference points, 3 shot-noise
draws, 8192 shots per circuit, scales {1, 3, 5}, variants genuine / identity / garbage
(`qem/folding.py`). `*_points.csv` has one row per (rung, variant, point, draw);
`*_summary.csv` gives W_neg quantiles per rung and pooled (`ALL`).

## What the numbers say

Pooled over the ladder, W_neg quantiles:

| noise | variant | q50 | q95 | q99 | max |
|---|---|---|---|---|---|
| p_2q = 0.01 | genuine | 0.0017 | 0.0100 | 0.0141 | 0.0174 |
| | identity | 0.0065 | 0.0346 | 0.0484 | 0.0577 |
| | garbage | 0.1673 | 0.4565 | 0.5759 | 0.6099 |
| ODRA rates | genuine | 0.0003 | 0.0062 | 0.0083 | 0.0099 |
| | identity | 0.0027 | 0.0364 | 0.0554 | 0.0786 |
| | garbage | 0.0501 | 0.3336 | 0.4539 | 0.4665 |

1. **The genuine null is small**: q99 is about 0.01 at 32 states and 8192 shots, 2-6 times
   below Koster & Mauerer's hardware 0.02-0.06 (16 states, 4096 shots, real device). Pure depolarizing noise is the most favourable case for Richardson, so this
   is a lower bound on what hardware will show.
2. **Identity is not a W_neg null.** It costs the same as genuine but does not scale the
   noise the way Richardson assumes. At p_2q = 0.01 its q95 on the routed rungs is
   0.028-0.048 against genuine's 0.005-0.014 (mean ratio 2.6-8x); at ODRA's rates the
   gap is rung-dependent (about 1x on all_to_all, 23-26x on linear and circular). It is a *cost*
   control. A threshold should come from genuine.
3. **W_neg loses its power once every scale is on the floor.** At p_2q = 0.01 garbage
   separates from both valid folds on every rung. At ODRA's rates it does not on the
   deep rungs: circular (39 CZ) garbage q50 = 0.008, all_to_all (57 CZ) q50 = 0.023,
   overlapping identity, with median SNR at lambda = 5 of 0.7-1.5. When nothing survives
   amplification all three variants give near-flat distributions and nothing goes
   negative. There, SNR(lambda_max), not W_neg, is the operative indicator, and the
   garbage-vs-genuine *error* comparison is the test.

## Limitations

- Depolarizing only: no T1 (so the floor of mean-Z is 0 here; on hardware it is not),
  no readout error, no coherent error. The device-calibrated model is P7.
- Ladder from the fixed-layout path on Qiskit 2.4.1 (12/30/39/57), see `DATA_NOTES.md` §1.
- The draws differ in Aer's seed only; the garbage twin V is the same across draws.
