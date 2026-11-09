# Offline prototypes on the w01 data (night A + P5): what can go in the paper without new QPU time

All numbers below are **exploratory**. There are 8 evaluation points per rung, a single window, and arms that are blocks run at different times (review/weryfikacja.md F6). Many variants were tried, so there is a multiplicity problem: no p-value here is confirmatory. "Paired" means paired by evaluation point. CIs are 95% percentile bootstraps over points (10k–20k resamples), and p is a two-sided Wilcoxon test. Error = |⟨O⟩_est − ⟨O⟩_ideal| for mean-Z. Night B is ignored.

Every script is read-only with respect to the repo. Scripts live in `research_notes/QEM combos and data reuse/prototypes/` and outputs in `prototypes/out/`. Rerun any of them with `KMP_DUPLICATE_LIB_OK=TRUE python3 <script>.py`. No QPU or IQM server was contacted. Credentials were not read: the only calibration fields used are `raw.readout.QBk.error_0_to_1/error_1_to_0` and `meta.qubit_order_logical_to_physical`.

Data layout used (verified in `runs/odra_campaign/w01A/counts.jsonl`):
- **CDR, per arm and point:** 6 target executions plus 20 training circuits × 6 repeats/frames. Each execution is 8192 shots, so 1,032,192 shots per point. The spread arm instead has 120 training circuits × 1 execution.
- **ZNE, genuine variant:** λ = 1, 3, 5 × 8192 shots, so 24,576 shots per point.
- **Mean-Z depends only on the Hamming weight.** Shot subsampling is therefore exact multivariate-hypergeometric sampling over 6 categories (`common.py: hw_hist / sub_hist`).

## Q1. CDR at ZNE's budget (24,576 shots/point): who wins at equal cost?

### Takeaway
- **12 CZ (star):** CDR subsampled to ZNE's budget still beats plain ZNE at every point (8/8, error ratio ≈ 0.34–0.40).
- **Caveat at 12 CZ:** once ZNE gets readout correction (Q2), the two tie. ZNE's loss at 12 CZ is mostly a readout offset, not a failure of extrapolation.
- **39 CZ (circular):** CDR at equal budget has lower mean error than ZNE, but the per-point picture is mixed (geometric ratio ≈ 0.9–1.0, 5/8 wins). It does beat readout-corrected ZNE (REM+ZNE) in 6/8 points, ratio 0.63–0.72.
- **CDR's budget is mostly wasted:** its error saturates at about 4–8× ZNE's budget, not 42×.

### Cited Findings
- **Prespecified allocation:** target 8192 shots + 20 training circuits × 819 shots = 24,572. Each figure is the expected error over 600 subsample draws — [q1b_prespecified.txt](prototypes/out/q1b_prespecified.txt).
  - **Star, 12 CZ:**

    | arm | CDR@24k error | ZNE error | diff [CI] | geo ratio [CI] | wins | p |
    |---|---|---|---|---|---|---|
    | off_copies | 0.0237 | 0.0452 | −0.0215 [−0.032, −0.011] | 0.40 [0.24, 0.64] | 8/8 | 0.008 |
    | twirl_native | 0.0167 | 0.0452 | — | 0.34 [0.22, 0.51] | 8/8 | 0.008 |
    | spread | 0.0180 | 0.0452 | — | 0.40 | 7/8 | 0.016 |

    Against REM+ZNE (0.0162), CDR@24k ties or loses: off_copies geo ratio 1.38 [0.72, 2.58] with 2/8 wins; twirl_native 1.17 [0.63, 2.28] with 4/8 wins.
  - **Circular, 39 CZ:**

    | arm | CDR@24k error | ZNE error | geo ratio vs ZNE [CI] | wins | p | vs REM+ZNE (0.1073): geo ratio [CI], wins |
    |---|---|---|---|---|---|---|
    | off_copies | 0.0739 | 0.1115 | 1.04 [0.61, 1.91] | 5/8 | 0.31 | 0.72 [0.57, 0.96], 6/8 |
    | twirl_native | 0.0557 | 0.1115 | 0.90 [0.42, 1.92] | 5/8 | 0.46 | 0.63 [0.40, 0.97], 6/8 (p = 0.078) |
    | spread | 0.1073 | 0.1115 | — | — | — | ≈ tie |
