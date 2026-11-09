# Earlier and supporting QEM results, the paper draft, and the reviews

Scope: everything outside the current ODRA w01/w02vn/w03dd/w04m campaign that could go into the paper, plus the draft's state and the reviewers' criticisms. Read-only analysis of `/Users/karinaleskiewicz/QEM` (branch `paper-odra-campaign`, HEAD `d53f3f4`, 41 commits). Sources are repo paths, relative to the repo root. No QPU, no credentials.

**Data generations** (from `reports/QEM combos and data reuse.md` and `DATA_NOTES.md`):
- **Generations 1–3** keep CSV means only: Month 1 ODRA (Jul 30 – Aug 1 2026), Garnet and Emerald (Month 2), and the ODRA twirl windows o1/o2 (Sep 13–15).
- **Generation 4** keeps full counts: the ODRA pilots of Oct 23–24 and w01.

---

## Q1. What results exist in results_sim/, results*/ CSVs, runs/ (other than odra_campaign) and reports, and with what numbers?

### Takeaway
There is a large archive of earlier hardware and simulator results:
- **Month 1 ODRA:** ZNE, REM, DD, and the routing ladder at 12/27/36/54 CZ.
- **Month 2 Garnet:** the full ladder, CDR, mirror, `[[4,2,2]]`, three twirl windows and κ.
- **Emerald:** one window.
- **banknote:** 5-fold CV on ODRA.
- **Simulator campaigns.**

Most of the archived ODRA CDR and ZNE numbers carry documented defects:
- CDR training circuits did not share their target's CZ skeleton.
- One training set was shared by every evaluation point.
- ZNE values above |E| > 1.25 were silently clamped.
- DD was never interleaved.

So they are usable only ordinally or descriptively. The cleanest reusable earlier datasets are the twirl campaigns (o1/o2, Garnet w1–w3), whose CZ skeletons match.

### Cited Findings

**Month 1, ODRA (star, 5q).** 30 points, 3 reps, 4096 shots, per-pattern weights.

| CZ | raw | DD-on raw | REM | ZNE Richardson |
|---|---|---|---|---|
| 12 | 0.1115 | 0.1591 | 0.0884 | 0.0243 |
| 27 | 0.2811 | 0.3754 | — | 0.1150 |
| 36 | 0.2990 | 0.3821 | — | 0.1760 |
| 54 | 0.3565 | 0.4583 | — | 0.2390 |

- ZNE reduction factor: 4.59× at 12 CZ, 2.44× at 27, 1.70× at 36 and 1.49× at 54 — [hardware_results.csv](hardware_results.csv); [final_raport.tex §sec:miesiac1](final_raport.tex)
- Accuracy was flat at 0.87–0.92 across all methods and rungs — [hardware_results.csv](hardware_results.csv)
- **The DD penalty is confounded.** DD-off always ran before DD-on, the circular pair was split across Jul 30 and Aug 1, and the campaign spans 3 days — [DATA_NOTES.md §5–6](DATA_NOTES.md)
- **The simulator predicts a slight DD gain** with ideal pulses — [results_sim/hardware_sim_smoke.csv](results_sim/hardware_sim_smoke.csv), cited in [reports/QEM combos and data reuse.md](reports/QEM%20combos%20and%20data%20reuse.md)

**Month 1, sim↔hardware validation.**
- The ODRA-calibrated simulator `zne_dryrun_results.csv` (DD+REM, 5 reps, 30 points) gives raw 0.193 / 0.408 / 0.405 / 0.454 and ZNE-Richardson 0.024 / 0.243 / 0.305 / 0.345 at 12/27/36/54 CZ — [zne_dryrun_results.csv](zne_dryrun_results.csv)
- The simulator is more pessimistic than the hardware (raw 0.1115 at 12 CZ) — [hardware_results.csv](hardware_results.csv)
- SESSION_STATE notes "Hardware beats the pessimistic sim … as in Month 1" — [SESSION_STATE.md](SESSION_STATE.md)
- Mapped calibration `p_2q` is two-qubit Clifford RB, about 2.5× the CZ's own IRB error: 0.0203 against 0.0078–0.0105 — [DATA_NOTES.md §6](DATA_NOTES.md)

**ODRA routing ladder (transpile-only).**
- ODRA: star 12, linear 27, circular 36, all_to_all 54 CZ (SWAPs 0/5/7/8) — [routing_ladder_odra.csv](routing_ladder_odra.csv)
- Garnet: linear/star 12, circular 24, all_to_all 57 CZ (9 SWAPs) — [routing_ladder_garnet.csv](routing_ladder_garnet.csv)
- Emerald: all_to_all 72 CZ (14 SWAPs) — [routing_ladder_emerald.csv](routing_ladder_emerald.csv)
- The ladders in different files disagree because there are two compile paths. The twirl runner gives 12/30/39/57 on ODRA — [DATA_NOTES.md §1](DATA_NOTES.md)

**ODRA 100-point CDR (Month 2, archived; tainted).** Rungs are 12/27/36/54 CZ.

| file | CDR r² | CDR error (raw error) |
|---|---|---|
| [odra_full_100pt.csv](odra_full_100pt.csv) | 0.958 / 0.809 / 0.792 / 0.598 | 0.0267 / 0.0712 / 0.105 / 0.220 (raw 0.0745 / 0.150 / 0.186 / 0.278) |
| [odra_cdr_100pt.csv](odra_cdr_100pt.csv) | 0.966 / 0.835 / 0.827 / 0.617 | — |

