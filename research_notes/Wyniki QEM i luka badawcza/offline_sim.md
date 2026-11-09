# QEM — offline analyses and simulation results: number-exact inventory (2026-11-09)

Scope: `paper_analysis/` (code + `out/`), matched simulations `runs/odra_sim_match/*`, margin simulation
`runs/margin_sim/simm_w01B` vs hardware `runs/odra_campaign/w04m`, other-dataset models
`trained_models_other/`. Sources are local repo paths (relative to `/Users/karinaleskiewicz/QEM/`).
Recomputations marked **[recomp]** were done read-only by this researcher from the CSVs in
`paper_analysis/out/` with **w03dd rows excluded** (w03dd window still running → preliminary).
Scripts: `/private/tmp/claude-501/-Users-karinaleskiewicz-QEM/90c3482e-267d-4a01-ae0d-f55912198ece/scratchpad/a1.py … a5.py`.

Global status / caveats that apply to everything below:
- **All `paper_analysis` analyses are exploratory (post hoc), not pre-registered** — stated in
  [summary.md](paper_analysis/out/summary.md). Only the per-window primary tests in
  [preregistration.md](preregistration.md) (H1, H3, H6, H7a, H7b, Holm family; H4 ZNE and H5 decisions as
  secondary), [preregistration_w02_vncdr.md](preregistration_w02_vncdr.md), [preregistration_w03_dd.md](preregistration_w03_dd.md) are pre-registered.
- **Non-independence:** every hardware rung uses the **same 8 eval points** (eval_index 0,3,…,21; 2 per
  |O_ideal| quartile, `campaign/eval_points.json`) **[recomp]**. 15 untwirled + 4 twirled rung cells over
  4 windows (w01A, w01B, w01P5, w02vn) ⇒ 152 point-cells, but only 8 distinct inputs; cells within a window
  share a calibration. Per-point p-values overstate evidence.
- `frontier.txt`, `decision_rule.txt`, `accuracy.txt`, `frontier_rungs.csv`, `decision_*.csv`,
  `frontier.png` were regenerated at 16:48 **including w03dd rows** (preliminary). The pooled lines printed in
  those .txt files therefore mix in w03dd; the [recomp] numbers below are the clean ones.
- `summary.md` (08:52, committed in 709c516) was written **before night B (w01B) finished** and before
  `decisions_sim` and the other datasets existed — several of its numbers changed (listed per section).

---

## 1. Budget frontier: copies vs n_train, gain vs CZ depth, break-even budget

### Takeaway
POSITIVE (robust): on ODRA, CDR error is limited by the number of training circuits, not by shot copies, and
CDR beats raw at (almost) the smallest budget tested in every rung. NEGATIVE/limiting: the untwirled CDR gain
decays with CZ count (×0.745 per +10 CZ, ρ = −0.78); Pauli twirling preserves a ~3.6–4.6× gain up to 57 CZ.
ZNE {1,3,5} is genuine only at 12 CZ; at ≥30 CZ it is indistinguishable from the "garbage" control.

### Cited Findings
- Method: per (window, rung, arm, point), CDR refit on random subsets (60 draws) of n_train ∈ {5,10,20}
  training circuits and m ∈ {1..6} copies; budget = (n_train+1)·m·S shots/point; seed 20261109 —
  [frontier.py](paper_analysis/frontier.py).
- **Copies vs n_train [recomp, 19 rung-arm cells excl. w03dd, mean of cell ratio CDR error / raw bias]:**
  n_train 5: m=1 → 6: 0.642 → 0.611; n_train 10: 0.490 → 0.437; n_train 20: 0.431 → 0.375. I.e. 6× shots via
  copies buys ~5–13 % relative; 4× training circuits (5→20 at m=6) buys 0.611 → 0.375 —
  [frontier_curves.csv](paper_analysis/out/frontier_curves.csv).
  *Changed vs summary.md* (0.385 → 0.381 at n_train 20; 0.57 → 0.43 → 0.38): copies effect is now visibly
  non-zero but still small.
