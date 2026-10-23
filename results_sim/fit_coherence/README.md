# ABC fit of the coherent CZ error to ODRA's twirl windows (P7)

**Produced by** `sim/fit_coherence.py`, three simulated draws per grid point
(`--sim-reps 3`), through `run_garnet_twirl.py --sim-device` with the archived protocol
(`--legacy-transpile`, logical twirl, shared training, n_train = 10, M = 6, 4 reference
points, 8192 shots), echo T2 inside gates, ALAP schedule, phi = 0. Hardware:
`odra_twirl_o1.csv`, `odra_twirl_o2.csv` (2026-09-13 / 09-15). Fit on star / linear /
circular, all_to_all held out.

| directory | calibration | grid | command |
|---|---|---|---|
| `spec_grid/` (primary) | `calibrations/odra_raw_20260803.json` | theta {0, .01, .02, .03, .05} x eps {0, .005, .01} | `python -m sim.fit_coherence --sim-reps 3 --out-dir results_sim/fit_coherence/spec_grid` |
| `extended_theta/` (diagnostic) | same | theta {.075, .1, .15}, eps 0 | `... --thetas 0.075 0.1 0.15 --eps 0 --out-dir results_sim/fit_coherence/extended_theta` |
| `cal20260730/` (diagnostic) | `calibrations/odra_raw.json` (2026-07-30) | theta {0, .01, .02, .03, .05}, eps 0 | `... --calibration calibrations/odra_raw.json --eps 0 --out-dir results_sim/fit_coherence/cal20260730` |

Each holds `grid.csv` (d2 on the fit points, d2_all on all four, simulated statistics
averaged over draws, ABC weight normalised *within that directory*),
`predictive_check.csv`, and `cache/` (the runner's CSV per draw; delete one to recompute).
Prefix commands with `KMP_DUPLICATE_LIB_OK=TRUE`.

Hardware targets (mean of two windows; between-window SD pooled over points:
s_r2 = 0.106, s_lr = 0.63):

| pattern | CZ | r2_off | log(err_on / err_off) |
|---|---|---|---|
| star | 12 | 0.975 | -0.83 |
| linear | 30 | 0.805 | -0.58 |
| circular | 39 | 0.739 | -0.81 |
| all_to_all | 57 | 0.659 | -1.26 |

## Result: no theta reproduces the routed rungs

| | spec grid | + extended theta | 2026-07-30 calibration |
|---|---|---|---|
| ABC posterior theta | 0.019 +/- 0.017 | 0.020 +/- 0.018 (mass at theta > 0.05: 0.5%) | 0.014 +/- 0.014 |
| ABC posterior eps | 0.006 | 0.006 | (eps = 0 only) |
| best point (d2 on 6 fit statistics) | theta 0, eps 0.01 (5.2) | same; theta >= 0.075 gives 12-16 | theta 0 (5.6) |
| d2 range over grid | 5.2-10.3 | | 5.6-8.7 |
| held out all_to_all, r2_off | pred 0.914 vs hw 0.659, z = +2.4 | pred 0.929 (extended alone), z = +2.6 | pred 0.916, z = +2.4 |
| held out all_to_all, log-ratio | pred -0.22 vs hw -1.26, z = +1.6 | pred -0.63 (extended alone), z = +1.0 | pred -0.34, z = +1.5 |

(The middle column re-weights the 18 points of `spec_grid` and `extended_theta`
together; d2 is comparable between them because both use the same hardware SDs and
three draws.)

1. **The spec grid does not constrain theta.** Weights over the 15 points are
   0.01-0.13, nearly flat, and the posterior sits near the middle of the prior. With 4
   evaluation points per rung and two windows, theta <= 0.05 moves the statistics less
   than their noise.
2. **The routed rungs stay out of reach for any theta up to 0.15.** Simulated r2_off at
   all_to_all is 0.89-0.94 for theta <= 0.1 (it even *rises* slightly with theta up to
   0.05) and 0.85 at theta = 0.15; the hardware has 0.66. Circular stays at 0.84-0.98
   against 0.74.
3. **A larger theta breaks the rungs that already fit.** Before it touches all_to_all,
   theta >= 0.1 pulls linear r2_off to 0.58-0.69 (hw 0.81) and star to 0.90-0.95 (hw
   0.975), and turns the circular log-ratio positive (+1.0 to +1.3: twirling *hurts*,
   against -0.81 on hardware). The extended points therefore fit worse than every spec
   point (d2 12-16 against 5-10), so the budget argument (RZZ(theta) infidelity ~
   theta^2/5, CZ IRB 0.008-0.010, so theta up to ~0.2 is allowed) does not rescue the
   model: the hardware's pattern -- r2 falling *with routing*, twirling gaining most at
   all_to_all -- is not the pattern a uniform ZZ over-rotation on every CZ produces.
4. **The calibration snapshot is not the reason.** The 2026-07-30 calibration gives the
   same picture and an even lower theta. It is internally inconsistent in places
   (thermal relaxation alone exceeds RB on the hub PRX and hub-QB5 CZ; the model flags
   those gates as over budget, see `sim/device_model.py`), so it is a robustness check,
   not a better fit.

**What this supports in the paper:** the twirling gain and the r2 drop observed on ODRA's
routed rungs are *not* explained by a coherent CZ angle error (or PRX over-rotation)
inside the calibrated budget. The draft should not explain the twirling gain as
"coherent ZZ error" on the strength of this model. What it does *not* show: that ODRA's
error is incoherent. Candidates the model leaves out and that would act selectively on
routed circuits: ZZ crosstalk on idle spectators during CZ (routing puts more CZs next
to waiting qubits), leakage, non-Markovian drift between the calibration and the
windows, and correlated errors on SWAP-decomposed CZ triples.

## Caveats

- Two hardware windows: the SDs (0.106, 0.63) are crude, and the held-out z-scores are
  only indicative.
- Four evaluation points per rung; the simulated log-ratio still varies by ~0.3 between
  neighbouring grid points after three draws.
- phi (single-qubit Z phase of the coherent CZ error) fixed at 0; not fitted.
- Calibrations are 6-7 weeks older than the windows.