- ZNE in `odra_full_100pt`: 0.0226 / 0.0895 / 0.142 / 0.219.
- **Taint:** for routed patterns only 0–2 of 10 training circuits had the target's skeleton, and one training set was shared — [DATA_NOTES.md §3–4](DATA_NOTES.md)
- The skeleton-matched pilot `p2_cdr100` gives r² 0.93 / 0.82 / 0.69 / 0.60 at 12/30/39/57 CZ. So most of the CDR breakdown survives fixing the routing — [reports/QEM combos and data reuse.md](reports/QEM%20combos%20and%20data%20reuse.md)

**ODRA twirl windows o1/o2** (skeletons match; 4 points per rung). From [odra_twirl_banded.csv](odra_twirl_banded.csv):

| CZ | r² off → on | Δr² | CDR error off → on |
|---|---|---|---|
| 12 | 0.975 → 0.986 | +0.011 | 0.050 → 0.022 |
| 30 | 0.805 → 0.949 | +0.144 | 0.068 → 0.041 |
| 39 | 0.739 → 0.932 | +0.193 | 0.131 → 0.061 |

- At 57 CZ, window o1 alone has Δr² +0.191 — [twirl_pairs_all.csv](twirl_pairs_all.csv)
- **o2 has only 32 jobs against 92 for o1.** Whether it was narrowed on purpose or stopped early is unresolved — [DATA_NOTES.md §5](DATA_NOTES.md)

**κ (ZNE variance constant).**
- ODRA archival uniform {1,3,5,7}: κ = 48.1 ± 6.0 at 12 CZ (prediction 44.6) — [odra_kappa_k7.csv](odra_kappa_k7.csv)
- Garnet {1,3,5}: 14.42 ± 0.95 (12 CZ) and 13.29 ± 1.73 (48 CZ); weighted mean 14.16 ± 0.83 against the predicted 14.656, i.e. 0.60σ — [zne_shot_boundary_results.csv](zne_shot_boundary_results.csv); [final_raport.tex](final_raport.tex)
- Garnet {1,3}: 3.39 ± 0.40 against the predicted 4.00 — [final_raport.tex](final_raport.tex)
- Joint fit: slope 0.937 ± 0.049, χ²/dof 0.79 — [final_raport.tex](final_raport.tex)
- **These ZNE values went through the silent clamp**, which changes the estimator variance that κ measures — [DATA_NOTES.md §6](DATA_NOTES.md)

**ZNE signal retention (sim/hardware, archived).** Retention R is 0.41 (optimal star, 33 CZ), 0.19 (adverse all_to_all, 87) and 0.15 (optimal all_to_all, 90, "collapse") — [zne_signal_retention.csv](zne_signal_retention.csv)
- **The R > 0.3 decision rule is withdrawn.** It becomes a ratio of floors when the signal is already on the floor — [DATA_NOTES.md §6](DATA_NOTES.md)

**Mirror fidelity, a task-agnostic yardstick.**
- ODRA two_curves survival: 0.549 / 0.211 / 0.118 / 0.094 at mirror CZ 24/54/72/108. DD lowers it at every rung (e.g. 0.389 at 24 CZ) — [two_curves_mirror_fidelity.csv](two_curves_mirror_fidelity.csv)
- Garnet survival: optimal 0.776 / 0.527 / 0.215 / 0.277 (24/42/66/111 CZ); adverse 0.552 / 0.592 / 0.251 / 0.273 (48/54/87/150 CZ) — [garnet_mirror_results.csv](garnet_mirror_results.csv)
- Mirror fidelity correlates with depth (Spearman +0.79, p = 0.021). Its correlation with CZ count (+0.48) and with ZNE gain (−0.36, p = 0.39) is not significant — [final_raport.tex](final_raport.tex)

**`[[4,2,2]]` detection (negative result).**
- Simulator, 1–4 layers (34/63/104/157 CZ): bare error 0.597 / 0.874 / 0.978 / 0.987; detected 0.419 / 0.788 / 0.937 / 0.987; acceptance 0.62 → 0.50 — [qec422_results.csv](qec422_results.csv)
- Garnet optimal (40/50/84/131 CZ): bare 0.418 / 0.707 / 0.773 / 0.863; detected 0.223 / 0.563 / 0.617 / 0.786; acceptance 0.75 → 0.56 — [garnet_qec422_results.csv](garnet_qec422_results.csv)
- Garnet adverse (64–164 CZ): bare 0.671 → 0.983; detected 0.541 → 0.969 — [garnet_qec422_results.csv](garnet_qec422_results.csv)
- The final report's verdict: detection "does not repay the post-selection cost" — [final_raport.tex abstract](final_raport.tex)

**Detection combined with ZNE (sim scopes).**
- Detection + ZNE on the QEC payload at 1 layer (34 CZ): 0.0324, against raw 0.498, ZNE 0.248 and detection 0.320. The benefit vanishes at deeper layers (0.43 at 63 CZ, 0.66 at 104) — [scope_qec_zne_results.csv](scope_qec_zne_results.csv)
- On the VQC, check-qubit detection worsens error at every pattern (e.g. star 0.137 against raw 0.055) — [scope_detzne_vqc_results.csv](scope_detzne_vqc_results.csv)

**Accuracy and margins.**
- Garnet 100-point adverse all_to_all (96 CZ): raw 0.221 → ZNE 0.169 (−24%), but accuracy 0.78 → 0.77 — [garnet_acc100_results.csv](garnet_acc100_results.csv)
- Margin stratification: ZNE recovers only +0.017 to +0.033 accuracy in the near/mid/far bins — [margin_stratify_results.csv](margin_stratify_results.csv)
- REM over 61 banknote configurations lowers the error by 0.0017 (0.9%) and changes no classifier decision — [final_raport.tex §sec:rem-wynik](final_raport.tex)