- Example w01A star (12 CZ), n_train 20: m=1 (172 032 shots) 0.0229 vs m=6 (1 032 192) 0.0216; raw bias
  0.0737; n_train 5, m=6 (294 912 shots) 0.0359 — [frontier_curves.csv](paper_analysis/out/frontier_curves.csv).
- **Per-rung at full budget (n_train 20, 6 copies, 1 032 192 shots/point; w02vn 4 128 768), 8 points each**
  (raw bias / CDR / geometric gain / CDR wins of 8) — [frontier.txt](paper_analysis/out/frontier.txt):
  - untwirled: w01A star 12 CZ 0.0737/0.0216/5.08/6; w01P5 star 12: 0.0672/0.0209/2.63/6; star_idle24 (12 CZ):
    0.0899/0.0139/10.48/7; star_idle36: 0.1121/0.0313/3.97/7; star_idle52: 0.1467/0.0374/4.52/8; w02vn star:
    0.0550/0.0145/3.51/6; star_L6 24: 0.1156/0.0367/3.79/7; star_cz24: 0.0938/0.0220/4.29/7; w01B linear 30:
    0.1098/0.0756/1.56/6; star_L9 36: 0.2266/0.1348/1.54/6; star_cz36: 0.1588/0.0723/1.48/6; w01A circular 39:
    0.1608/0.0529/3.02/7; star_L13 52: 0.2511/0.1847/1.14/7; star_cz52: 0.1765/0.0741/1.63/6; w01B all_to_all 57:
    0.2234/0.1518/1.49/5.
  - twirl_native: star 12: 0.0763/0.0150/4.62/6; linear 30: 0.1242/0.0532/2.05/7; circular 39:
    0.1581/0.0397/4.49/7; all_to_all 57: 0.2272/0.0529/3.62/7.
- **Depth trend [recomp, 15 untwirled rungs excl. w03dd, log-linear fit]:** gain ×0.745 per +10 CZ; raw bias
  ×1.261; CDR error ×1.561 per +10 CZ; Spearman(n_CZ, gain) = −0.78, p = 0.00066. (frontier.txt's printed
  "×0.78 / ×1.27 / ×1.53, 17 rungs" includes the 2 preliminary w03dd off_copies rungs; summary.md said
  ×0.73/1.27/1.57 on 14 rungs.)
- Pooled wins [recomp]: untwirled CDR beats raw in 97/120 point-cells; twirled in 27/32.
- **Break-even budget** (cheapest budget where mean CDR error < raw bias): 49 152 shots/point (= smallest
  tested: n_train 5, m=1, S=8192) in every rung except w01B linear (90 112, both arms) and w02vn (196 608 =
  its smallest budget, S=32 768) — [frontier_rungs.csv](paper_analysis/out/frontier_rungs.csv). *Changed vs
  summary.md* ("beats raw already at the smallest budget in every rung"): w01B linear is the exception.
- **ZNE {1,3,5}, Richardson, budget 24 576** (genuine vs garbage control): 12 CZ 0.0452 vs 0.1373; linear 30 CZ
  0.0643 vs 0.0676; circular 39 CZ 0.1115 vs 0.1028; all_to_all 57 CZ 0.1701 vs 0.1613 —
  [frontier.txt](paper_analysis/out/frontier.txt). Pre-registered H4 ("ZNE pays") not met at any rung
  (ZNE<garbage p = 0.012/0.371/0.844/0.988) — [slide_numbers.txt](runs/odra_campaign/slide_numbers.txt).
- Pre-registered H1 (twirling lowers CDR error) on w01 (32 pairs): 20/32 wins, Wilcoxon p = 0.092, ratio 0.75 →
  not confirmed as a primary test — [slide_numbers.txt](runs/odra_campaign/slide_numbers.txt). (The 3.6–4.6×
  twirled *gain vs raw* above is a different, exploratory comparison.)