- **Allocation scan** over 8 shapes (T, N, s) — [q1_equal_budget.txt](prototypes/out/q1_equal_budget.txt):
  - **Keep all 20 training circuits; cut shots per circuit.** Cutting N to 4 roughly doubles the error (star off_copies 0.044, circular 0.11).
  - **Shared_random arms collapse under subsampling.** star twirl_native:shared_random goes from 0.031 at full budget to 0.046–0.19 at 24k. Their training ideals take only 3 values (review F7), so the fit is fragile.
  - **The "best allocation" rows are optimistic** because they were picked after the fact.
- **Raw at the same 24,576 shots:** star 0.0737, circular 0.1609. CDR@24k beats raw in 6–7/8 points on both rungs — [q1_equal_budget.txt](prototypes/out/q1_equal_budget.txt).
- **Cost curve,** expected CDR error vs budget as a multiple of 24,576 (the full CDR budget is 42×) — [q1b_prespecified.txt](prototypes/out/q1b_prespecified.txt):

  | rung, arm | 0.25× | 0.5× | 1× | 2× | 4× | 8× | 16× | 42× |
  |---|---|---|---|---|---|---|---|---|
  | star off_copies | 0.028 | 0.025 | 0.024 | 0.023 | 0.022 | 0.022 | — | 0.0216 |
  | star twirl_native | 0.022 | 0.019 | 0.017 | 0.016 | 0.015 | 0.015 | — | 0.015 |
  | circular off_copies | 0.119 | 0.091 | 0.075 | 0.064 | 0.058 | 0.055 | 0.054 | 0.053 |
  | circular twirl_native | 0.112 | 0.076 | 0.056 | 0.045 | 0.042 | 0.040 | 0.040 | 0.040 |
- **ZNE shot standard error** is about 0.011–0.012 per point; CDR's is about 0.003–0.008 at full budget — [q3_hybrids.txt](prototypes/out/q3_hybrids.txt).

### Inferences
- The 42× budget mismatch the review raises (review/recenzja.md) is real, but it does not overturn the ranking.
  - At equal cost CDR keeps most of its advantage.
  - The real equal-cost contest at 12 CZ is CDR vs REM+ZNE, and that is a tie.
  - At 39 CZ, CDR's mean advantage over ZNE is driven by a few points with large ZNE bias (the collapse points, Q7). The geometric mean shows no clear winner.
- **Proposed contribution:** an "equal-budget re-analysis" figure (cost curve) built entirely from stored counts. It also implies a design rule: about 4–8 × 24k shots per point is enough for CDR, which is roughly 5–10× cheaper than the current design.

### Gaps
- **ZNE cannot be scaled up offline:** it has only one realization at 24,576 shots. Its error is a single draw, whereas CDR's is an expectation over subsamples. Both are unbiased for the expected error, but ZNE's per-point value is noisier (SE ≈ 0.011).
- **Subsampling inherits drift:** draws come from the actual block, so they keep its drift and time-of-block effects (F6).

## Q2. Readout correction: is there calibration data, and does REM+ZNE beat raw at 12 CZ?

### Takeaway
- **The data exists.** Per-qubit SSRO error_0_to_1 and error_1_to_0 are stored for calibration set b1b5d2a8, identical at the start and end of night A.
- **On mean-Z, readout error is a fixed offset plus a gain:** offset +0.029, gain ≈ 0.96. Richardson weights sum to 1, so ZNE passes this λ-independent offset through untouched.
- **At 12 CZ, readout correction fixes ZNE:** error 0.0452 → 0.0162, better at all 8 points (geo ratio 0.29 [0.19, 0.42], p = 0.008). Against raw, REM+ZNE wins 6/8 (0.0162 vs 0.0690; geo ratio 0.29 [0.08, 1.09], p = 0.078).
- **At 39 CZ, readout correction does almost nothing** (0.1115 → 0.1073). The error there is signal collapse, not readout.

### Cited Findings
- **Calibration values.** Source fields: `calibrations/odra_raw_w01A_start.json` → `raw.readout`; wire→physical map `['QB3','QB1','QB2','QB4','QB5']` (`meta.qubit_order_logical_to_physical`). The end-of-window dump is identical — [q2_readout.txt](prototypes/out/q2_readout.txt).
  - e01 = [0.0066, 0.0033, 0.0048, 0.0053, 0.0077]
  - e10 = [0.0254, 0.0507, 0.0347, 0.0272, 0.0335]