**banknote_study (second dataset, ODRA hardware 5-fold CV; not git-tracked as far as `git ls-files` shows).**
- The "star" ansatz at depth 2/4/6 (8/16/24 CZ):
  - raw 0.072 / 0.126 / 0.161
  - ZNE-Richardson 0.043 / 0.036 / 0.093
  - noiseless accuracy about 0.86–0.89
- The "odra" ansatz at depth 2/4/6 (13/36/58 CZ):
  - raw 0.112 / 0.259 / 0.226
  - ZNE-Richardson 0.058 / 0.217 / 0.177
  - [banknote_study/banknote_hardware_cv_full_summary.csv](banknote_study/banknote_hardware_cv_full_summary.csv)
- One CDR point (star, depth 4, 16 CZ): 0.1075 → 0.0755, r² 0.943 — [banknote_study/banknote_cdr_results.csv](banknote_study/banknote_cdr_results.csv)
- DD hurts here as well: star at 24 CZ goes 0.141 → 0.183 and accuracy 0.73 → 0.52 — [banknote_study/banknote_hardware_results.csv](banknote_study/banknote_hardware_results.csv)
- Classed as "a whole second hardware dataset, on the bench" — [project_review_gaps.md §6](project_review_gaps.md)

**trained_models_other (untracked).**
- Two extra datasets, `linear` and `manifold` (300 samples, 8 features, 5q, L3, 100 eval points). For `linear`, test accuracy is star 0.83, circular 0.70, all_to_all 0.625 — [trained_models_other/linear/models.json](trained_models_other/linear/models.json)
- They feed the simulated decision analyses `paper_analysis/out/decisions_sim_{linear,manifold}.csv`, both untracked — [paper_analysis/out/decisions_sim_linear.csv](paper_analysis/out/decisions_sim_linear.csv)

**CDR error-bar rule (paper_analysis, uncommitted output).** Over 161 cells:
- leave-one-out error vs true CDR error: ρ = 0.34 per point and 0.59 per cell; median ratio true/loo 1.02.
- Rule "CDR if loo < train_raw": mean error 0.0668, against always-CDR 0.0593 and the oracle 0.0547.
- [paper_analysis/out/decision_rule.txt](paper_analysis/out/decision_rule.txt)

**Simulator controls.**
- **Null and coherent sims use a placeholder calibration.** `night_null_*` and `night_coh05/10_*` used `p_2q = 0.01`, and the positive control had coherent error only — [DATA_NOTES.md §6](DATA_NOTES.md)
- Example: coh05 at 33 CZ, Δr² +0.034 over 5 windows — [night_coh05_banded.csv](night_coh05_banded.csv)
- Superseded by `results_sim/legacy_nested_cal/` — [DATA_NOTES.md §6](DATA_NOTES.md)
- The ABC fit (P7) finds **no coherent CZ angle θ ≤ 0.15 that reproduces the routed rungs**:
  - posterior θ = 0.019 ± 0.017
  - held-out all_to_all r²_off predicted 0.914 against 0.659 on hardware (z = +2.4)
  - [results_sim/fit_coherence/README.md](results_sim/fit_coherence/README.md)
- CDR benchmark sim (θ = 0.05, 57 CZ): spread+near_target 0.109 against twirl_native+shared_random 0.194 (p = 5e-5). But twirling adds nothing inside spread (0.109 vs 0.106, p = 0.74) — [HANDOFF_P7.md §5](HANDOFF_P7.md)

**NI-CDR offline (runs/nicdr_offline).**
- MI-CDR (one noise model per window) is NO-GO on hardware:
  - Model misfit on training circuits is 0.023 / 0.013 / 0.043, against shot noise of about 0.002.
  - It is worse than CDR in 8 of 9 cells.
- The pre-specified 2-axis vnCDR on P5: geo ratio 1.12 [0.69, 1.73], 2/8 wins, p = 0.73.
- Simulated CDR error at 1M shots (0.007) is 3× below hardware (0.021).
- [runs/nicdr_offline/summary.md](runs/nicdr_offline/summary.md)

**Report "QEM combos and data reuse" (Polish), conclusions:**
- **CDR at ZNE's budget still wins at 12 CZ.** At 24,576 shots per point CDR has 0.0237 (off_copies) and 0.0167 (twirl_native) against ZNE's 0.0452. It wins 8/8 points with geo ratio 0.34–0.40, and its error saturates at 4–8× ZNE's budget.
- **ZNE's loss at 12 CZ is mostly a readout offset.** Richardson weights sum to 1, so an offset that does not depend on λ passes through unchanged. REM lowers ZNE from 0.0452 to 0.0162 (8/8). After REM, CDR vs REM+ZNE at 12 CZ is a tie (ratio 1.38 [0.72, 2.58]). At 39 CZ CDR at ZNE's budget beats REM+ZNE in 6/8 points (ratio 0.63–0.72).
- **The 39-CZ ZNE sits on the floor.** E(λ=5) is within −0.002 to +0.006 of the garbage floor, and the SNR against the floor is 0.4–0.8 (against zero it is 4.1).
- **The twirling "penalty" at 12 CZ is a log-floor artefact.**
- **Twirling raises r²:** Δr² +0.017 (7/8) and +0.116 (8/8).
- **Twirling is frame-limited.** Frame variance is 29× and 12× the shot variance.
- **Duration-scaled vnCDR on P5:** 0.0209 → 0.0134 (ratio 0.56, 7/8, p = 0.039). This is exploratory and was not confirmed; see draft Table neg.
- **Cross-topology:**
  - Lattices tolerate about 1.5–2× more CZ before r² falls to about 0.7.
  - Raw error slope is about 0.0045 per CZ on ODRA against 0.0016 per CZ on Garnet.
  - Emerald is "an illustration, not proof".