- `frontier.png`: left = error vs CZ (raw, CDR 1 M shots, CDR+twirl, ZNE, ZNE garbage), right = CDR error vs
  budget (n_train 20) for star/circular/linear/all_to_all with raw bias dotted —
  [frontier.py](paper_analysis/frontier.py) `plot()`. It currently plots w03dd off_copies star/circular too
  (preliminary).

### Inferences
- Design rule for a paper: at fixed budget spend shots on distinct training circuits, not on copies (shot noise
  is not the bottleneck; training-set variance/model misfit is).
- The CZ-depth decay of the untwirled gain is the "breakdown frontier"; its slope is well-determined only in
  rank (ρ = −0.78) — the rungs mix different trained models (star_L* are deeper *models*, not deeper circuits
  of the same model) and 3 windows/calibrations.
- No rung reached gain < 1 for CDR (lowest 1.14 at 52 CZ untwirled); a hard breakdown point was not observed
  within ≤57 CZ.

### Gaps
- No CIs on the per-+10-CZ slopes (only point estimates and a rank test); cells not independent.
- Twirled arm covers only 4 rungs (w01A, w01B); no twirled P5 depth ladder.
- ZNE measured only in w01A/w01B (one copy).

---

## 2. LOO-CV error bar and the decision rule "CDR or raw"

### Takeaway
POSITIVE (exploratory): leave-one-out error on the Clifford training circuits is an approximately calibrated
error bar for untwirled CDR (72 % / 91 % coverage at 1/2 LOO-rms) and ranks cells by true gain (ρ = 0.73).
NEGATIVE: under-covers for the twirled arm (53 % / 72 %), and the rule "CDR if LOO < training raw error"
does not beat "always CDR" (73.0 % vs 81.6 % correct picks).

### Cited Findings
- Method: predictors from training circuits only (LOO OLS error, training raw error, R², slope a) —
  [decision_rule.py](paper_analysis/decision_rule.py).
- [recomp, excl. w03dd: 152 points, 19 rung-arm cells]:
  - per point Spearman: LOO vs true CDR error ρ = 0.36 (p = 6e-6); train_raw vs true raw error ρ = 0.45
    (p = 5e-9); R² vs CDR error ρ = −0.48 (p = 3e-10).
  - coverage: true CDR error ≤ LOO-rms in 67.8 %, ≤ 2·LOO-rms in 86.8 % (Gaussian 68/95). Untwirled (n=120):
    71.7 % / 90.8 %; twirled (n=32): 53.1 % / 71.9 %.
  - per cell: LOO vs true CDR error ρ = 0.61 (p = 0.005), median true/LOO 0.93 (true/LOO-rms 0.75);
    train_raw vs true raw ρ = 0.34 (p = 0.2), median true/train_raw 1.58; predicted gain (train_raw/LOO) vs
    true gain ρ = 0.73 (p = 4e-4).
  - rule picks CDR in 86.2 %; CDR truly better in 81.6 % (124/152, binomial p = 1.3e-15); rule correct 73.0 %
    vs always-CDR 81.6 %. Mean error: rule 0.0657, always-CDR 0.0582, always-raw 0.1393, oracle 0.0536.
- As printed incl. w03dd (161 pts, 23 cells): coverage 66 % / 87 %, cell ρ = 0.59, median 1.02, gain ρ = 0.78,
  rule 72 % vs 81 % — [decision_rule.txt](paper_analysis/out/decision_rule.txt).
- *Changed vs summary.md*: coverage was 71 %/91 % (now 68/87 pooled — the drop is the twirled arm of night B);
  per-point ρ 0.43 → 0.36; cell ρ 0.66 → 0.61; gain ρ 0.72 (17 cells) → 0.73 (19); rule 71 % vs 82 % →
  73.0 % vs 81.6 %; training raw under-estimates target raw error ×1.5 → ×1.58.

