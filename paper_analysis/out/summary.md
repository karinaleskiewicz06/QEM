# Offline paper analyses — summary (2026-11-09)

Code: `paper_analysis/` (`frontier.py`, `decision_rule.py`, `accuracy.py`, `common.py`).
Data: hardware windows w01A, w01P5, w02vn and the part of w01B measured so far
(night B still running: its rows are preliminary). Matched simulations in
`runs/odra_sim_match/` (same window ids → same circuits, training sets and shots; device
model from each window's start calibration). Full printouts: `out/*.txt`.
All exploratory (not pre-registered).

## 1. Where mitigation pays (frontier.py)

- **CDR on ODRA is limited by the number of training circuits, not by shots.** Repeating
  circuits (copies 1 → 6, 6× the shots) leaves the error unchanged in every rung
  (ratio CDR/raw 0.385 → 0.381 at n_train 20). More training circuits help: n_train
  5 → 10 → 20 gives CDR/raw 0.57 → 0.43 → 0.38. Star 12 CZ: 172 k shots ≈ 1 M shots.
  Design rule: spend the budget on training circuits, not on copies.
- CDR beats raw already at the smallest budget tested (≈ 49 k shots per point) in every
  rung.
- **The CDR gain shrinks with depth** (untwirled, 14 rungs): ~5× at 12 CZ, 1.1–1.6× at
  52 CZ, ×0.73 per +10 CZ. Raw bias grows ×1.27 and CDR error ×1.57 per +10 CZ.
- With twirling the gain holds: 4.6× (12 CZ), 4.5× (39 CZ), 3.6× (57 CZ, night B, preliminary).
- ZNE {1,3,5} (night A): 0.045 at 12 CZ (genuine, beats garbage), 0.112 at 39 CZ (= garbage
  0.103: artefact).

## 2. Can one tell beforehand whether CDR helped? (decision_rule.py)

- **The leave-one-out error on the training circuits is a calibrated error bar for the
  target:** true CDR error ≤ LOO-rms in 71 % of points, ≤ 2 LOO-rms in 91 % (Gaussian: 68 / 95 %).
  Per point ρ = 0.43 (p = 1e-7); per rung-arm cell ρ = 0.66 (p = 0.004), median
  true/LOO 0.90.
- Predicted gain (training raw error / LOO) vs true gain: ρ = 0.72 (p = 0.001) over 17 cells.
- A rule "CDR if LOO < training raw error, else raw" does NOT beat always-CDR (71 % vs 82 %
  correct picks): the training raw error underestimates the target's raw error ~1.5×.
- Recommendation: always CDR, and report the LOO error bar with it.

## 3. Classifier decisions (accuracy.py)

- Mitigation fixes the number, **not the decision**: raw already gives the ideal circuit's
  decision in 92 % of points (noise shrinks ⟨O⟩ toward 0 but rarely flips its sign).
- On points with |O_ideal| above the rung median every method agrees with the ideal 100 %.
  All disagreements are next to the boundary; there CDR breaks 7 and fixes 3 decisions
  (McNemar p = 0.34). CDR+twirl and ZNE fix 2, break 0 (n = 16, p = 0.5).
- Accuracy vs labels is the ideal model's (0.5–0.75 on these stratified 8-point sets); no
  method changes it in a significant way.

## 4. Simulation vs ODRA (accuracy.py + residual check)

- Values: ⟨O⟩ sim vs hw Pearson r = 0.99 (raw), 0.987 (CDR), 0.99 (CDR+twirl), 0.993 (ZNE);
  same decision in 98–100 % (ZNE 88 %). 240 point-method pairs, 3 windows.
- Per rung-method cell (30 cells): accuracy r = 0.92 (p = 9e-13), agreement with ideal
  r = 0.82, error r = 0.94.
- **The calibration model gets raw error right (×1.1) but underestimates the error left
  after CDR ×1.9.** After twirling it is right again (×1.1, night A only).
- The unmodelled residual grows with inserted CZ gates, not with inserted idle time (P5,
  same points and same extra duration): excess hw − sim CDR error 0.037 (+CZ) vs 0.006
  (+idle), paired Wilcoxon p = 0.0003.
  Reading: idle decoherence is captured by the calibration (T1/T2) model; what CDR cannot
  remove on hardware is tied to the CZ gates and is largely removed by twirling. Twirling
  works empirically; the mechanism goes beyond a simple ZZ error on CZ.
- w02vn: in simulation 2-axis vnCDR beats CDR (geo 0.52, 6/8, p = 0.055); on hardware it
  does not (geo 1.21, p = 0.63). The simulator's CDR error (0.007) is 2× below hardware.

## Caveats

- 8 points per rung; many cells share points and windows (not independent).
- Night B rows are preliminary until the window ends; rerun the three scripts then.
- The P5 star_L* rungs are different trained classifiers (deeper models), not just deeper
  circuits of the same model.