- **Novelty niches identified:**
  - CDR with two noise-scaling axes (CZ count and duration)
  - CDR with a learned, shared noise prior
  - a CDR+twirling(+DD) stack on an IQM star, with equal-budget and garbage controls
- [reports/QEM combos and data reuse.md](reports/QEM%20combos%20and%20data%20reuse.md)

### Inferences
- The earlier archive can support three things in the paper:
  - a **descriptive, multi-device appendix**: r² vs CZ on 3 devices, the Garnet ZNE ladder, mirror fidelity, and `[[4,2,2]]` as a negative result
  - **κ confirmation** on Garnet, with the clamp caveat
  - the **"pitfall catalogue" provenance story**, from DATA_NOTES §1–6
- It cannot support confirmatory claims.
- The skeleton-matched twirl windows (ODRA o1/o2, Garnet w1–w3) are the most defensible earlier data. They independently replicate the w01 Δr² > 0 result across 2 devices and 5 windows.

### Gaps
- Per-point data for Garnet and Emerald do not exist, only means, so paired tests are impossible.
- The number of ZNE estimates the silent clamp altered is unrecoverable ([DATA_NOTES.md §6](DATA_NOTES.md)).
- I did not open every `results_sim/legacy_nested_cal` or `bench_cdr` row, only their READMEs and summaries.

---

## Q2. What were the Garnet/Emerald findings and their status?

### Takeaway
**Garnet (20q, IQM Resonance)** confirmed the routing thesis with one error-vs-CZ curve across optimal and adverse placements, up to 96 CZ. ZNE's gain decays with CZ, CDR wins above about 39–57 CZ, and twirling raises CDR r² in 3 drift windows. REM is unavailable on Garnet.

**Emerald (54q)** has a single window with 4 points. CDR r² falls only at ≥ 69 CZ, and everything collapses at 114 CZ.

**Status:** archived means only, never re-run under the P0–P8 pipeline. The current paper draft v2 drops both devices entirely.

### Cited Findings

**Garnet full ladder, ZNE** (15 points, 4096 shots, REM off).

| placement | CZ | raw | ZNE |
|---|---|---|---|
| optimal | 12 / 24 / 39 / 57 | 0.061 / 0.075 / 0.136 / 0.163 | 0.019 / 0.073 / 0.106 / 0.131 |
| adverse | 36 / 42 / 54 / 96 | 0.117 / 0.102 / 0.144 / 0.205 | 0.087 / 0.082 / 0.117 / 0.177 |

- [garnet_full_results.csv](garnet_full_results.csv)
- ZNE gain decays from 3.2× (12 CZ) to 1.16× (96 CZ) — [SESSION_STATE.md](SESSION_STATE.md)
- Note: [routing_correlation_summary.csv](routing_correlation_summary.csv) lists different CZ counts for the same configurations (adverse star 42, linear 48, circular 63, all_to_all 102; optimal linear 27). This is an unexplained inconsistency.

**Garnet CDR** (n_train 40, 2048 shots).

| CZ | 12 | 36 | 57 | 96 |
|---|---|---|---|---|
| raw error | 0.036 | 0.130 | 0.106 | 0.160 |
| CDR error | 0.021 | 0.099 | 0.043 | 0.125 |
| r² | 0.992 | 0.952 | 0.850 | 0.688 |

- [garnet_cdr_results.csv](garnet_cdr_results.csv)
- Crossover by device, from the final report's table (winner in bold):

| device | CZ | raw | CDR | ZNE | winner |
|---|---|---|---|---|---|
| ODRA | 12 | 0.075 | 0.027 | **0.023** | ZNE |
| ODRA | 27 | 0.150 | **0.071** | 0.090 | CDR |
| ODRA | 36 | 0.186 | **0.105** | 0.142 | CDR |
| ODRA | 54 | 0.278 | 0.220 | 0.219 | tie |
| Garnet | 12 | 0.073 | 0.049 | **0.031** | ZNE |
| Garnet | 57 | 0.127 | **0.058** | 0.081 | CDR |
| Garnet | 96 | 0.111 | **0.058** | 0.103 | CDR |
| Emerald | 21 | 0.037 | **0.024** | 0.168 | CDR (ZNE hurts) |
| Emerald | 63 | 0.101 | **0.070** | 0.077 | CDR |
| Emerald | 69 | 0.079 | 0.059 | **0.049** | ZNE |
| Emerald | 114 | **0.101** | 0.279 | 0.139 | collapse |

- The final report puts the ZNE↔CDR crossover "around 39 CZ" and says ZNE is about 7× cheaper there — [final_raport.tex](final_raport.tex)
- Garnet per-placement winners: ZNE at 12 and 36 CZ, CDR at 57 and 96 CZ. Effective shots are ZNE 12,288 against CDR 83,968 — [garnet_crossover_summary.csv](garnet_crossover_summary.csv)
- **The crossover was "drawn, not computed".** `shots_to_target.compare_methods` and `shots_to_target_curve` are defined but never called — [project_review_gaps.md §1](project_review_gaps.md)

**Garnet twirl, 3 windows** (shot-matched, n_avg 6, 1024 shots).

| CZ | CDR error off → on | Δr² ± sd | per-window Δr² | verdict |
|---|---|---|---|---|
| 12 | 0.049 → 0.025 | +0.016 ± 0.019 | — | within drift |
| 57 | 0.058 → 0.043 | +0.069 ± 0.023 | +0.090 / +0.044 / +0.074 | significant |
| 96 | 0.058 → 0.031 | +0.073 ± 0.108 | — | within drift |