### Inferences
- Paper-ready recommendation: "always apply CDR and report LOO-rms as its error bar (≈1σ for untwirled CDR)";
  for twirled CDR the LOO bar needs inflation (~×1.4 by the coverage numbers) — inference, not tested.
- The rule fails because training circuits (near-Clifford) are systematically easier than the target (raw
  error ×1.58 higher on targets).

### Gaps
- No held-out validation of the calibration factor; 8 distinct points per cell.

---

## 3. Classifier decisions (hardware, 8 points per rung)

### Takeaway
NULL: on hardware, mitigation fixes ⟨O⟩ but not the classifier decision. Raw already matches the ideal
decision in 90.8 % of point-cells, every method agrees 100 % on points with |O_ideal| above the rung median, and
no McNemar comparison is significant (CDR fixes 4 / breaks 7, p = 0.55).

### Cited Findings
- Decision = sign(⟨O⟩); "agree" = matches sign(O_ideal) — [accuracy.py](paper_analysis/accuracy.py).
- [recomp, excl. w03dd]: agreement with ideal — raw 0.908 (n=120), CDR 0.883 (120), CDR+twirl 0.969 (32),
  ZNE 0.938 (32). Above-median |O_ideal|: 1.000 for all (n = 60/60/16/16); below median: raw 0.817, CDR 0.767,
  CDR+twirl 0.938, ZNE 0.875.
- McNemar (agree with ideal) [recomp]: raw→CDR n=120, fixed 4, broken 7, p = 0.549; raw→CDR+twirl n=32, 4/0,
  p = 0.125; raw→ZNE n=32, 3/0, p = 0.25. Versus labels: raw→CDR 3/8 p = 0.227; twirl 3/1 p = 0.625; ZNE 2/1 p = 1.
- Accuracy vs labels [recomp]: raw 0.617, CDR 0.575, CDR+twirl 0.594, ZNE 0.562; ideal model 0.658 on the
  same 120 point-cells (8-point stratified sets: per-rung ideal 0.5–1.0) — [accuracy.txt](paper_analysis/out/accuracy.txt).
- *Changed vs summary.md*: raw agree 92 % → 90.8 %; CDR fix/break 3/7 (p 0.34) → 4/7 (p 0.55); twirl/ZNE
  "fix 2, break 0, n=16, p=0.5" → 4/0 and 3/0 on n=32 (night B added).
- Pre-registered as secondary (H5, decisions McNemar) in [preregistration.md](preregistration.md).

### Inferences
- With only 8 points (2 near the boundary per quartile design) the hardware decision tests have very low power;
  the null is "no evidence of an effect", not evidence of none. The simulation in §4 supplies power.

### Gaps
- w03dd CDR+DD decision rows (n=4) excluded as preliminary.

---

## 4. Classifier decisions in simulation: threshold model, McNemar, generalisation (two_curves, linear, manifold)

### Takeaway
POSITIVE (simulation, exploratory): with 100 points per rung, CDR restores the ideal decision far more often
than it breaks it (132 fixed / 32 broken over 19 rung-models, p = 1.3e-15; 3 cells survive Holm), but
NEGATIVE/NULL for classification accuracy vs labels (raw 0.735, CDR 0.727, ideal 0.731; p = 0.24) — flips
occur only near the boundary, where the ideal model is itself near-random. Noise acts as a threshold shift:
raw ≈ s·ideal + c.

### Cited Findings
- Setup: ODRA device model from `calibrations/odra_raw_w01B_start.json` (no coherent terms: θ=φ=ε=0), raw =
  2×8192 shots, CDR = OLS on 20 near-Clifford circuits ×8192 shots, 100 class-balanced eval points per dataset;
  note CDR decision = raw decision with threshold moved to −b/a — [decisions_sim.py](paper_analysis/decisions_sim.py).