- **The correction is exact for mean-Z.** Per qubit, Z = (Z_m − (e10 − e01)) / (1 − e01 − e10). Mean-Z depends only on single-qubit marginals, so this equals the full tensored inverse.
- **The wire mapping barely matters.** Qubit-averaged and random-permutation versions differ by ≤ 0.0004, so the latent wire/clbit indexing issue B7 is harmless here — [q2_readout.txt](prototypes/out/q2_readout.txt).
- **Star, 12 CZ** — [q2_readout.txt](prototypes/out/q2_readout.txt):
  - Raw (λ1): 0.0690 → 0.0492 with REM (6/8 better).
  - ZNE: 0.0452 → 0.0162 with REM (8/8 better).
  - REM+ZNE vs REM-raw: 0.0162 vs 0.0492, but only 4/8 wins (geo ratio 0.39 [0.10, 1.25], p = 0.31).
  - Signed ZNE − ideal is +0.039 to +0.077 at all 8 points, mean ≈ +0.045. This is a systematic positive offset; readout explains +0.029 of it.
- **Circular, 39 CZ:** ZNE 0.1115 → 0.1073 with REM (4/8 better, p = 0.38); raw 0.1584 → 0.1485 — [q2_readout.txt](prototypes/out/q2_readout.txt).
- **CDR is invariant to readout correction** (star 0.0216 → 0.0211, circular 0.0529 → 0.0528). The affine CDR map already absorbs a readout offset and gain — [q2_readout.txt](prototypes/out/q2_readout.txt).
- **Leftover star offset after REM is ≈ +0.016.** That is consistent with the T1 pull toward |0…0⟩ documented in review/weryfikacja.md F2.

### Inferences
- **Proposed contribution: "ZNE needs REM, CDR does not."** This is a clean, analytic, data-supported point. Richardson with Σc_k = 1 leaves any noise-scale-independent offset in place (readout, final-idle T1), while CDR's intercept removes it.
- **The "ZNE doesn't beat raw at 12 CZ" result (H4) is mostly a readout artifact.** With REM, ZNE beats raw in most points. The paper should either report H4 with REM or explain why it doesn't.
- **REM is free in shots** (vendor calibration), so it does not change the cost comparison. But it relies on the vendor's SSRO numbers measured at 07:56 UTC; blocks ran until 20:39.

### Gaps
- No in-window readout calibration circuits were run, so the SSRO numbers cannot be validated against the device state during the blocks.
- Correlated readout errors cannot be assessed; mean-Z makes them irrelevant only at first order.

## Q3. CDR × ZNE hybrids, including variable-noise CDR

### Takeaway
- **Night A (only targets folded):** no hybrid beats plain CDR.
  - Applying the CDR map to every folded target and then extrapolating is algebraically identical to a·ZNE + b. It double-corrects and is 2–8× worse than CDR.
  - Averages and inverse-variance mixes fall between CDR and ZNE.
  - Leave-one-point-out stacking ties CDR.
- **P5 makes true variable-noise CDR (vnCDR) possible offline.** The CZ-insertion and idle-insertion rungs carry the same 20 training circuits and the same targets at several noise levels.
  - **Idle-scaled vnCDR (2 levels: base + idle24), at equal cost:** error 0.0209 → 0.0134 (7/8 better, p = 0.039, geo ratio 0.56 [0.32, 0.83]).
  - **CZ-scaled vnCDR:** weaker, 0.0209 → 0.0166–0.0188, not significant.
  - This is the most promising new-method lead, but it is exploratory and multiplicity-exposed.

### Cited Findings
- **Night A, off_copies arm, star / circular** (mean error) — [q3_hybrids.txt](prototypes/out/q3_hybrids.txt):

  | estimator | star | circular |
  |---|---|---|
  | CDR | 0.0216 | 0.0529 |
  | ZNE | 0.0452 | 0.1115 |
  | a·ZNE + b | 0.0660 | 0.1069 |
  | (CDR + ZNE)/2 | 0.0333 | 0.0807 |
  | IVW mix (shot variances; weight on CDR 0.95 / 0.80) | 0.0227 | 0.0681 |
  | LOO stacking (ideal ~ α·CDR + β·ZNE + γ, fit on the other 7 points; oracle-ish) | 0.0167 | 0.0603 |

  - a·ZNE + b vs CDR: star geo ratio 8.1, 2/8 wins, p = 0.039.
  - LOO stacking vs CDR: 4/8 and 3/8 wins, p = 0.64 and 1.0.
  - The twirl_native arm gives the same picture.