- [garnet_twirl_w123_banded.csv](garnet_twirl_w123_banded.csv)
- Per-window error ratios on/off range 0.24–1.11 — [twirl_pairs_all.csv](twirl_pairs_all.csv)
- The final report claims twirl gain is predicted by the untwirled r² (ρ = −0.85, p = 0.004) and that the mechanism is coherent error — [final_raport.tex abstract](final_raport.tex)
- **The ABC sim fit later contradicts the coherent mechanism** — [results_sim/fit_coherence/README.md](results_sim/fit_coherence/README.md); [reports/QEM combos and data reuse.md](reports/QEM%20combos%20and%20data%20reuse.md)

**Inconsistent Garnet r² values for the same rungs:**

| source | r² at 12 / 57 / 96 CZ | protocol |
|---|---|---|
| [cross_topology_summary.csv](cross_topology_summary.csv) | 0.980 / 0.851 / 0.787 | — |
| [garnet_twirl_w123_banded.csv](garnet_twirl_w123_banded.csv) | 0.969 / 0.853 / 0.827 | untwirled, 3-window mean |
| [garnet_cdr_results.csv](garnet_cdr_results.csv) | 0.992 / 0.850 / 0.688 | n_train 40, 1 window |

- The final report uses 0.827 and concludes Garnet never drops below r² < 0.8 — [final_raport.tex Tab. xtopo](final_raport.tex)
- The combos report uses 0.69 — [reports/QEM combos and data reuse.md](reports/QEM%20combos%20and%20data%20reuse.md)
- The paper must pick one protocol and say which.

**Emerald** (window em1, 2048 shots, n_avg 1).

| placement / pattern | CZ | raw | CDR | ZNE | r² |
|---|---|---|---|---|---|
| optimal star | 21 | 0.037 | 0.024 | 0.168 | 0.963 |
| adverse star | 63 | 0.101 | 0.070 | 0.077 | 0.961 |
| optimal all_to_all | 69 | 0.079 | 0.059 | 0.049 | 0.873 |
| adverse all_to_all | 114 | 0.101 | 0.279 | 0.139 | 0.683 |

- [emerald_xtopo.csv](emerald_xtopo.csv)
- `em_smoke.csv` is header-only — [em_smoke.csv](em_smoke.csv)
- Interpolated r² < 0.8 thresholds: star (ODRA) about 32 CZ, Emerald about 86 CZ; Garnet never below 0.8 up to 96 CZ, which is a lower bound — [final_raport.tex §sec:xtopo](final_raport.tex)
- ZNE harmed at Emerald 21 CZ (0.168 against raw 0.037). The final report says this agrees with the κ help–harm boundary (bias 0.0370 against threshold 0.0378), predicted correctly in 6 of 7 cases — [final_raport.tex](final_raport.tex)

**Hygiene and planning status.**
- Garnet and Emerald have no counts, no readout calibration and no REM. Garnet and Emerald still use their own transpilation path, not `compile_native` — [DATA_NOTES.md §1](DATA_NOTES.md); [reports/QEM combos and data reuse.md](reports/QEM%20combos%20and%20data%20reuse.md)
- The reviewer advises reprocessing the Garnet archive only where the path was correct (the twirl campaigns with a fixed layout) — [review/recenzja.md §8.2 N7](review/recenzja.md)
- Budget: about 312 of 3700.5 credits were spent at the SESSION_STATE snapshot. Drift windows and Emerald were still listed as "remaining" — [SESSION_STATE.md](SESSION_STATE.md)
- The `.planning` GSD roadmap (Garnet port → Emerald → meta-analysis → breakdown → report) shows 0/5 phases complete. It is stale: last activity 2026-08-26 — [.planning/STATE.md](.planning/STATE.md); [.planning/ROADMAP.md](.planning/ROADMAP.md)

### Inferences
- Garnet and Emerald are the only cross-topology evidence. They fit a descriptive "r² vs CZ per topology" figure with an explicit caveat about protocol differences:
  - n_train varies: 10 / 40 / 100
  - shots vary
  - the training sets were the shared-legacy ones
  - Emerald has 1 window and 4 points
- The "coherent mechanism" and "ρ = −0.85 decision rule" claims from the final report should not be carried into the paper unqualified.
- The help–harm κ result on Garnet is the strongest quantitative Month-2 claim. It is a replication of Scavino Alfaro (arXiv:2605.08251) per [review/recenzja.md §6](review/recenzja.md), not a discovery.

### Gaps
- No between-window variance for Emerald.
- The Garnet "drift windows" for the ZNE ladder (as opposed to twirl) were not found as separate files beyond `garnet_twirl_w1/2/3.csv`.
- No Garnet REM is possible.
- The source of the Garnet {1,3} κ = 3.39 data file was not located; it is cited only from `final_raport.tex`.

---

## Q3. What does the existing paper draft claim, and which claims are still TBD?

### Takeaway
The draft is `paper_draft/main.tex`, v2, aimed at IEEE QCE 2027 as a full paper (about 8 pages): "Honest Hardware Evaluation of Quantum Error Mitigation: Equal-Budget Controls, Pre-Registration and a Catalogue of Pitfalls on a Five-Qubit Star Processor". It is ODRA-only: Garnet, Emerald, `[[4,2,2]]` and banknote do not appear. `main_v1.tex` mentions lattices only as future work. All `\TBD` placeholders concern the w02vn result plus the code-availability URL and the acknowledgments. w02vn has since finished, and its summary file gives the fill: the primary hypothesis is NOT SUPPORTED.