- Per cell (acc ideal/raw/CDR; agree raw/CDR; fixed/broken; p; slope s; offset c; |c|/s; flips predicted by
  threshold model) — [decisions_sim.txt](paper_analysis/out/decisions_sim.txt):
  - linear star 0.86/0.86/0.87; 0.98/0.99; 2/1 p=1.0; s 0.84 c +0.0215; 2/2 predicted.
  - linear circular 0.68/0.73/0.71; 0.83/0.91; 13/5 p=0.096; s 0.39 c +0.0418; 13/17.
  - linear all_to_all 0.62/0.59/0.59; 0.83/0.85; 6/4 p=0.754; s 0.40; 5/17.
  - manifold star 0.91/0.89/0.90; 0.98/0.99; 2/1; s 0.82; 1/2.
  - manifold circular 0.72/0.79/0.74; 0.77/0.92; 19/4 p=0.003; s 0.29 c +0.0452; 23/23.
  - manifold all_to_all 0.84/0.74/0.83; 0.86/0.99; 13/0 p<0.001; s 0.28 c +0.0532; 11/14.
  - two_curves star 0.70/0.71/0.70; 0.95/0.98; 4/1; s 0.81; 5/5. linear 0.69/0.74/0.68; 0.83/0.93; 11/1 p=0.006.
    circular 0.65/0.71/0.65; 0.78/0.94; 18/2 p<0.001; s 0.33. all_to_all 0.75/0.69/0.72; 0.88/0.93; 9/4 p=0.267.
    star_L6 9/0 p=0.004; star_L9 8/1 p=0.039; star_L13 5/0 p=0.062; star_cz24/36/52 2/1, 2/1, 3/2 (p=1);
    star_idle24/36/52 2/0, 2/2, 2/2.
  - All: fixed 132, broken 32 (McNemar p = 1.3e-15); raw flips 189 of 1900; |O_ideal| of flipped points median
    0.061, max 0.354 (all points median 0.306).
- [recomp] Holm over 19 cells: significant only manifold all_to_all (p=0.0002), two_curves circular
  (0.0004), manifold circular (0.0026). Per dataset: linear fixed 21/broken 10 (p = 0.071, NS); manifold 34/5
  (p = 2.4e-6); two_curves 77/17 (p = 2.7e-10). 73 % of flipped points have |O_ideal| < 0.1.
- [recomp] Accuracy vs labels: linear raw 0.727/CDR 0.723/ideal 0.720 (+15/−16, p=1); manifold 0.807/0.823/0.823
  (+22/−17, p=0.52); two_curves 0.721/0.705/0.712 (+37/−57, **p = 0.049, CDR slightly worse**); all 0.7353 /
  0.7268 / 0.7305 (+74/−90, p = 0.24). Agreement with ideal raw 0.9005 → CDR 0.9532; mean |err| raw 0.1613 → CDR 0.0597.
- Threshold model: the offset c is positive in every cell (+0.013 … +0.070) and slope s falls with CZ
  (0.81–0.86 at star → 0.26–0.29 at all_to_all); flips predicted by sign(s·ideal+c) ≠ sign(ideal) match most
  observed flips in deep cells (e.g. 22/22, 23/23) but not all (linear all_to_all 5/17) —
  [decisions_sim.txt](paper_analysis/out/decisions_sim.txt).
- Other-dataset models (qml_benchmarks `linearly_separable` margin 0.02 and `hidden_manifold_model` dim 3; 300
  samples, 8 features, 5 qubits, L3, 60 epochs Adam, seed 42) — [train_other.py](paper_analysis/train_other.py),
  [models.json](trained_models_other/linear/models.json): linear star train 0.939/test 0.833, circular
  0.844/0.700, all_to_all 0.806/0.625; manifold star 0.894/0.908, circular 0.817/0.750, all_to_all 0.856/0.850
  ([train_linear.log](paper_analysis/out/train_linear.log), [train_manifold.log](paper_analysis/out/train_manifold.log)).
- Runs logged a UserWarning that the noise model's listed thermal error on r[0] exceeds the measured infidelity —
  [dec_linear.log](paper_analysis/out/dec_linear.log).