- **Why a·ZNE + b fails:** the CDR slope (star 1.22, circular 2.50) and ZNE's implied gain ZNE/E1 (median 1.18 / 1.34) both correct the same attenuation, so composing them over-amplifies — [q3_hybrids.txt](prototypes/out/q3_hybrids.txt).
- **Cross-block check:** applying the CDR-block map to the ZNE-block λ1 measurement of the same circuit gives star 0.0204 and circular 0.0460, matching CDR. The map transfers across blocks hours apart — [q3_hybrids.txt](prototypes/out/q3_hybrids.txt).
- **P5 data check:** training ideals and target ideals are identical across `star`, `star_cz24/36/52` and `star_idle24/36/52` for every (point, train_index). This is asserted in the script; scales λ = n_cz/12 = 1, 2, 3, 4.33 — [q3_hybrids.py](prototypes/q3_hybrids.py).
- **P5 results, all against CDR(λ=1) = 0.0209 and raw = 0.0672** — [q3_hybrids.txt](prototypes/out/q3_hybrids.txt):

  | estimator | idle family | CZ family |
  |---|---|---|
  | vnCDR + intercept, L = 2 | 0.0132 (7/8 better, p = 0.039) | 0.0188 (6/8 better, p = 0.25) |
  | vnCDR + intercept, L = 2, equal cost (each level at half the shots) | 0.0134 (geo ratio 0.56 [0.32, 0.83], 7/8 better, p = 0.039) | 0.0188 (6/8 better) |
  | vnCDR + intercept, L = 4 | 0.0129 (6/8 better, p = 0.25) | 0.0162 (5/8 better, p = 0.46) |
  | vnCDR + intercept, L = 4, equal cost | — | 0.0166 (5/8 better, p = 0.46) |
  | vnCDR + intercept, L = 3 | 0.0214 | 0.0265 |
  | ZNE by insertion on targets alone (linear, all 4 levels) | 0.042 | 0.032 |
  | ZNE by insertion on targets alone (quadratic) | 0.075–0.14 | 0.075–0.14 |

  The non-monotone behaviour in L (worse at L = 3 in both families) is a warning sign of noise-fitting.

### Inferences
- **Proposed contribution (method, exploratory):** "duration-scaled vnCDR" — CDR training repeated at one extra noise level made by matched idle insertion, at equal total shots.
  - **Idle insertion may be the better noise-scaling knob for vnCDR here.** It scales mainly duration and T1/T2 decoherence. P5 found duration is the main error driver (×1.43/µs) and CZ count is not (×0.955 per 10 CZ).
  - **Before a paper claim:** the procedure (levels, intercept) must be pre-registered and confirmed on another window. Calibration changed during P5 blocks (F5), and the cz24/cz52 rungs were affected.
- **Combining a ZNE estimate with CDR inside one window adds nothing at either rung.** CDR's shot variance is 4–20× smaller and its bias is smaller, so any mixture moves toward the worse estimator. A negative result worth one sentence.

### Gaps
- Night A training circuits were never folded, so vnCDR cannot be tested at 39 CZ.
- With 8 points and about 14 variants per family, the 7/8 result for idle-scaled vnCDR L = 2 could be a forking-paths artifact. A Holm correction over the variants would make it non-significant.

## Q4. Twirl × n_CZ interaction; r² of CDR fits

### Takeaway
- **The interaction is in the expected direction but not established.** On log CDR error (OLS, near_target), twirl_native vs off_copies:
  - 12 CZ: ×1.41 [0.60, 3.52]
  - 39 CZ: ×0.68 [0.47, 1.08]
  - Interaction (ratio of ratios) ×0.48 [t-CI 0.15, 1.52; bootstrap 0.18, 1.25], p = 0.20
- **The 12 CZ "sign flip" is fragile.** It disappears once the log floor is raised from 1e-4 to ≥ 1e-3: ×0.99 at 1e-3, ×0.83–0.85 at 3e-3 to 1e-2. On arithmetic or RMS error, twirl is better at both rungs.
- **Twirling raises the CDR fit's r² consistently:** +0.017 at star (7/8 points), +0.116 at circular (8/8).