### Cited Findings

**Claims made in the abstract and contributions:**
- an equal-budget protocol
- at equal cost CDR's 42× advantage shrinks; CDR saturates at 4–8× ZNE's budget
- at ZNE's budget CDR ties REM-corrected ZNE at 12 CZ (ZNE 0.045 → 0.016 with REM)
- at 39 CZ, ZNE collapse is seen by garbage folding and by a floor-referenced SNR, but not by W_neg or a zero-referenced SNR
- the identity-folding control is invalid because of T1
- the twirling penalty at 12 CZ is a log-floor artefact; twirling raises r² and is frame-limited (12–29× shot variance)
- P5: each µs multiplies raw error by 1.43, a confirmed pre-registered result (H7b); the CZ effect is unresolved
- negative results: MI-CDR, CDR–ZNE hybrids, duration covariates, P5 vnCDR

Sources: [paper_draft/main.tex l.47–122](paper_draft/main.tex)

**Main table (Tab. main):**

| estimator | 12 CZ | 39 CZ |
|---|---|---|
| raw λ=1 | 0.069 | 0.158 |
| REM raw | 0.049 | 0.149 |
| ZNE | 0.045 | 0.112 |
| ZNE + REM | 0.016 | 0.107 |
| garbage | 0.137 | 0.103 |
| identity | 0.072 | 0.194 |
| CDR@24k off_copies | 0.024 | 0.074 |
| CDR@24k twirl_native | 0.017 | 0.056 |
| CDR off_copies | 0.022 | 0.053 |
| CDR twirl_native | 0.015 | 0.040 |
| CDR spread | **0.012** | 0.068 |
| CDR twirl_native, shared_random | 0.031 | 0.032 |
| CDR twirl_logical, shared_random | 0.019 | **0.025** |

- [paper_draft/main.tex l.335–368](paper_draft/main.tex)

**Pilot section (exploratory):** κ = 15.8 ± 1.7, 12.5 ± 1.1, 20.7 ± 14.7, 26.0 ± 3.3 and 25.7 ± 11.3, and the archival 48 ± 6. Winner's curse in pilot twirl ratios (0.22–0.57). Decision changes only at small margins — [paper_draft/main.tex l.580–590](paper_draft/main.tex)

**TBD placeholders:**

| line | placeholder |
|---|---|
| 72 | w02vn primary result in one sentence (abstract) |
| 318 | commit hash of `prereg-vn1` |
| 571–577 | §IV-H: run date, number of circuits, interruptions; calibration-set IDs; complete points; mean error vnCDR vs CDR; geometric ratio with CI; wins/8; Wilcoxon p; verdict; sensitivity without calibration-change blocks; secondary variants; comparison with the simulated 0.0065 at 4.1M shots |
| 648 | deviations for w02vn |
| 668 | one-sentence w02vn conclusion |
| 673 | repository URL / DOI |
| 676 | acknowledgments |

- [paper_draft/main.tex](paper_draft/main.tex)

**The fill is available.** Per [runs/odra_campaign/w02vn/vncdr_summary.txt](runs/odra_campaign/w02vn/vncdr_summary.txt):
- complete points: 8, none excluded
- primary result: 2-axis vnCDR vs CDR, 4/8 wins, mean 0.0172 vs 0.0145, geo 1.212 [0.432, 3.430], p = 0.6289 → **NOT SUPPORTED**
- secondary variants: geo 0.85–1.22, all p ≥ 0.42
- raw vs CDR: geo 3.51
- the run log ends `=== KONIEC w02vn ===` at 2026-11-09 01:37 — [runs/odra_campaign/w02vn.log](runs/odra_campaign/w02vn.log)

**The headline numbers are reproducible.** The independent verification reproduced every declared night-A and P5 number from `counts.jsonl` to machine precision, with 0 mismatches — [review/weryfikacja.md §1, §4](review/weryfikacja.md)

**Other drafts.**
- `main_v1.tex` (725 lines) mentions Garnet and Emerald only as an outlook: "on lattices … the same function costs a different number of CZ" — [paper_draft/main_v1.tex l.688](paper_draft/main_v1.tex)
- An older draft, `spec/draft_artykul_QEM_ODRA.md`, claimed "12 calibration windows" and confirming κ "on two devices"; the reviewer flagged both as no longer true — [review/recenzja.md C18](review/recenzja.md)

### Inferences
- The draft currently leaves out the whole Month-2 cross-topology story that the project's Core Value is built around ("device- and topology-resolved characterization").
- The decision is to add a short descriptive cross-topology section or appendix, or to state explicitly that it is out of scope.
- With w02vn NOT SUPPORTED, the "duration-scaled vnCDR" lead becomes another negative result, and the forking-paths warning in Tab. neg is vindicated.

### Gaps
- I did not find the `prereg-vn1` commit hash in my searches; `git tag` was not checked.
- I did not check whether the w03dd and w04m results are referenced in the draft. They belong to the current campaign, which is out of scope here.

---

## Q4. What did the reviews in review/ criticise (weaknesses the paper must address)?

### Takeaway
The critical review ([review/recenzja.md](review/recenzja.md), 2026-10-25) judges the work "solid experimental craft without a confirmed headline result". Its venue estimates:

| venue | estimated chance |
|---|---|
| short paper or workshop | about 60–70% |
| QCE full paper | about 30–40% |
| TQE | about 20–30% |
| Quantum | about 10% |
| PRX Quantum | < 5% |

The verification ([review/weryfikacja.md](review/weryfikacja.md)) found 0 numeric mismatches. It also lists 10 code and data issues and finds the statistics anti-conservative.