- decisions_sim was produced at 09:17–10:21, i.e. **after** summary.md — not covered there.

### Inferences
- Paper message: "mitigation corrects the value and the near-boundary decisions, not the accuracy" — the decisions
  CDR repairs are ones where the noiseless classifier is itself ~coin-flip vs labels.
- Generalisation: the fix>break pattern holds for the non-linear manifold task and two_curves, only as a
  non-significant trend for the linear task; it concentrates in deep (circular/all_to_all) models, where s is small.

### Gaps
- Simulation only, one calibration (w01B start), no coherent error; §5 shows hardware offset c is smaller than
  the simulated one, so the simulated flip counts likely over-state hardware flips (see §5).
- 100 points reused across all rungs of a dataset (paired, not independent across cells).
- Other-dataset models: one seed each; linear all_to_all test accuracy only 0.625.

---

## 5. Simulation vs hardware agreement

### Takeaway
POSITIVE: the calibration-based ODRA model predicts raw ⟨O⟩, raw error, and ZNE essentially exactly
(Pearson r ≈ 0.98–0.99; error ratio hw/sim ×1.04 raw, ×1.05 ZNE), also on the independent 1300-point w04m
margin window (r = 0.984). NEGATIVE: it under-predicts the residual error left after untwirled CDR by ×1.88
(Wilcoxon p = 6.5e-10), and the excess is tied to CZ gates, not idle time (0.037 vs 0.006, p = 0.0003). After
twirling, sim no longer under-predicts (×0.86).

### Cited Findings
- Matched sims use the same window id ⇒ same circuits, training sets, shots; device model from each window's
  start calibration — [common.py](paper_analysis/common.py).
- Per point (4 windows w01A/w01B/w01P5/w02vn, 304 point-method pairs) — [accuracy.txt](paper_analysis/out/accuracy.txt):
  CDR ⟨O⟩ Pearson 0.982, error Spearman 0.54, same decision 98 %, mean err hw 0.0630 / sim 0.0335 (×1.9);
  CDR+twirl 0.988, 0.29 (p=0.1), 94 %, 0.0402/0.0466 (×0.9); ZNE 0.987, 0.72, 88 %, 0.0978/0.0932 (×1.0);
  raw 0.989, 0.91 (p=2e-47), 98 %, 0.1374/0.1316 (×1.0).
- Per rung-method cell (38): accuracy Pearson 0.82 (p=3e-10); agreement 0.73 (p=2e-7); error 0.92 (p=5e-16).
- [recomp] CDR ratio by window: w01A ×1.58, w01B ×1.96, w01P5 ×1.89, w02vn ×2.21 (pooled 1.88, one-sided
  Wilcoxon hw>sim p = 6.5e-10, n=120); raw ×1.04 (p=0.16); ZNE ×1.05 (p=0.17); CDR+twirl ×0.86 (w01A 1.09,
  w01B 0.78; p=0.77). Sim *over*-predicts twirled all_to_all (sim 0.098 vs hw 0.053). On the same w01A/w01B
  rungs, untwirled CDR hw 0.0755 vs sim 0.0408.
- **CZ vs idle residual (w01P5, CDR, 24 paired points)** [recomp]: hw−sim excess CZ rungs 0.0371 vs idle
  rungs 0.0057, paired Wilcoxon p = 0.00032; by level 24: 0.0086 vs 0.0020, 36: 0.0547 vs 0.0107, 52: 0.0479 vs
  0.0042; base star 0.0174. Same comparison for raw: 0.0239 vs −0.0072, p = 0.0039.
- *Changed vs summary.md*: Pearson values (0.99/0.987/0.99/0.993 → 0.989/0.982/0.988/0.987); pairs 240/3
  windows → 304/4; cell correlations acc 0.92 → 0.82, agree 0.82 → 0.73, err 0.94 → 0.92 (30 → 38 cells);
  CDR+twirl same-decision 98–100 % → 94 %; raw ratio ×1.1 → ×1.04; **twirl ratio ×1.1 (night A only) → ×0.86
  with night B**; CDR ×1.9 and CZ/idle unchanged.