### Cited Findings
- **Effect sizes, model log err ~ twirl + twirl:circ + C(rung:point), 32 rows** — [q4_q5_twirl.txt](prototypes/out/q4_q5_twirl.txt):

  | outcome | effect at 12 CZ | effect at 39 CZ | interaction | p |
  |---|---|---|---|---|
  | CDR error, OLS fit (above) | ×1.41 | ×0.68 | ×0.48 | 0.20 |
  | CDR error, EIV fit | ×1.48 | ×0.45 | ×0.31 [0.07, 1.30] | 0.10 |
  | raw error | ×0.90 | ×1.01 | ×1.12 | 0.72 |
  | spread arm as the twirl implementation | ×1.00 | ×1.20 | ×1.19 | 0.80 |

  Twirling barely changes the raw error at either rung; the twirl effect acts through the fit, not the target.
- **Floor sensitivity** — [q7b_floor_sensitivity.txt](prototypes/out/q7b_floor_sensitivity.txt):
  - At star, off_copies has two points with error ≤ 6e-4: eval 3 at 0.0006 and eval 18 at 0.0001, which hits the 1e-4 floor. These two drive the ×1.41.
  - Star geo ratio by floor: ×1.41 (1e-4), 0.99 (1e-3), 0.84 (3e-3), 0.83 (5e-3), 0.85 (1e-2).
  - Star arithmetic ratio 0.69, RMS ratio 0.60. Circular is stable: ×0.68–0.80.
- **r² and slope by arm, mean [min, max]** — [q4_q5_twirl.txt](prototypes/out/q4_q5_twirl.txt):

  | rung | arm | r² | slope OLS | slope EIV |
  |---|---|---|---|---|
  | star | off_copies | 0.972 [0.929, 0.992] | 1.22 | — |
  | star | twirl_native | 0.989 [0.982, 0.996] | 1.27 | — |
  | circular | off_copies | 0.789 [0.498, 0.903] | 2.50 | — |
  | circular | twirl_native | 0.905 [0.752, 0.951] | 3.23 | — |
  | circular | spread | 0.677 | 2.39 | 4.77 (de-attenuation cap active; see review B5) |

  Paired r² differences: star twirl − off +0.017 (p = 0.016); circular +0.116 (p = 0.008).

### Inferences
- The paper should not claim that "twirling hurts at low n_CZ." The 12 CZ contrast sits at the noise floor and rests on log-transforming errors of about 1e-4.
- **Proposed robustness rule:** use log(max(err, σ_shot)) or RMS error as the primary metric, and pre-register the floor. The current FLOOR = 1e-4 (review B10) is far below the per-point shot SE of about 0.003.
- **What is defensible from night A:** twirling improves the CDR fit's linearity (r²) at both depths, and the improvement grows with n_CZ.

### Gaps
- Only two n_CZ levels have twirl arms; P5 has no twirled arms. The interaction is a 2-level contrast with 8 points per level, and no slope in n_CZ can be estimated.

## Q5. Frame variance vs copy variance and its share of the error

### Takeaway
- **Copies show no excess variance.** Copy-to-copy variance of untwirled targets equals shot noise (ratio ≈ 0.8–1.0), so there is no detectable drift within a block.
- **Native twirl frames are noisy.** Frame-to-frame variance is 29× shot variance at 12 CZ (SD 0.027) and 12× at 39 CZ (SD 0.018), in both targets and training circuits.
- **With M = 6 frames this noise matters:**
  - At 12 CZ it is about 55% of the twirled CDR's mean squared error.
  - At 39 CZ it is about 25%.
  - The estimated bias with M → ∞ is 0.013 for twirl vs 0.032 for off at 12 CZ, and 0.043 vs 0.067 at 39 CZ.
- **Twirling's bias benefit is masked at 12 CZ** by too few frames.

### Cited Findings
- **Variance ratios and error shares** (target variance across M = 6 repeats vs multinomial shot variance) — [q4_q5_twirl.txt](prototypes/out/q4_q5_twirl.txt), [q5_frame_variance.csv](prototypes/out/q5_frame_variance.csv):

  | rung, arm | target var / shot var | training var / shot var | \|a\|·SE(target mean) | CDR error | share of err² |
  |---|---|---|---|---|---|
  | star off_copies | 0.8 | 0.9 | 0.0022 | 0.0216 | 0.5% |
  | star twirl_native | 28.9 | 31.3 | 0.0138 | 0.0150 | 55% |
  | circular off_copies | 0.8 | 1.0 | 0.0047 | 0.0529 | 0.5% |
  | circular twirl_native | 12.3 | 13.1 | 0.0239 | 0.0397 | 25% |
