# Pre-registration: analysis plan for the ODRA window w01 (and later windows)

**Registered:** 2026-10-24, before any analysis output of window w01 was produced or
inspected. Frozen by the git tag `prereg-v1` on the commit that adds this file and
`analysis/prereg_w01.py`.

**Honest status.** This is a *pre-analysis plan*, not a pre-data registration. Night A of
w01 started at 09:56 local time on 2026-10-24, before this file existed; its raw counts
were being collected while the plan was written, but no error, ratio, fit or test of w01
had been computed or looked at. The pilot windows (`runs/odra_pilot/p1_*`, `p2_*`, `p3_*`,
2026-10-23/24) **were** analysed and inform the hypotheses below; they are exploratory
and are not part of any confirmatory test here.

The confirmatory analysis is `analysis/prereg_w01.py`, committed with this file. Any
deviation from it is reported as a deviation.

---

## 1. Data

| window | content | rungs (CZ) |
|---|---|---|
| `w01A` | night A, point set 0 | star 12, circular 39 |
| `w01B` | night B, point set 0 | linear 30, all_to_all 57 |
| `w01P5` | P5 night, point set 0 | star 12; star + 6/12/20 CZ·CZ pairs (24/36/52); star + matched idle; star L6/L9/L13 (24/36/52) |

Produced by `campaign/odra_window.py` (git commit in each manifest), analysis tables
`cdr.csv` / `zne.csv` rebuilt from `counts.jsonl` by `--analyse`.

Design (fixed in code before this plan): 8 evaluation points per window (two per
quartile of the ideal margin |O_ideal| of the star L3 model, `campaign/eval_points.json`,
point set 0 = indices 0, 3, 6, …, 21); n_train = 20 (spread: 120), M = 6 frames or copies,
S = 8192 shots; equal budget (n_train + 1)·M·S per point and arm; block-randomised order;
calibration set ID read before and after every block.

CDR arms in nights A and B: `off_copies:near_target`, `twirl_native:near_target`,
`spread:near_target`, `twirl_logical:shared_random`, `twirl_native:shared_random`.
ZNE: scales {1, 3, 5}, Richardson, folding variants genuine / identity / garbage.
P5 night: `off_copies:near_target` only, no ZNE.

**Primary metric:** the absolute error of the mitigated value at one evaluation point,
ε = |⟨O⟩_mitigated − O_ideal|, with ⟨O⟩ = mean Z over the five qubits. CDR uses the
ordinary least-squares fit (`fit == "ols"`); the errors-in-variables fit is secondary. An
error of exactly 0 is floored at 1e-4 before taking logs.

## 2. Hypotheses, tests, criteria

All paired tests pair two arms on the same (rung, evaluation point). Nights A + B give
4 rungs × 8 points = **32 pairs**.

| id | hypothesis | comparison | test | success criterion |
|---|---|---|---|---|
| **H1** | Pauli twirling lowers the CDR error at an equal budget | `twirl_native:near_target` vs `off_copies:near_target` | one-sided Wilcoxon signed-rank on log ε, 32 pairs | Holm-adjusted p < 0.05 **and** geometric-mean ratio < 1 |
| **H3** | native twirling is at least as good as logical twirling | `twirl_native:shared_random` vs `twirl_logical:shared_random` | one-sided Wilcoxon, native < logical, 32 pairs | Holm-adjusted p < 0.05; otherwise report the ratio and its 95% bootstrap CI (no claim of difference) |
| **H6** | spreading the budget over distinct training circuits beats twirled CDR | `spread:near_target` vs `twirl_native:near_target` | one-sided Wilcoxon, 32 pairs | Holm-adjusted p < 0.05 **and** geometric-mean ratio < 1 |
| **H7a** | at fixed duration, more CZ raises the raw error | P5 night, `star_cz*` vs `star_idle*` and `star` | OLS of log ε_raw on n_CZ/10 and duration/µs with point fixed effects, SE clustered by point, L3 rungs only (`analysis/depth_regression.py`, sample `l3_only`) | coefficient of n_CZ/10 > 0, Holm-adjusted two-sided p < 0.05 |
| **H7b** | at fixed gate counts, longer duration raises the raw error | same model | coefficient of duration > 0 | Holm-adjusted two-sided p < 0.05 |

**Family-wise error:** Holm correction across the five primary tests {H1, H3, H6, H7a,
H7b} at α = 0.05.

### Secondary (reported, not part of the family)

- **H4, the ZNE window, per rung.** Genuine ZNE "pays" at a rung if all of: (i) its mean
  error is below the raw error (one-sided Wilcoxon over the 8 points, p < 0.05,
  uncorrected); (ii) it is below the garbage-folding error at the same rung; (iii) the
  median W_neg of the genuine variant is ≤ 0.02; (iv) the median SNR at λ = 5 is ≥ 2.
  The W_neg threshold 0.02 is set from the P3 depolarizing null at 8192 shots
  (`results_sim/wneg_null/`: genuine q99 = 0.014 at p_2q = 0.01, 0.008 at ODRA's rates).
  The prediction from the pilot, stated now: ZNE pays at 12 CZ and not at 57 CZ.
- **H5, decisions.** McNemar (exact binomial on discordant pairs) of sign agreement with
  the ideal decision, raw vs `twirl_native:near_target`, pooled over the 32 pairs. With
  32 points the test is weak; the claim tested is the margin structure: decision changes
  occur in points below the median |O_ideal|.
- Every primary comparison per rung, and with the EIV fit.
- H1 and H6 with `train_set = shared_random` where both arms exist.

### Not tested here

- **Stability across calibration windows (spec H2):** one window cannot test it.
- **κ and Neyman allocation (H4 lower edge):** not measured in w01; the pilot κ values
  are exploratory.

## 3. Exclusions and edge cases

- A block whose calibration set ID differs before and after it, or from the first
  block of its night, is flagged. Primary analysis keeps it; a sensitivity analysis drops
  the rungs containing it.
- Circuits re-measured by `--resume` after a failed job use the same seeds and are used
  as recorded; aborted partial records are kept aside, not analysed.
- No evaluation point is excluded for its value. A rung missing any arm of a comparison
  drops out of that comparison only, and the reduced n is reported.
- If night B or the P5 night does not complete, the hypotheses are tested on what was
  measured, and the missing rungs are reported as missing.

## 4. Freezing

1. Commit this file and `analysis/prereg_w01.py`.
2. `git tag prereg-v1` on that commit (done by the author, not by the assistant).
3. Only then run `python -m analysis.prereg_w01` on the w01 windows.