- **Margin window: simm_w01B (sim) vs w04m (ODRA hardware, raw only, 13 rungs × 100 points × 2 copies × 8192
  shots, 2026-11-09 08:19–12:46 UTC, one calibration set d13a40e8…)** — [sim summary](runs/margin_sim/simm_w01B/margin_summary.txt),
  [hw summary](runs/odra_campaign/w04m/margin_summary.txt), [recomp] on the two `margin.csv`:
  - 1300 paired points: raw ⟨O⟩ Pearson 0.984, Spearman 0.986; raw error mean sim 0.1614 / hw 0.1686 (×1.045),
    error Spearman 0.90; same raw decision 92.8 %; raw accuracy sim 0.7215 / hw 0.7200 / ideal 0.7115.
  - flips (raw ≠ ideal decision): sim 107, hw 91, both 52 — the *which-point* agreement is modest.
  - per rung (13 cells): slope s Pearson 0.956, median hw/sim 0.95; error Pearson 0.960; flip-count Spearman 0.59
    (p = 0.035).
  - **offset c differs systematically**: sim +0.013…+0.070 in every rung, hw +0.034 … −0.026 (star +0.0020,
    circular +0.0295, star_cz52 −0.0256, idle rungs ≈ 0) — readout refs differ (sim offset +0.0369, hw +0.0316).
  - hw has more flips than sim on CZ rungs (cz24/36/52: hw 5/8/11 vs sim 2/3/4) and fewer on routed rungs
    (circular 13 vs 22). Raw error excess hw−sim CZ rungs 0.0273 vs idle −0.0101 (Wilcoxon over 300 paired
    points, p = 1.4e-36) — reproduces the CZ-not-idle pattern on raw data in an independent window.
  - Caveat: sim uses w01B *start* calibration, not w04m's.
- w02vn vnCDR (pre-registered primary H_vn, n=8): sim geo 0.524 [0.294, 0.992], 6/8, p = 0.0547 → not supported;
  hw geo 1.212 [0.432, 3.430], 4/8, p = 0.629 → not supported — [sim](runs/odra_sim_match/w02vn/vncdr_summary.txt),
  [hw](runs/odra_campaign/w02vn/vncdr_summary.txt). Sim CDR error 0.0066 vs hw 0.0145.
- Adjacent offline result (NI-CDR, exploratory): MI-CDR worse than CDR in 8/9 hardware cells; 2-axis vnCDR
  primary on P5 geo 1.12 [0.69, 1.73], p = 0.73; simulated CDR error at 1 M shots 3× below hardware (0.007 vs
  0.021) — [nicdr summary](runs/nicdr_offline/summary.md).

### Inferences
- The model captures readout + depolarising/T1/T2 physics (raw, ZNE agree), but misses a CZ-specific error that
  CDR's linear map cannot remove and twirling largely removes → consistent with coherent / non-Pauli CZ error
  (the summary notes the mechanism "goes beyond a simple ZZ error on CZ"; NI-CDR sim with θ_ZZ = 0.05 is the
  related test).
- The sim's positive offset c (decision bias) is not seen on hardware → simulated decision-flip counts (§4) should
  be presented as model-based, with hardware w04m flip rates (91/1300 = 7.0 %) as the empirical anchor.
- Simulation is optimistic for CDR (×1.9–3 too low error) but not for raw/ZNE — matters for any sim-only
  break-even claims.

### Gaps
- No CDR on w04m (raw only), so the ×1.9 CDR under-prediction is not tested on 100-point data.
- Twirled comparison rests on 32 points / 2 windows; w03dd (DD) sim match not available.
- No CI on the ×1.88 ratio beyond the Wilcoxon test; points not independent across rungs.