- **Regression dilution of the slope from frame noise in training x:** 0.994 at star twirl, 0.937 at circular twirl (6% slope attenuation). This is consistent with EIV slope 3.44 vs OLS 3.23 at circular — [q4_q5_twirl.txt](prototypes/out/q4_q5_twirl.txt).
- **Unbiased bias² estimate** err² − a²·var_frames/M — [q7_misc.txt](prototypes/out/q7_misc.txt):

  | rung | arm | RMS error (M = 6) | RMS bias (M → ∞) |
  |---|---|---|---|
  | star | off_copies | 0.0315 | 0.0315 |
  | star | twirl_native | 0.0188 | 0.0126 |
  | circular | off_copies | 0.0674 | 0.0672 |
  | circular | twirl_native | 0.0496 | 0.0429 |

### Inferences
- **Proposed contribution (design rule):** for native twirling on this device, error is dominated by the frame count M, not shots per frame.
  - Frame SD of about 0.02–0.03 means shots per frame beyond about 300–500 do not help.
  - For the same budget, M ≈ 50–100 frames × 500–1000 shots would cut frame noise about 3–4×.
  - That should reveal twirling's bias reduction even at 12 CZ: predicted RMS ≈ 0.013 vs 0.032 untwirled.
- The large frame variance is itself a measurement of coherent-error magnitude: the twirl turns coherent error into spread across frames. It is a candidate per-rung diagnostic (it falls with n_CZ: 29× → 12×).

### Gaps
- M = 6 is the only frame count measured, so the extrapolation to large M assumes frame effects are independent and identically distributed. Testing it needs a run with more frames (new QPU time).

## Q6. Duration- and PRX-aware CDR on night A

### Takeaway
- **Null result.** The training-vs-target duration gap is small: −0.20 µs at star, −0.08 to −0.13 µs at circular.
- **P5's idle rungs give a signal attenuation of only ≈ 8% per µs,** so the implied correction is ≤ 2% of the slope.
- **The correct "attenuation transfer" correction changes errors by ≤ 0.001.**
- **Covariate methods make CDR worse.** Adding duration or PRX count as a regressor up to 2.5× worse at star off_copies. Every training circuit is shorter than the target, so the covariate model has to extrapolate.

### Cited Findings
- **Attenuation from P5 idle rungs:** log(CDR slope) rises 0.084 per µs (SE 0.015), i.e. attenuation ×0.920 per µs. Mean slopes: star 1.190 @ 0.80 µs, idle24 1.283 @ 1.52 µs, idle36 1.383 @ 2.24 µs, idle52 1.458 @ 3.20 µs — [q6_duration.txt](prototypes/out/q6_duration.txt).
- **Star off_copies** (plain CDR 0.0216) — [q6_duration.txt](prototypes/out/q6_duration.txt):

  | variant | error | comparison with plain |
  |---|---|---|
  | +duration covariate | 0.0543 | 1/8 wins, p = 0.016 |
  | x:duration term | 0.0734 | — |
  | +PRX covariate | 0.0543 | identical to +duration, because ASAP duration is linear in PRX count at a fixed CZ skeleton |
  | kernel weighting | 0.0223 | — |
  | attenuation transfer | 0.0210 | 3/8 wins, p = 0.95 |
  | closest-half subset | 0.0247 | — |
- **Other arms and rungs:** attenuation transfer changes errors by −0.001 to +0.0002. The only "significant" case is circular spread, 0.0679 → 0.0669 (7/8, p = 0.023), which is practically negligible — [q6_duration.txt](prototypes/out/q6_duration.txt).
- **Gaps behind the null:** star training circuits have 9.8 fewer PRX than the target (20 PRX); circular has 6.2 fewer — [q6_duration.txt](prototypes/out/q6_duration.txt).

### Inferences
- The review's concern that training circuits have fewer PRX than the target is real but quantitatively negligible here. It can be answered in the paper with these numbers: ≤ 2% slope change, ≤ 0.001 error change.
- Do not use duration as a CDR covariate: the target always sits outside the training duration range.
- If duration matters, the better use is vnCDR along duration (Q3).

