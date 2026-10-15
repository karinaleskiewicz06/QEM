# Nested device-calibrated noise controls (prior session)

Simulator-only controls produced before this campaign branch existed, moved here from the
repository root so that new results live under `results_sim/` as the campaign layout requires.

**Produced by** `nested_null_odra.sh`, which drives `run_garnet_twirl.py --sim --device odra
--calibration calibrations/odra_20260803.json`. Log: `runs/legacy_logs/nested_null.log`.

**What they are.** Three noise models that differ by exactly one term, so that "excess r² decay
over the device null" is a meaningful quantity:

| prefix | model |
|---|---|
| `nested_cal00_*` | ODRA's measured calibration only (T1/T2, p_1q, p_2q = 0.0203, readout) |
| `nested_cal02_*` | the same, plus a coherent ZZ over-rotation θ = 0.02 on every CZ |
| `nested_cal05_*` | the same, with θ = 0.05 |

Three windows each (`w1`–`w3`) plus a `_banded` aggregate. Protocol matched to the ODRA
hardware twirl campaign: 4 evaluation points, 8192 shots, n_train = 10, M = 6.

**Known limitations**, which is why these are `legacy_` and not a campaign result:

- The transpiler seed is fixed across windows, so window-to-window spread is Aer shot noise
  alone. Simulation does not reproduce device drift, and these files must not be used to
  estimate between-window variance.
- The coherent term is composed into each per-pair CZ error inside `build_noise_model`.
  Registering it afterwards as an all-qubit error does **not** work: Aer silently drops an
  all-qubit error for a gate that already has qubit-specific errors, which produced an
  earlier run where every θ gave identical results.
- The training set is the shared one (the P1 defect), and the circuits were compiled through
  the pre-P1 path.
- Only ODRA. `calibrations/garnet.json` carries topology only — no T1/T2, gate or readout
  errors — so no Garnet null exists and Garnet hardware must not be compared against this one.

Analysis that consumed these files: `analyze_excess_r2.py` → `r2_excess_over_null.csv`.