### Cited Findings

**What stands** (§2.1):
- ZNE collapse at 39 CZ detected by garbage folding (genuine 0.112 vs garbage 0.103, p = 0.84). This is a replication of Köster & Mauerer, not a discovery.
- ZNE at 12 CZ beats garbage (p = 0.012) but not raw (p = 0.47).
- The identity control is invalid by construction.
- Twirling raises r² (+0.116 at 39 CZ, 8/8; +0.017 at 12 CZ, 7/8; p < 0.001), but this was not pre-registered.
- P5 duration effect: ×1.43 per µs, robust.
- [review/recenzja.md §2.1](review/recenzja.md)

**Overstated claims (C1–C19):**

| item | criticism |
|---|---|
| C1 | "−30% from twirling" at 39 CZ: n = 8, the pre-registered pooled p = 0.35, and the actual change is −25% |
| C2 | "nothing to fix at 12 CZ": false, the error is 5–10× the noise |
| C3 | "twirl CDR best on both rungs": false |
| C4 | contradictions in the SNR and W_neg diagnostics |
| C5 | the ZNE error has a constant positive sign (+0.01 to +0.076), a readout/T1 offset |
| C6 | two different "raw" columns are mixed |
| C7 | CZ vs idle in P5 is fully confounded with time of night and a calibration change: T1 of QB1 went 15.6 → 20.8 µs |
| C8 | duration is computed, not measured |
| C9, C10 | the L6/L9/L13 models are different functions; L13 training has 27 PRX against 70 in the target |
| C11 | the second Neyman κ window (20.7 ± 14.7) was omitted |
| C12 | the McNemar 2⁻³¹ figure is a strawman |
| C13 | winner's curse from pilots |
| C14, C15 | the twirling and depolarizing statements are only valid in expectation or for global noise |
| C16 | the training set is fully Clifford, not near-Clifford |
| C17 | the plan was frozen after night A had started, on a dirty commit |
| C18 | the draft claims 12 windows |
| C19 | the calibration ID detects recalibration, not drift |

- [review/recenzja.md §2.2](review/recenzja.md)

**Weaknesses W1–W15:**

| item | weakness |
|---|---|
| W1 | Power and heterogeneity: the sign of H1 differs between rungs, so the analysis needs an arm × n_CZ interaction model |
| W2 | One device, one window, no between-window variance. This breaks the project's own "≥ 2 calibration windows" rule. Garnet enters only from the defective archive |
| W3 | One block per condition, so drift is unidentifiable |
| W4 | 42× unequal budget and no REM for ZNE |
| W5 | ZNE diagnostic definitions |
| W6 | Training is not near-Clifford: 78–85% of ideals are 0 at 39 CZ, and training has 10 PRX against 20 in the target, so it sees weaker noise |
| W7 | Four separately trained classifiers on the ladder confound CZ count with the function |
| W8 | The identity control |
| W9 | Pre-analysis, not pre-data |
| W10 | The log-error model near zero |
| W11 | Uncorrected p-values outside the Holm family |
| W12 | Pseudoreplication in H3 (shared training set) |
| W13 | Incomplete factorial |
| W14 | Mean-Z specifics |
| W15 | Weak ML task: noiseless accuracy 0.675–0.767 |

- [review/recenzja.md §4](review/recenzja.md)

**Novelty** (§6):
- ZNE degeneracy and garbage folding: no novelty (Köster & Mauerer, arXiv:2607.09360).
- κ: a replication of Scavino Alfaro (arXiv:2605.08251).
- `spread` is close to Czarnik 2022.
- EIV: small contribution.
- Potentially novel: identity insertion separating CZ from duration; a decomposition of when twirling helps CDR; the pitfall catalogue.
- [review/recenzja.md §6](review/recenzja.md)

**Required fixes M1–M10** (about 2–3 weeks offline):

| item | task |
|---|---|
| M1 | finish night B |
| M2 | rewrite claims C1–C19 |
| M3 | ZNE + REM offline |
| M4 | thin counts to get equal-budget curves |
| M5 | floor-referenced diagnostics |
| M6 | P5 sensitivity analyses |
| M7 | variance decomposition |
| M8 | training–target mismatch report |
| M9 | verify night-A circuits across the commits `4b0d849` (dirty) and `ecaa139` |
| M10 | device-model simulation of the mechanisms |

- **Nice to have (N1–N7):** an interleaved P5 night (N1), true near-Clifford CDR (N2), a U(W†W)^k control (N3), a second window (N4, required for TQE), per-qubit CDR (N5), extended κ (N6), and Garnet reprocessing only for the fixed-layout twirl runs (N7) — [review/recenzja.md §8](review/recenzja.md)

**Verification issues:**
- B1: calibration ID mis-tagged; 1008 `star_cz52` records carry the old calibration.
- B2: the code uses a one-sided p for H7 where the pre-registration says two-sided.
- B3: no completeness assertion in `prereg_w01.py`.
- B4: clustered SE with G = 8. P5 raw duration p goes from 5e-13 to 1.7e-4 (t(7)) or 0.010 (wild bootstrap); P5 CDR CZ p becomes 0.018 or 0.020.
- B5: shot noise double-counted in the EIV spread.
- B6, B7: identity non-equivalence; a latent wire/clbit mapping bug that does not affect mean-Z.
- B8: two different "raw" columns in H4.
- B10: FLOOR = 1e-4.
- Power for H1 after night B: 0 (if B behaves like 12 CZ), 0.16 (like 39 CZ) and 0.006 (like a mix of night A).
- [review/weryfikacja.md §2–3](review/weryfikacja.md)