### Gaps
- Night A has no scheduled durations (`duration_sched_s` is empty), so ASAP `duration_s` was used. P5's γ uses `duration_sched_s`; the two scales may differ by a constant factor.

## Q7. Other quick wins: ZNE floor, SNR vs floor, drift; plus a ranked shortlist

### Takeaway
- **At 39 CZ the largest ZNE scale has fully collapsed onto the floor.** The point-wise SNR of E(λ=5) against the measured garbage floor has median 0.4–0.8; against zero it is 4.1. The circular ZNE "gain" over raw is therefore the Koster–Mauerer rescaling regime, not genuine extrapolation.
- **Exponential ZNE with a measured floor** helps slightly at star (0.0426 vs 0.0452) and is undefined in 5/8 circular points.
- **No SNR variant predicts the per-point ZNE gain** (Spearman |ρ| ≤ 0.05).
- **Detectable drift between blocks at 39 CZ:** the same circuit measured in the ZNE and CDR blocks differs with χ²/df = 2.4, vs 1.0 at 12 CZ.

### Cited Findings
- **Circular collapse:** E(λ5) − mean garbage floor is −0.002 to +0.006 at all 8 points, while ideals span −0.43 to +0.17. SNR(λ5) median: 4.1 vs zero, 0.8 vs the point's own floor, 0.4 vs the mean floor. Star: 23.4 vs zero, 11.8 vs the point floor — [q7_misc.txt](prototypes/out/q7_misc.txt).
- **ZNE extrapolation variants:**

  | variant | star | star with REM | circular |
  |---|---|---|---|
  | Richardson {1,3,5} | 0.0452 | 0.0162 | 0.1115 |
  | Richardson {1,3} | 0.0463 | 0.0170 | 0.1298 |
  | linear LSQ | 0.0502 | 0.0253 | 0.1510 |
  | exponential with the point's garbage-λ5 floor | 0.0426 | 0.0239 | finite in only 3/8 points |

  Garbage floor mean: star −0.014 (SD 0.022), circular +0.0185 (SD 0.005) — [q7_misc.txt](prototypes/out/q7_misc.txt).
- **SNR vs ZNE gain over 16 points:** Spearman ρ = +0.05 (vs zero), +0.04 (vs point floor), +0.00 (vs mean floor), all p ≥ 0.86 — [q7_misc.txt](prototypes/out/q7_misc.txt).
- **Drift check:** ZNE-block λ1 minus CDR-block target, in SE units — [q7_misc.txt](prototypes/out/q7_misc.txt):
  - star: −1.7 to +1.5 (χ²/df 1.0)
  - circular: −2.9 to +0.7 (χ²/df 2.4)

### Inferences
- **Ranked shortlist of paper contributions that need no QPU time:**
  1. **Equal-budget re-analysis and CDR cost curve (Q1).** It directly answers the review's 42× objection. CDR still wins at equal cost at 12 CZ against unmitigated ZNE, and at 39 CZ against REM+ZNE. CDR saturates at 4–8× ZNE's budget. Strong, cheap, robust.
  2. **"ZNE keeps scale-independent offsets; REM+ZNE vs CDR" (Q2).** An analytic statement (Σc_k = 1) plus data: REM fixes star ZNE at 8/8 points. It changes the H4 reading.
  3. **Frame-count, not shot-count, limits native twirling (Q5),** and the 12 CZ "twirl hurts" claim is a log-floor artifact (Q4). It reframes the H1 result and gives a concrete design rule.
  4. **vnCDR along duration (idle insertion), built from P5 (Q3).** A new-method lead with a promising exploratory signal (7/8, ratio 0.56). It needs pre-registration and one confirmation window.
  5. **Collapse diagnostics at 39 CZ (Q7):** report SNR against the measured floor, not zero; circular λ = 5 is at the floor at all 8 points.
  6. **Negative results worth one line each:** ZNE∘CDR hybrids (Q3 night A) and duration-covariate CDR (Q6).
- **Metric hygiene to adopt everywhere:** pre-register the log-error floor at the shot SE (about 3e-3), and report arithmetic or RMS error next to the geometric ratios.

### Gaps
- None of these can establish cross-window robustness; that needs at least one more window (night B or later).
- The Koster–Mauerer collapse interpretation rests on the repo's own `qem/zne.py` docstring summary of arXiv:2607.09360. The paper itself was not re-read here.