**Earlier review notes and project gaps (Month 1/2):**
- The headline crossover is drawn, not computed.
- The Emerald routing cost is computed but unused.
- topo_dist ↔ SWAP ↔ degradation correlation is promised but not synthesised.
- The second logical qubit of `[[4,2,2]]` is unused.
- ODRA is weakly integrated into the cross-method comparison.
- banknote is benched.
- DD was never tried on lattices.
- The placeholder lattice calibration risks entering quantitative claims.
- [project_review_gaps.md](project_review_gaps.md)

### Inferences
Draft v2 already absorbs most of M2–M8: equal budget, REM, the floor SNR, the log floor, Tab. neg, labelling exploratory results, and the deviations section. The items still open:
- **W2:** only one window. If the paper wants a cross-topology or between-window claim, the Garnet 3-window twirl data plus ODRA o1/o2 are the only between-window variance available.
- **W7:** ladder confound.
- **W15:** weak task.
- **M9:** dirty-commit integrity.
- **M10:** mechanism simulation. Partly done: the ABC result is negative.

### Gaps
- It is not verified whether M9 (the night-A commit consistency check) was ever done; no output was found in `review/scripts/tmp` listing.
- I did not check whether the C1–C19 slide corrections were applied to the `prezentacja_teoria*.tex` decks.

---

## Q5. What does reports/QEM combos and data reuse.md conclude?

### Takeaway
Existing data suffice for an equal-cost paper built on the w01 raw counts (nights A and P5). Garnet, Emerald and the older ODRA data serve as a meta-analysis of means. The report proposes one new method, duration-scaled vnCDR, which was later NOT SUPPORTED in w02vn. The research question shifts from "which method wins" to "what limits each method":
- ZNE: a scale-independent readout offset when shallow, and signal collapse when deep.
- CDR: map linearity degrading with routed CZ, partly restored by twirling.
- Twirling: the number of frames.

### Cited Findings

**What the report says is ready (from w01A):**
- CDR beats ZNE at equal budget at 12 CZ, 8/8 points (0.0237 / 0.0167 vs 0.0452).
- CDR saturates at 4–8× ZNE's budget; circular twirl_native gives 0.056 at 1×, 0.042 at 4× and 0.040 at 42×.
- REM fixes ZNE at 12 CZ (0.0452 → 0.0162) but not at 39 CZ (0.1115 → 0.1073).
- CDR barely responds to REM (0.0216 → 0.0211).
- Readout offset +0.029 and gain 0.96, from SSRO e01 ≈ 0.003–0.008 and e10 ≈ 0.025–0.051.
- After REM, a residual offset of about +0.016 remains at 12 CZ, consistent with T1 pull.

**Twirling numbers:**
- Frame variance is 29× and 12× the shot variance; at M = 6 that is about 55% and 25% of the squared error.
- Estimated bias as M → ∞: 0.013 vs 0.032 (12 CZ) and 0.043 vs 0.067 (39 CZ). The report's conclusion: "frames, not shots per frame, limit twirling."

**Negative results:**
- ZNE∘CDR hybrid gives a·ZNE + b, 2–8× worse than CDR (0.066 vs 0.0216), because it double-corrects the attenuation.
- CDR with a duration or PRX covariate: 0.0543 vs 0.0216.
- Attenuation transfer changes the error by ≤ 0.001.
- Model-informed CDR is a toy-sim result only: MAE 0.0071 vs 0.0105 over 12 trials.
- Classic vnCDR loses to CDR at equal budget until about 2.7M shots per target, because of the collinearity of E₁, E₃, E₅.

**DD:** no offline evaluation is possible. Month-1 DD was worse at every rung but confounded, and the P6 interleaved DD ablation was never implemented.

**Literature positioning:**
- vnCDR (Lowe et al. arXiv:2011.01157) is simulation-only, at about 501·N_s shots.
- UNITED (Bultrini et al.) shows the method ranking depends on the budget.
- The closest competitor is bnZNE (Harris et al. arXiv:2603.10224).
- No published CDR + twirling stack with controlled equal budget was found.
- All hardware combination studies are on IBM heavy-hex devices; IQM appears only in Köster & Mauerer and in Star NRE+ZNE reports.

**Prioritised plan:**

| step | cost | content |
|---|---|---|
| 1–5 | free | equal budget, REM, collapse diagnostic, twirling r²/frames, cross-topology mixed model |
| 6 | free | pooled MI-CDR (later: NO-GO) |
| 7 | 1 window | pre-registered duration vnCDR (later: w02vn, NOT SUPPORTED) |
| 8 | within the same window | a DD-on arm on the `star_idle*` schedule (w03dd exists in runs/, out of scope here) |

- [reports/QEM combos and data reuse.md](reports/QEM%20combos%20and%20data%20reuse.md)
- **Risk the report flags:** strong results rest on 1 window, 8 points and many variants, and the r² gain from twirling has no physical explanation; ABC excludes coherent ZZ — [reports/QEM combos and data reuse.md, "Wnioski"](reports/QEM%20combos%20and%20data%20reuse.md)

### Inferences
- The report's step 5 (a cross-topology mixed model of r² and error vs CZ for ODRA/Garnet/Emerald on summary rows) is the main unrealised use of Month-2 data. It is free, descriptive, and would restore the topology dimension to the paper.
- Its single "strong combination" lead failed confirmation (w02vn), which strengthens the paper's "protocol dissolves apparent effects" framing.

### Gaps
- No mixed-model output for cross-topology was found in `paper_analysis/out/`. Its frontier files (`frontier*.csv`) appear to cover the ODRA campaign only; I did not inspect them in detail.
