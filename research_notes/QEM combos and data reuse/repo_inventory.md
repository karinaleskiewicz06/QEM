# Repo inventory: existing QEM data and how to reuse it offline

Scope: every experimental and simulation result in `/Users/karinaleskiewicz/QEM` as of 2026-10-25,
what each one measured, how far it can be trusted, and what can be re-analysed **without new QPU
runs**. All "sources" are files in the repo (absolute root `/Users/karinaleskiewicz/QEM/`). Numbers
marked "(computed)" I computed read-only from the stored CSV or `counts.jsonl` while writing these
notes, with scratch scripts and nothing written to the repo. Workload everywhere: the frozen
5-qubit `two_curves` VQC classifier (`trained_models_hard/`, offset 0.1), observable mean-Z
(coeffs 0.2 ×5), unless noted. No credentials or URLs were read or printed.

---

## Q1. What data exists (device, circuits, methods, size, date)?

### Takeaway
There are four generations of data. (1) **Month-1 ODRA** (Jul 30–Aug 1): CSV means only, DD and REM arms.
(2) **Month-2 Garnet/Emerald** (late Aug to early Sep): CSV means only, routing ladders up to 96/114 CZ, ZNE/CDR/twirl/[[4,2,2]]/mirror.
(3) **Legacy ODRA twirl/κ/100-pt windows** (Sep 13–16): CSV means only, some tainted.
(4) **P0+ ODRA pilots and the w01 campaign** (Oct 23–25): full per-circuit `counts.jsonl` with QASM3, CZ skeleton, twirl frame, ideal values and calibration-set IDs, plus raw calibration dumps.
Only generation (4) supports real offline re-analysis. Generations (1)–(3) support only meta-analysis of summary statistics.

### Cited Findings

**A. ODRA (IQM Spark, 5q star). Generation 4 has per-circuit raw counts (runs/, P0 layout)**

| dataset | dates (UTC) | what | size | source |
|---|---|---|---|---|
| `runs/odra_campaign/w01A` (night A, **pre-registered**) | 2026-10-24 08:19 → 20:39 (with a resume) | rungs star 12 CZ and circular 39 CZ. CDR arms: `off_copies:near_target`, `twirl_native:near_target`, `spread:near_target`, `twirl_logical:shared_random`, `twirl_native:shared_random`. ZNE at λ∈{1,3,5}, Richardson, with genuine/identity/garbage folds | 10,192 records; 8 eval points (indices 0,3,…,21); n_train=20 (spread 120), M=6, S=8192; CDR budget 1,032,192 shots per point per arm, ZNE genuine 24,576 per point | [manifest](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01A/manifest.json), [cdr.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01A/cdr.csv) (160 rows = 5 arms × 2 fits × 2 rungs × 8 points), [zne.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01A/zne.csv) (48 rows), [review/weryfikacja.md §1](/Users/karinaleskiewicz/QEM/review/weryfikacja.md) |
| `runs/odra_campaign/w01P5` (P5 night, **pre-registered**) | 2026-10-24 20:39 → 10-25 09:21 | identity insertion on star: base 12 CZ; `star_cz24/36/52` (CZ·CZ pairs, PRX fixed at 20); `star_idle24/36/52` (12 CZ plus delay matched to the cz rung's duration); `star_L6/L9/L13` (deeper classifiers with 24/36/52 CZ and 35/50/70 PRX). `off_copies:near_target` CDR only, no ZNE | 10,080 records, 8 points, n_train=20, M=6, S=8192; 110 jobs | [manifest](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01P5/manifest.json), [cdr.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01P5/cdr.csv), [results/depth_regression_w01P5.csv](/Users/karinaleskiewicz/QEM/results/depth_regression_w01P5.csv) |
| `runs/odra_campaign/w01B` (night B, **pre-registered, incomplete**) | started 2026-10-25 09:22; `finished_utc` null | linear 30 / all_to_all 57, same arms as A | only 400 of 10,192 planned records: 3 complete points (0, 3, 6) and 22 training records of point 9, all in the `all_to_all/twirl_native/near_target` block. Log shows "ODRA not answering" repeatedly through 19:18 local on 10-25 | [manifest](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01B/manifest.json), [w01.log](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01.log) (computed) |
| `runs/odra_campaign/sim1` | 2026-10-24 (sim) | device-model simulation of the campaign; rungs star 12 / all_to_all 57; arms include `spread_off` and `off_copies:shared_random`. Built from `spec/odra_cal_example.json`, θ=φ=ε=0 | 15,520 of 36,624 planned records (unfinished) | [manifest](/Users/karinaleskiewicz/QEM/runs/odra_campaign/sim1/manifest.json) |
| `runs/odra_pilot/p1/p2/p3_logical` (exploratory) | p1 10-23 11:46–12:24; p2 21:40–22:41; p3 10-24 02:21–03:23 | `run_garnet_twirl.py` on ODRA: raw, CDR off/on with logical twirl, ZNE {1,3,5}. p1 and p3 cover star 12 and all_to_all 57; p2 covers linear 30 and circular 39 | 1,088 records each; 4 eval points; n_train=10, M=6, S=8192; legacy shared training set; per-point ZNE values in `*_zne_points.csv` | [p1 manifest](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p1_logical/manifest.json), [p1 twirl_logical.csv](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p1_logical/twirl_logical.csv), [p2](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p2_logical/twirl_logical.csv), [p3](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p3_logical/twirl_logical.csv) |
| `runs/odra_pilot/p1/p2/p3_native` (exploratory) | p1 10-23 12:39–13:39; p2 22:41–23:41; p3 10-24 03:23–04:22 | CDR off/on with native (merged-1q) twirl, same rungs as the logical runs | 1,056 records each; 4 points; n_train=10, M=6 | [p1](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p1_native/twirl_native.csv), [p2](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p2_native/twirl_native.csv), [p3](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p3_native/twirl_native.csv) |
| `runs/odra_pilot/p2_cdr100` (exploratory) | 10-23 23:41 → 10-24 01:12 | `run_odra_cdr.py --zne` on all 4 rungs (12/30/39/57). CDR with 100 training circuits shared across all points, plus ZNE λ=3,5 on all **100 eval points** (λ=1 is the CDR eval circuit) | 1,600 records: per rung, 100 train + 100 eval at λ1 + 100 at λ3 + 100 at λ5; S=8192 | [manifest](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p2_cdr100/manifest.json), [cdr_zne_100pt.csv](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p2_cdr100/cdr_zne_100pt.csv) |
| `runs/odra_pilot/p2_depth_L6/L9/L13` (exploratory) | 10-24 01:12–02:21 | star classifiers with 6/9/13 layers (24/36/52 CZ), CDR (100 train) and ZNE on 100 points | 400 records each | [L6](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p2_depth_L6/cdr_zne.csv), [L9](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p2_depth_L9/cdr_zne.csv), [L13](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p2_depth_L13/cdr_zne.csv) |
| `runs/odra_pilot/*kappa*` (exploratory) | 10-23 15:43 → 10-24 05:02 | `zne_shot_boundary.py`, star 12 CZ, budgets S∈{256,…,4096}, 10 reps, 4 points. p1: Neyman {1,3,5}. p2_n13: Neyman {1,3}. p2_n1357: Neyman {1,3,5,7}. p2_u135: uniform {1,3,5}. p3_n135 and p3_n1357 repeat Neyman | 608–1,016 records each, all with per-rep counts | [p1 kappa_neyman.csv](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p1_kappa/kappa_neyman.csv), [p3_n135 kappa.csv](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p3_kappa_n135/kappa.csv), etc. |
| Calibration dumps | 2026-07-30, 08-03, 10-23 (start/end), 10-23 23:37 (start/end), "10-24_start" (actually collected 10-23 16:13), w01A start/end, w01B start, w01P5 start/end | mapped files (`odra_*.json`: t1, t2, t2_echo, p_1q, p_2q, p_ro). Raw dumps (`odra_raw_*.json`) also carry per-qubit `single_shot_01_error` / `single_shot_10_error`, CZ IRB, PRX RB and gate durations | — | [calibrations/](/Users/karinaleskiewicz/QEM/calibrations/), [review/recenzja.md §9 B11](/Users/karinaleskiewicz/QEM/review/recenzja.md) |

Every generation-4 record carries `counts` (full 5-bit histogram), `shots`, `expval`, `n_cz`, `n_prx`, `depth`, `cz_skeleton`, `duration_s` and `qasm3`.
- w01 records add `ideal`, `role` (train/target), `train_index`, `repeat_index`, `twirl_kind`, `frame` (Pauli frame string), `skeleton_matches_target`, `insert_pairs`/`insert_mode`, `duration_sched_s`, `calibration_set_id`, and `scale`/`variant` for ZNE.
- Pilot records lack `ideal`. Ideals can be recomputed from `qasm3` by statevector (5 qubits) (computed: key listing).
- `review/weryfikacja.md §1` re-derived every w01A/P5 CSV number from `counts.jsonl` to machine precision (MISMATCH: 0) ([weryfikacja §1, §4](/Users/karinaleskiewicz/QEM/review/weryfikacja.md)).

**B. ODRA, generations 1 and 3: CSV means only, no per-circuit counts**

| file | date | content | source |
|---|---|---|---|
| `hardware_results.csv` | Month-1, 2026-07-30 → 08-01 | routing ladder 12/27/36/54 CZ × DD off/on. Columns: raw, REM, ZNE linear/Richardson/exp, accuracy. 30 points, 3 reps, 4096 shots, job IDs included | [hardware_results.csv](/Users/karinaleskiewicz/QEM/hardware_results.csv) |
| `two_curves_mirror_fidelity.csv` (+ `_sim`) | Month-1 | mirror survival per pattern, DD off/on; 5 points, 1 rep, 8192 shots | [file](/Users/karinaleskiewicz/QEM/two_curves_mirror_fidelity.csv) |
| `odra_twirl_o1.csv`, `odra_twirl_o2.csv`, `odra_twirl_banded.csv` | o1 2026-09-13/14 (92 jobs), o2 09-15 (32 jobs) | ladder 12/30/39/57. raw, CDR off/on (logical twirl), ZNE; 4 points, 8192 shots, n_train=10, M=6. Banded file = mean/sd over the 2 windows | [DATA_NOTES §5](/Users/karinaleskiewicz/QEM/DATA_NOTES.md), [odra_twirl_banded.csv](/Users/karinaleskiewicz/QEM/odra_twirl_banded.csv) |
| `odra_twirl_native_o1.csv` | 09-14 | old native twirl, before the 1q-merge fix: twirled circuits carried roughly 2× the PRX (e.g. star r_tw_old 92 vs 40) | [spec/native_twirl_merge_check.csv](/Users/karinaleskiewicz/QEM/spec/native_twirl_merge_check.csv) |
| `odra_full_100pt.csv`, `odra_cdr_100pt.csv` | ~09-08 | 100-point CDR (n_train 100) + ZNE on ladder 12/27/36/54 | [file](/Users/karinaleskiewicz/QEM/odra_full_100pt.csv) |
| `odra_depth_L6/L9/L13.csv` | 09-16 | star depth ladder 24/36/52 CZ, CDR 100 pt (ZNE column empty) | [L13](/Users/karinaleskiewicz/QEM/odra_depth_L13.csv) |
| `odra_kappa_k7.csv` | 09-14 | κ at scales {1,3,5,7}, uniform allocation, star 12 and all_to_all 57, budgets 256–8192 | [file](/Users/karinaleskiewicz/QEM/odra_kappa_k7.csv) |
| `twirl_pairs_all.csv` | compiled 10-12 | per-window CDR off/on err and r² pairs, ODRA o1/o2 + Garnet w1/w2/w3 | [file](/Users/karinaleskiewicz/QEM/twirl_pairs_all.csv) |
| `r2_excess_over_null.csv` | 10-12 | ODRA r²_off minus nested-cal sim null: −0.02 / −0.19 / −0.25 / −0.28 at 12/30/39/57 CZ | [file](/Users/karinaleskiewicz/QEM/r2_excess_over_null.csv) |
| `runs/legacy_logs/job_index.csv` | — | 153 IQM job IDs with UUIDv7 times | [README](/Users/karinaleskiewicz/QEM/runs/legacy_logs/README.md) |

**C. IQM Garnet (20q lattice) and Emerald (54q lattice): CSV means only, all generation 2**

| file | content | source |
|---|---|---|
| `garnet_full_results.csv` | 8 rungs: optimal 12/24/39/57 and adverse 36/42/54/96 CZ. raw, ZNE (REM off); 15 points, 4096 shots | [file](/Users/karinaleskiewicz/QEM/garnet_full_results.csv) |
| `garnet_gonogo_results.csv` | 4 rungs, go/no-go pilot | [file](/Users/karinaleskiewicz/QEM/garnet_gonogo_results.csv) |
| `garnet_cdr_results.csv` | CDR at 12/36/57/96 CZ, n_train 40, 2048 shots, r² 0.99/0.95/0.85/0.69 | [file](/Users/karinaleskiewicz/QEM/garnet_cdr_results.csv) |
| `garnet_acc100_results.csv` | adverse all_to_all, 96 CZ, 100 points, raw/ZNE accuracy | [file](/Users/karinaleskiewicz/QEM/garnet_acc100_results.csv) |
| `garnet_mirror_results.csv` | mirror survival, 8 rungs (24–150 mirror CZ), 3 inputs | [file](/Users/karinaleskiewicz/QEM/garnet_mirror_results.csv) |
| `garnet_qec422_results.csv` | [[4,2,2]] detection, layers 1–4, optimal 40–131 / adverse 64–164 CZ; acceptance 0.50–0.75; 3 seeds, 8192 shots | [file](/Users/karinaleskiewicz/QEM/garnet_qec422_results.csv) |
| `garnet_twirl_w1/w2/w3.csv`, `_banded`, `_w12_banded`, `_w123_banded` | 3 windows; rungs 12/57/96; raw, CDR off/on, ZNE; 4 points, 1024 shots, n_train 10, M 6 | [final_raport.tex Tab. założenia](/Users/karinaleskiewicz/QEM/final_raport.tex) |
| `garnet_crossover_summary.csv`, `routing_correlation_summary.csv` | ZNE-vs-CDR winner per rung; error vs CZ, SWAPs, topological distance and depth | [file](/Users/karinaleskiewicz/QEM/garnet_crossover_summary.csv) |
| `zne_shot_boundary_results.csv`, `zne_boundary_k4_results.csv` | κ / break-even shot budget. The files have no device column. The `zne_shot_boundary.py` docstring names Garnet optimal and adverse star | [zne_shot_boundary.py header](/Users/karinaleskiewicz/QEM/zne_shot_boundary.py) |
| `emerald_xtopo.csv` | one window `em1`; optimal 21/69 and adverse 63/114 CZ; raw/CDR/ZNE, no twirl; 4 points, 2048 shots, n_avg 1 | [file](/Users/karinaleskiewicz/QEM/emerald_xtopo.csv) |
| `em_smoke.csv` | header only | — |
| `cross_topology_summary.csv` | Garnet 12/57/96 combined with Emerald 21/63/69/114 (raw, CDR, r², ZNE) | [file](/Users/karinaleskiewicz/QEM/cross_topology_summary.csv) |
| `routing_ladder_{odra,garnet,emerald}{,_optimal,_adverse}.csv` | transpile-only ladders (CZ, SWAPs, topo_dist, depth); Emerald adverse reaches 78–135 CZ | [routing_ladder_emerald_adverse.csv](/Users/karinaleskiewicz/QEM/routing_ladder_emerald_adverse.csv) |
| Unitarity RB on a Garnet pair | u=0.843, p=0.908, so u−p²=+0.019; drift between windows ≈0.09. **No CSV found**: numbers exist only in the report | [final_raport.tex ~l.939](/Users/karinaleskiewicz/QEM/final_raport.tex) |

**D. Simulations**

| path | content | source |
|---|---|---|
| `results_sim/bench_cdr/*_{reference,uniform}.csv` | P7 device model (calibration 2026-08-03, θ=0.05, φ=0.03), all_to_all 57 CZ; 8 reps × 8 targets; arms off_copies, twirl_native, spread_off, spread × {near_target, shared_random} × {OLS, EIV}; 1,024 rows each | [README](/Users/karinaleskiewicz/QEM/results_sim/bench_cdr/README.md) |
| `results_sim/fit_coherence/{spec_grid,extended_theta,cal20260730}` | ABC fit of a coherent CZ angle θ (and PRX ε) to the ODRA o1/o2 twirl statistics | [README](/Users/karinaleskiewicz/QEM/results_sim/fit_coherence/README.md) |
| `results_sim/wneg_null/` | W_neg null for genuine/identity/garbage folds, depolarizing noise, 24 points × 3 draws × 4 rungs | [README](/Users/karinaleskiewicz/QEM/results_sim/wneg_null/README.md) |
| `results_sim/legacy_nested_cal/` | nested ODRA-calibration nulls: θ=0 / 0.02 / 0.05, 3 sim windows | [README](/Users/karinaleskiewicz/QEM/results_sim/legacy_nested_cal/README.md) |
| `results_sim/device_model/schedule_sensitivity.csv` | error under ALAP vs ASAP vs no-idle schedules | [HANDOFF_P7 §5](/Users/karinaleskiewicz/QEM/HANDOFF_P7.md) |
| `results_sim/hardware_sim_smoke.csv` | `run_hardware.py --sim-device`, DD off/on at 12 and 57 CZ | [file](/Users/karinaleskiewicz/QEM/results_sim/hardware_sim_smoke.csv) |
| `results_sim/legacy_sim_bench_qiskit2.5.2/cdr_variants_sim_raw.csv` | 9,216 rows; CDR-variant benchmark on Qiskit 2.5.2 (ladder 12/27/36/54) | [README](/Users/karinaleskiewicz/QEM/results_sim/legacy_sim_bench_qiskit2.5.2/README.md) |
| `night_null_*`, `night_coh05_*`, `night_coh10_*` | companion sims (null and coherent controls) with the Garnet-shaped ladder 33/87/90 | [DATA_NOTES §6](/Users/karinaleskiewicz/QEM/DATA_NOTES.md) |
| `zne_dryrun_results.csv`, `zne_hard_results.csv`, `cdr_results.csv`, `cdr_hard_results.csv`, `qec422_results.csv`, `random_mirror_results.csv`, `scope_*_results.csv`, `zne_signal_retention.csv`, `margin_stratify*.csv`, `hard_accuracy_results.csv` | Month-1/2 sim campaigns (ladder 12/27/36/54; QEC 34–157 CZ; detection+ZNE scopes) | CSV headers (computed) |
| `banknote_study/*` | Month-1 Banknote classifier, hardware and sim, with DD off/on rows. **Declared out of scope** | [DATA_NOTES §8](/Users/karinaleskiewicz/QEM/DATA_NOTES.md) |

**Headline values, for orientation (computed from the files cited):**

- **w01A, mean over 8 points, OLS:**

  | arm (rung) | err raw | err mitigated | r² |
  |---|---|---|---|
  | `off_copies` (star) | 0.0737 | 0.0216 | 0.972 |
  | `twirl_native:near_target` (star) | 0.0763 | 0.0150 | 0.989 |
  | `spread` (star) | — | 0.0122 | — |
  | `off_copies` (circular) | 0.161 | 0.0529 | 0.789 |
  | `twirl_native:near` (circular) | — | 0.0397 | 0.905 |
  | `spread` (circular) | — | 0.0679 | 0.677 |
  | `twirl_logical:shared` (circular) | — | 0.0248 | — |
  | `twirl_native:shared` (circular) | — | 0.0320 | — |

  ZNE genuine / garbage / identity: star 0.045 / 0.137 / 0.072; circular 0.112 / 0.103 / 0.194. ZNE raw at λ1 was 0.069 / 0.158. ([w01A/cdr.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01A/cdr.csv), [w01A/zne.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01A/zne.csv))
- **w01P5, mean over 8 points:**

  | rung | raw err | CDR err | r² |
  |---|---|---|---|
  | star (12 CZ) | 0.067 | 0.021 | 0.963 |
  | cz24 / cz36 / cz52 | 0.094 / 0.159 / 0.177 | 0.022 / 0.072 / 0.074 | 0.917 / 0.780 / 0.648 |
  | idle24 / idle36 / idle52 | 0.090 / 0.112 / 0.147 | 0.014 / 0.031 / 0.037 | 0.951 / 0.919 / 0.821 |
  | L6 / L9 / L13 | 0.116 / 0.227 / 0.251 | 0.037 / 0.135 / 0.185 | 0.864 / 0.807 / 0.631 |

  ([w01P5/cdr.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01P5/cdr.csv))
- **P5 regression (L3 rungs, point fixed effects):**
  - log raw error per 10 CZ: coefficient −0.046 (p=0.68); per µs: +0.36 (p=5e-13, asymptotic).
  - log CDR error per 10 CZ: +0.29 (p=0.002).
  - ([depth_regression_w01P5.csv](/Users/karinaleskiewicz/QEM/results/depth_regression_w01P5.csv))
  - With small-cluster corrections: raw-duration p = 1.7e-4 (t₇) and 0.010 (wild bootstrap); CDR-CZ p = 0.018–0.020 ([weryfikacja F4](/Users/karinaleskiewicz/QEM/review/weryfikacja.md)).

### Inferences
- The only ODRA sets with matched routing, per-target training, stored frames and stored ideals are w01A and w01P5 (plus the w01B fragment). They should be the backbone of any quantitative re-analysis. The 7 pilot windows add counts at 4 points on all four rungs but use the shared training set.
- The P5 night carries a clean, non-pre-hyped mechanistic result. At matched duration, adding CZs raises the *CDR* error and lowers r² (cz52 r² 0.65 vs idle52 0.82), while the *raw* error is driven by duration. In other words, routing CZs hurt the linearity CDR relies on more than they hurt the raw signal. This fits the paper's "where QEM stops paying" axis. It is subject to the calibration and time-of-night confounds in Q2.

### Gaps
- No per-circuit counts were found for any Garnet, Emerald, Month-1 ODRA, or o1/o2 ODRA run. Their raw data would exist only on IQM servers (job IDs in `hardware_results.csv` and `runs/legacy_logs/job_index.csv`). Fetching them is an online action and out of scope.
- Unitarity-RB data: no file located, only report text.
- `random_mirror_results.csv` (ODRA, 61–226 CZ): I could not determine from the file whether it is hardware or simulation.

---

## Q2. Which datasets are known-defective, and what can be salvaged?

### Takeaway
Most generation-1–3 ODRA CDR numbers have at least one documented defect:
- routing mismatch between training circuits and target (non-star patterns of the 12/27/36/54 ladder);
- one training set shared by all points;
- silent ZNE clamping;
- per-Clifford calibration in the sims;
- DD ordering confounds.

Each is still usable for ordinal or qualitative statements, or as a contrast showing why the corrected protocol matters.

### Cited Findings
- **Two ladders, two compile paths.** 12/27/36/54 comes from `native_transpile` (no layout, no seed) and is non-deterministic: 5 distinct CZ skeletons in 5 compiles for linear/circular/all_to_all. 12/30/39/57 comes from the fixed-layout path. Qiskit 2.4.1 is the version consistent with the archive ([DATA_NOTES §1–2](/Users/karinaleskiewicz/QEM/DATA_NOTES.md)).
- **CDR routing mismatch.** In `odra_full_100pt.csv` and `odra_cdr_100pt.csv`, 0–2 of 10 training circuits shared the target's CZ skeleton for every routed pattern; star was 10/10. Their r² and err_cdr columns are tainted. The twirl campaigns (`odra_twirl_o1/o2`, `garnet_twirl_w*`) used the fixed-layout path, so skeletons match ([DATA_NOTES §3](/Users/karinaleskiewicz/QEM/DATA_NOTES.md)).
- **Shared training set.** All archived campaigns, and the pilots and w01 `shared_random` arms, reuse circuits 1..n-1 for every target. Every rotation is snapped to Clifford, so these are random Clifford circuits sharing a skeleton. Fits across points are strongly correlated ([DATA_NOTES §4](/Users/karinaleskiewicz/QEM/DATA_NOTES.md)). In w01A the shared-set training ideals took only the values 0 and ±0.2, identical between points in 135–140 of 140 cases ([weryfikacja F7](/Users/karinaleskiewicz/QEM/review/weryfikacja.md)).
- **ZNE clamping.** Every archived ZNE error (twirl campaigns, `odra_full_100pt`, κ campaigns) was silently replaced by the linear fit when |E|>1.25. How often this happened cannot be recovered. Since P3, `fallback_used` and `unphysical` are stored ([DATA_NOTES §6](/Users/karinaleskiewicz/QEM/DATA_NOTES.md)). In w01A, `unphysical` and `fallback_used` are 0 in every row (computed).
- **Four eval points per ladder point** in the twirl campaigns: only means, no per-point distribution ([DATA_NOTES §6](/Users/karinaleskiewicz/QEM/DATA_NOTES.md)).
- **Simulated nulls.** `night_null_*` used placeholder `p_2q=0.01`, and its coherent control had coherent error only, so the two are not nested. `results_sim/legacy_nested_cal/` supersedes it, but its p_2q comes from per-Clifford RB (≈2.5× the CZ IRB error), it used a fixed transpiler seed (no window variance), the shared training set, and the pre-P1 compile path. It covers ODRA only, since `calibrations/garnet.json` is topology-only ([DATA_NOTES §6](/Users/karinaleskiewicz/QEM/DATA_NOTES.md), [legacy_nested_cal README](/Users/karinaleskiewicz/QEM/results_sim/legacy_nested_cal/README.md)).
- **Failed run.** ODRA native twirl on 2026-10-12: header-only CSVs. Two job IDs may still be recoverable server-side ([runs/legacy_failed/2026-10-12/NOTE.md](/Users/karinaleskiewicz/QEM/runs/legacy_failed/2026-10-12/NOTE.md)).
- **Aborted partial records kept aside:**
  - `p1_logical/counts_all_to_all_attempt1_aborted.jsonl`: 268 records ([NOTE](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p1_logical/NOTE.md)).
  - `p2_kappa_u135/counts_S4096_attempt1_aborted.jsonl`: 40 raw records ([NOTE](/Users/karinaleskiewicz/QEM/runs/odra_pilot/p2_kappa_u135/NOTE.md)).
- **Old native twirl** (`odra_twirl_native_o1.csv`): the PRX overhead before the 1q-merge fix (e.g. all_to_all 356 vs 130 PRX) confounds any native-vs-logical comparison ([spec/native_twirl_merge_check.csv](/Users/karinaleskiewicz/QEM/spec/native_twirl_merge_check.csv)).
- **o2 is a third the size of o1** (32 vs 92 jobs); whether it is complete is unresolved ([DATA_NOTES §5](/Users/karinaleskiewicz/QEM/DATA_NOTES.md)).
- **w01-specific issues** ([weryfikacja F2, F5, F6](/Users/karinaleskiewicz/QEM/review/weryfikacja.md); [recenzja C5, C7, C10, B6, B10](/Users/karinaleskiewicz/QEM/review/recenzja.md)):
  - The `identity` fold is not a noise-equivalent control: T1 drives ⟨O⟩ toward +1, reaching 0.57 at circular λ5.
  - Calibration changed mid-block in P5 (`star_cz52`), and all of that block's records carry the old calibration tag. `star_cz24` and `star_L6` ran entirely on the new calibration (higher T1).
  - Arms are time blocks hours apart.
  - The first part of night A ran on a dirty commit `4b0d849`.
  - The CDR training circuits have about 50% of the target's PRX (L13: 27 vs 70).
  - ZNE carries a constant +0.04–0.05 offset at 12 CZ from readout/T1, because there is no REM.
- **ABC fit.** No coherent CZ angle θ ≤ 0.15 inside the calibrated budget reproduces ODRA's routed-rung r² drop or twirl gain. Held-out all_to_all r²_off is predicted at 0.91 against 0.66 on hardware ([fit_coherence README](/Users/karinaleskiewicz/QEM/results_sim/fit_coherence/README.md)). This contradicts the final report's claim that the θ=0.05 companion sim reproduces the hardware r² drop ([final_raport.tex ~l.935](/Users/karinaleskiewicz/QEM/final_raport.tex)). The two used different models: the final report's sim used the placeholder or legacy noise.

### Inferences
- **Salvageable as-is:**
  - star-pattern CDR in the legacy 100-pt files (star skeleton was always matched);
  - all raw and ZNE means as ordinal error-vs-CZ curves (the clamp affects ZNE, not raw);
  - twirl campaigns o1/o2 and Garnet w1–w3, for the twirl Δr² sign and magnitude, since skeletons matched;
  - Month-1 DD rows as a qualitative negative, flagged as confounded.
- **Salvageable as a negative or methodological contrast:**
  - `odra_full_100pt.csv` (routing-mismatched CDR) next to `p2_cdr100` (same 100-pt design, matched skeleton, 12/30/39/57). Both have r² falling with CZ: legacy 0.96/0.81/0.79/0.60; matched 0.93/0.82/0.69/0.60. This shows how much of the CDR breakdown survives fixing routing. The CZ ladders differ, so pair by rank.
  - Legacy depth L6/L9/L13 (`odra_depth_*`, Sep 16) next to pilot L6/L9/L13 (Oct 24) and w01P5 L6/L9/L13. This is a three-epoch replication of the depth ladder, with r² 0.83/0.72/0.44, 0.67/0.52/0.32 and 0.86/0.81/0.63. The spread itself shows drift across epochs.
- **The `identity` fold results** are reusable as a documented T1 artefact, not as a control.

### Gaps
- How often the archived ZNE clamp fired cannot be recovered (only means were stored).
- Whether Garnet's CDR training circuits shared the target's routing is not documented. Garnet and Emerald go through their own transpilation (`iqm_resonance.transpile_for_backend`), and the routing-match audit in DATA_NOTES covers ODRA paths only.

---

## Q3. Is there dynamical decoupling (DD) data, and what did it show?

### Takeaway
Hardware DD data exists only from Month-1 ODRA, non-interleaved. There DD-on was worse at every ladder rung and in mirror fidelity. The device-model simulation says DD should help slightly. The interleaved P6 DD ablation was never implemented. No DD data exists on Garnet/Emerald or in any generation-4 run.

### Cited Findings
- **`hardware_results.csv` (ODRA, Month-1, 30 points, 3 reps, 4096 shots).** Raw error DD-off → DD-on:
  - star 12 CZ: 0.112 → 0.159
  - linear 27: 0.281 → 0.375
  - circular 36: 0.299 → 0.382
  - all_to_all 54: 0.357 → 0.458

  Richardson ZNE is also worse with DD (star 0.024 → 0.029; all_to_all 0.239 → 0.373) ([hardware_results.csv](/Users/karinaleskiewicz/QEM/hardware_results.csv)).
- **`two_curves_mirror_fidelity.csv`.** Survival off → on: star 0.549 → 0.389; all_to_all 0.094 → 0.048. F_per_cz 0.975 → 0.961 at star ([file](/Users/karinaleskiewicz/QEM/two_curves_mirror_fidelity.csv)). In simulation DD slightly helped (0.330 → 0.367), because DD pulses were modelled as ideal ([raport_month_1.tex l.678–682](/Users/karinaleskiewicz/QEM/raport_month_1.tex)).
- **Confounds.** DD-off always ran before DD-on; the circular pair was split across 30 July and 1 August; the campaign spans three days ([DATA_NOTES §5–6](/Users/karinaleskiewicz/QEM/DATA_NOTES.md)). DD used IQM's built-in compiler strategy ([raport_month_1.tex l.244](/Users/karinaleskiewicz/QEM/raport_month_1.tex)).
- **P7 device model sim** (`hardware_sim_smoke.csv`, 8 points, 2048 shots). DD lowers raw error: star 0.128 → 0.114, all_to_all 0.361 → 0.332 ([file](/Users/karinaleskiewicz/QEM/results_sim/hardware_sim_smoke.csv)).
- **Interleaved DD was never run.** `campaign/odra_window.py --dd-ablation` raises SystemExit: "implemented with P6 (interleaved ABAB DD …)" ([campaign/odra_window.py l.555, 591–592](/Users/karinaleskiewicz/QEM/campaign/odra_window.py)). All w01 manifests have `dd_ablation: false`.
- **The reviewer's Aer ablation** shows DD (echo T2 in idle) does not remove the T1-driven identity-fold drift: star identity λ5 +0.129 with DD vs +0.132 without ([weryfikacja F2](/Users/karinaleskiewicz/QEM/review/weryfikacja.md)).
- **Banknote (out of scope)** has DD on/off hardware and mirror rows ([banknote_study/banknote_hardware_results.csv](/Users/karinaleskiewicz/QEM/banknote_study/banknote_hardware_results.csv), [banknote_mirror_fidelity.csv](/Users/karinaleskiewicz/QEM/banknote_study/banknote_mirror_fidelity.csv)).

### Inferences
- Offline, a DD + twirling + CDR combination cannot be evaluated on hardware. No dataset has DD together with twirling or CDR, and the only DD data predates the routing-matched compile path and uses the 12/27/36/54 ladder.
- **What the existing data does support for a DD claim:**
  1. the P5 finding that raw error is duration-driven at fixed gate count, which is the regime DD targets;
  2. the idle-insertion rungs (`star_idle*`), which are a ready-made DD-off baseline for a future DD-on run at identical schedules;
  3. the T1 floor (identity-fold drift and the ZNE offset), which DD cannot fix (amplitude damping), bounding what DD can buy.
- Month-1 DD-on penalties of 30–40% relative are larger than typical calibration drift between windows (`odra_twirl_banded` raw sd ≈0.005–0.01). That suggests a real DD penalty under IQM's default DD on ODRA, but ordering could explain part of it.

### Gaps
- No DD data on Garnet, Emerald, or any P0+ ODRA window.
- I found no DD sequence specification beyond "IQM built-in strategy".

---

## Q4. Is there cross-topology data (Garnet/Emerald) usable for a routing-cost comparison with ODRA?

### Takeaway
Yes, but only as summary means. Garnet has the richest set: 8-rung ladder with raw+ZNE, 4-rung CDR, 3-window twirl, [[4,2,2]], mirror. Emerald has one window with 4 rungs × raw/CDR/ZNE. Both use the same frozen classifier and mean-Z observable, but they differ from ODRA in shots, eval points, training set and transpiler, and have no counts. This is enough for a meta-level, CZ-indexed comparison of "r² and error vs CZ" across three topologies, not for paired statistics.

### Cited Findings
- **Garnet raw / ZNE error.**

  | placement | rung (CZ) | raw | ZNE |
  |---|---|---|---|
  | optimal | 12 | 0.061 | 0.019 |
  | optimal | 57 | 0.163 | 0.131 |
  | adverse | 96 | 0.205 | 0.177 |

  15 points, 4096 shots, REM off because the Resonance backend exposes no readout calibration ([garnet_full_results.csv](/Users/karinaleskiewicz/QEM/garnet_full_results.csv); [SESSION_STATE.md](/Users/karinaleskiewicz/QEM/SESSION_STATE.md)). SESSION_STATE says optimal and adverse fall on one error-vs-CZ curve.
- **Garnet CDR** (n_train 40, 2048 shots), err_cdr / r² by CZ ([garnet_cdr_results.csv](/Users/karinaleskiewicz/QEM/garnet_cdr_results.csv)):

  | CZ | 12 | 36 | 57 | 96 |
  |---|---|---|---|---|
  | err_cdr | 0.021 | 0.099 | 0.043 | 0.125 |
  | r² | 0.99 | 0.95 | 0.85 | 0.69 |

  The crossover file names ZNE the winner at 12/36 CZ and CDR at 57/96 CZ, at effective shots 12,288 vs 83,968 ([garnet_crossover_summary.csv](/Users/karinaleskiewicz/QEM/garnet_crossover_summary.csv)).
- **Emerald em1** (2048 shots, 4 points, 1 window):

  | CZ | raw | CDR | ZNE | r² |
  |---|---|---|---|---|
  | 21 | 0.037 | 0.024 | 0.168 (ZNE harms) | 0.96 |
  | 63 | 0.101 | 0.070 | 0.077 | 0.96 |
  | 69 | 0.079 | 0.059 | 0.049 | 0.87 |
  | 114 | 0.101 | 0.279 (CDR collapses) | 0.139 | 0.68 |

  ([emerald_xtopo.csv](/Users/karinaleskiewicz/QEM/emerald_xtopo.csv))
- **Twirl pairs.** Garnet w1–w3 (1024 shots) give err ratio on/off 0.24–1.11 and Δr² −0.013 to +0.19. ODRA o1/o2 (8192 shots) give err ratio 0.13–0.82 and Δr² +0.01 to +0.31 ([twirl_pairs_all.csv](/Users/karinaleskiewicz/QEM/twirl_pairs_all.csv)).
- **Routing ladders.** The ODRA fixed-layout ladder 12/30/39/57 equals the Garnet and Emerald *optimal* ladders 12/27/39/57 only approximately; linear differs (27 vs 30). Adverse placements reach Garnet 42–102 and Emerald 78–135 CZ ([routing_ladder_*_optimal.csv / _adverse.csv](/Users/karinaleskiewicz/QEM/routing_ladder_garnet_adverse.csv)). Garnet placements: optimal [3,0,2,4,8], adverse [0,16,12,5,18] ([final_raport.tex l.370](/Users/karinaleskiewicz/QEM/final_raport.tex)).
- **Garnet [[4,2,2]] detection.** Optimal L1: error 0.418 → 0.223 at acceptance 0.75. Bare error at every rung is 0.42–0.98 and acceptance falls to 0.50–0.56 by 4 layers, so detection does not reach usefulness at these depths ([garnet_qec422_results.csv](/Users/karinaleskiewicz/QEM/garnet_qec422_results.csv)).
- **Garnet mirror survival.** Optimal: 0.78 (24 mirror CZ) → 0.28 (111). Adverse: 0.55 (48) → 0.27 (150) ([garnet_mirror_results.csv](/Users/karinaleskiewicz/QEM/garnet_mirror_results.csv)).
- **The final report's Emerald caveat:** a single window, no twirl, no simulated null possible at 54 qubits ([final_raport.tex l.770, 790](/Users/karinaleskiewicz/QEM/final_raport.tex)). There is also no Garnet noise calibration on disk; `calibrations/garnet.json` is topology-only ([legacy_nested_cal README](/Users/karinaleskiewicz/QEM/results_sim/legacy_nested_cal/README.md)).

### Inferences
- **The strongest cross-topology quantity is the CDR r²-vs-CZ curve,** available on all three devices:
  - ODRA p2_cdr100: 0.93/0.82/0.69/0.60 at 12/30/39/57
  - Garnet: 0.99/0.95/0.85/0.69 at 12/36/57/96
  - Emerald: 0.96/0.96/0.87/0.68 at 21/63/69/114

  This suggests the lattice devices tolerate about 1.5–2× more CZ before r² hits ≈0.7. It is a "where CDR stops paying" frontier per topology, but the n_train, shots and training-set types differ.
- **Error per CZ.** Garnet raw error grows ≈0.0016 per CZ from 12 to 96 on the optimal and adverse union. ODRA p2_cdr100 raw grows from 0.064 to 0.268 over 12 to 57 CZ, ≈0.0045 per CZ (computed from the files). The star topology pays more per routed CZ, consistent with SWAPs through the hub.
- **Combining the three devices** works best through a mixed model over the summary rows (device × CZ, error and r²), weighted by sd where banded files exist. Paired per-point tests are not possible.

### Gaps
- There are no Garnet or Emerald counts and no readout calibration, so the lattice devices cannot get any re-fit, REM, subsampling or per-point analysis.
- Emerald's eval-point indices are not stated in the CSV. Matching Emerald to the ODRA w01 point set 0 is not possible from the files. The final report says 4 points.

---

## Q5. Which offline re-analyses do the stored data allow (files, fields, what is missing)?

### Takeaway
The w01A/w01P5 counts (plus pilots) enable:
- readout correction from the raw calibration dumps;
- CDR re-fits at any thinned shot, frame or training budget, including ZNE's budget;
- frame-variance decomposition;
- twirl × n_CZ interaction models;
- r² diagnostics.

**Variable-noise CDR (vnCDR) is not possible:** no training circuit was ever folded or noise-scaled. Only targets were folded, and only in w01A (8 points), the pilots (4 points) and the 100-pt pilots.

### Cited Findings and per-analysis feasibility

1. **Readout-error mitigation (REM) for ZNE and CDR.**
   - **Enabling data:**
     - Every record stores the full 5-bit `counts` histogram, and mean-Z depends only on per-qubit marginals.
     - Each window has a raw calibration dump with per-qubit `single_shot_01_error` and `single_shot_10_error`. Keys verified in `odra_raw_w01A_start.json` (computed). Mapped `p_ro` is in `odra_*.json`.
     - Dumps exist for w01A start/end, w01P5 start/end and w01B start; the pilots use the 20261023 start/end and 2337 start/end dumps.
   - **Why it matters:** the reviewer found ZNE − ideal at 12 CZ has a constant positive sign (+0.010 to +0.076, mostly +0.04–0.05), attributed to readout plus T1 that folding does not scale. CDR absorbs it through its intercept b, so "ZNE vs CDR" without REM is not a fair method comparison ([recenzja C5](/Users/karinaleskiewicz/QEM/review/recenzja.md)).
   - **Missing / caveats:**
     - Pilot manifests have `calibration_set_id` null, so dump-to-pilot matching goes by timestamp.
     - The w01A start/end dumps are byte-identical, so they detect recalibration only, not drift ([recenzja C19](/Users/karinaleskiewicz/QEM/review/recenzja.md)).
     - The mid-block P5 recalibration is mis-tagged at record level ([weryfikacja F5/B1](/Users/karinaleskiewicz/QEM/review/weryfikacja.md)).
     - Clbit-to-wire indexing is physical-wire after routing. This is harmless for symmetric mean-Z, but **per-qubit REM must map wire → physical qubit QB1..QB5 correctly** ([weryfikacja B7](/Users/karinaleskiewicz/QEM/review/weryfikacja.md)).
     - Garnet has no readout calibration at all.

2. **CDR re-fit at ZNE's shot budget, by subsampling.**
   - **Enabling data:** w01A and w01P5 records with `role`, `train_index`, `repeat_index` (M=6 per circuit) and `ideal` (training and target), at S=8192 each. Arm budget is 1,032,192 shots per point vs ZNE genuine 24,576 ([weryfikacja §1](/Users/karinaleskiewicz/QEM/review/weryfikacja.md)).
   - **Method:** thin histograms without replacement (hypergeometric) and drop repeats or training circuits, e.g. n_train=20, M=1, S≈1170 ([recenzja §5.3 item 5](/Users/karinaleskiewicz/QEM/review/recenzja.md)). The spread arm already has 120 distinct training circuits × 1 repeat, so "many cheap training circuits" is directly subsampleable.
   - **Pilots p2_cdr100 / depth L6–L13:** 100 training circuits × 8192 shared over 100 points, 1 repeat. Thinning works, but ideals must be recomputed from `qasm3` because the records have no `ideal` field (computed).
   - **Missing:** thinning cannot create independent shots beyond the 8192 recorded per circuit; budgets above the recorded ones are impossible.

3. **Frame-variance and noise decomposition of twirled CDR.**
   - **Enabling data:** `frame` strings and `repeat_index` (w01A twirl_native/logical/spread), `copy_index` (pilots), M=6.
   - The reviewer reports two independent 6-frame sets for one target differ by RMS ≈0.008 (12 CZ) and 0.010 (39 CZ), 4–5× shot noise. This explains why twirling loses at 12 CZ ([recenzja C2](/Users/karinaleskiewicz/QEM/review/recenzja.md)).
   - `rebuild_from_frame` reproduces executed circuits exactly in 184/184 samples ([weryfikacja F1](/Users/karinaleskiewicz/QEM/review/weryfikacja.md)).

4. **Variable-noise CDR / noise-scaled CDR, combining ZNE-folded target data with Clifford training data.**
   - **What exists:** folded **targets** only.
     - w01A: genuine, identity and garbage at λ=3,5 for 8 points × 2 rungs; λ1 is genuine only; 112 ZNE records.
     - p2_cdr100: λ=3,5 for 100 points × 4 rungs, λ1 = CDR eval.
     - p2_depth L6/L9/L13: λ3,5 × 100 points.
     - Pilots p1–p3 logical: λ1,3,5 × 4 points.
     - κ runs: λ up to 7 × 4 points × 10 reps per budget.
     - (computed from role/scale tabulation)
   - **What is missing:** every CDR training record has scale 1 or no scale field; no training circuit was folded (computed). vnCDR (training at multiple λ) cannot be reconstructed.
   - **Offline substitutes:**
     - (a) "CDR-then-ZNE" or "ZNE-then-CDR" composites, applying the λ1 CDR map to folded targets. This assumes the map transfers to λ>1, which is untested.
     - (b) Cross-validated "learned extrapolation" on the 100-pt pilots. Targets have classically computable ideals (5 qubits), so a regression from (E1,E3,E5) to ideal can be fit leave-one-out. This is an oracle upper bound, not a deployable method.
     - (c) In simulation, the P7 device model (`sim/device_model.py`) can generate folded training circuits to prototype vnCDR before a hardware run.

5. **Twirl × n_CZ interaction models.**
   - **Data with counts:**
     - w01A: 12 and 39 CZ × 8 points × twirl_native vs off_copies, same training set type.
     - Pilots p1/p3: logical and native, 12 and 57 CZ.
     - Pilot p2: logical and native, 30 and 39 CZ.
     - w01B fragment: all_to_all twirl_native only, 3 points, no off arm.
   - **Summary-only:** o1/o2 (4 rungs × 2 windows) and Garnet w1–w3 (12/57/96 × 3 windows) in `twirl_pairs_all.csv`.
   - **Observed pattern:** w01A ratio on/off is 1.41 at star (twirl worse) and 0.68 at circular. The reviewer flags winner's curse versus pilot ratios 0.22–0.57 at 12 CZ ([weryfikacja §1](/Users/karinaleskiewicz/QEM/review/weryfikacja.md), [recenzja C13](/Users/karinaleskiewicz/QEM/review/recenzja.md)). The reviewer recommends log ε ~ arm × n_CZ + (1|point) + (1|rung) as an exploratory deviation ([recenzja §5.2–5.3](/Users/karinaleskiewicz/QEM/review/recenzja.md)).
   - **Caveat:** pilots use the shared training set and 4 points, and w01 arms are time blocks.

6. **r²-based analyses.**
   - **Data:** `r2` per point (w01A/P5 `cdr.csv`) and per rung (all other CDR files); `a` (slope) and `b` (intercept) are also stored.
   - **Findings:**
     - The largest consistent effect in w01A is twirling raising r²: +0.116 at 39 CZ (8/8 points), +0.017 at 12 CZ (7/8), Wilcoxon on 16 pairs p<0.001. It was not pre-registered ([recenzja §2.1 item 4](/Users/karinaleskiewicz/QEM/review/recenzja.md)).
     - ODRA r² excess over the nested null is −0.02/−0.19/−0.25/−0.28 ([r2_excess_over_null.csv](/Users/karinaleskiewicz/QEM/r2_excess_over_null.csv)).
     - The CDR slope `a` grows with CZ in the w01A off arm (1.22 at 12 CZ → 2.50 at 39), i.e. signal compression (computed).
   - **Possible re-analyses:** r² or slope as a cheap pre-run predictor of CDR breakdown across ODRA, Garnet and Emerald, and r² vs P5 insertion type (cz vs idle), using existing columns.

7. **ZNE diagnostics re-computation.**
   - **Data:** stored λ-resolved `ev_lam*`, `w_neg`, `snr_lmax`, `floor`, `floor_tracking` (w01A zne.csv, pilot `*_zne_points.csv`, wneg_null sims).
   - **Fixes the reviewer asks for:** SNR measured relative to the floor f≈0.02, not zero, and a statement that W_neg is necessary but not sufficient ([recenzja C4, B1](/Users/karinaleskiewicz/QEM/review/recenzja.md)). Both can be recomputed from counts.
   - The κ pilots allow re-estimating κ with bootstrap CIs per window: Neyman {1,3,5} gave 12.5 (p1) vs 20.7±14.7 (p3), and the archived k7 file gives 48 ([recenzja C11](/Users/karinaleskiewicz/QEM/review/recenzja.md)).

8. **Bootstrap CIs and a mixed model.** Clustered by point and rung, these are feasible from w01A/P5 per-point rows ([recenzja §5.3](/Users/karinaleskiewicz/QEM/review/recenzja.md)). Existing scripts: `analysis/rebuild_from_counts.py`, `analysis/annotate_twirl_counts.py`, `analysis/depth_regression.py`, `analysis/prereg_w01.py`, and the reviewer's `review/scripts/*` (recompute_w01A, p5_robust, power_h1, identity_anomaly).

### Inferences
- **For a combined DD + twirl + CDR method,** the repo can supply only the twirl + CDR leg on hardware (w01A, pilots, o1/o2, Garnet w1–w3). DD would have to be prototyped on the P7 simulator, which has a DD option for idle echo, and then measured.
- **For noise-scaled CDR,** the 100-pt pilots are the best data: they have both λ1,3,5 targets and a 100-circuit training set at λ1, with matched skeletons. A "training at λ=1 only" version of vnCDR, extrapolating the CDR correction along λ, can be tested there with ideals computed classically.
- **REM-corrected ZNE vs CDR at matched shots** is fully doable on w01A, star and circular only. Thinning the CDR budget to ZNE's 24,576 shots gives the paper's "shots-to-target" comparison without new runs. This is probably the single most valuable offline analysis for the "where QEM stops paying" claim.

### Gaps
- No folded training circuits, no DD data in P0+ runs, and no lattice counts.
- Whether the thinned estimates are unbiased for M<6 frames, given the frame-variance structure, needs checking in simulation.

---

## Q6. Which results are pilot/exploratory vs pre-registered?

### Takeaway
Only w01 (A, B, P5) is covered by the pre-analysis plan `preregistration.md`, frozen by tag `prereg-v1` at commit `ecaa139`. Everything else is exploratory: pilots, legacy ODRA, Garnet, Emerald and all sims. Even w01 is a pre-analysis plan, not pre-data: night A was already collecting.

### Cited Findings
- **Plan contents.** It registers H1 (twirl_native vs off_copies, near_target), H3 (native ≥ logical, shared_random), H6 (spread vs twirl_native), H7a (CZ at fixed duration) and H7b (duration at fixed gates), with Holm across the five. Primary metric: |⟨O⟩_mit − O_ideal|, OLS. Secondary: H4 (ZNE window: W_neg ≤ 0.02, SNR ≥ 2) and H5 (McNemar). It states that the pilots p1–p3 "were analysed and inform the hypotheses … they are exploratory" ([preregistration.md](/Users/karinaleskiewicz/QEM/preregistration.md)). Tag `prereg-v1` → `ecaa139` (computed via `git tag`/`git log`).
- **Honesty note:** night A started before the plan file existed. The first part of night A ran on dirty commit `4b0d849`, the resume on `ecaa139` ([preregistration.md](/Users/karinaleskiewicz/QEM/preregistration.md); [recenzja C17, B10](/Users/karinaleskiewicz/QEM/review/recenzja.md)).
- **Reviewer's run on A+P5 only,** 16 pairs instead of 32 because night B is missing:
  - H1 p=0.353, H3 p=0.851, H6 p=0.550, H7a p=0.660, H7b p≈0;
  - only H7b is rejected after Holm;
  - H4 "pays" is false on both rungs.
  - ([weryfikacja F3](/Users/karinaleskiewicz/QEM/review/weryfikacja.md))
- **Deviations in code vs plan:**
  - H7 uses one-sided p while the plan says two-sided;
  - there is no completeness assertion;
  - the P5 cluster-robust SE with 8 clusters is anti-conservative.
  - ([weryfikacja B2–B4, F4](/Users/karinaleskiewicz/QEM/review/weryfikacja.md))
- **Power:** the estimated power for H1 after night B is 0–17% ([weryfikacja F8](/Users/karinaleskiewicz/QEM/review/weryfikacja.md)).
- **The final report's "pre-registered prediction" of the ZNE break-even** (6/7 cases) belongs to Month-2 Garnet/Emerald work and predates `prereg-v1` ([final_raport.tex l.1152–1180](/Users/karinaleskiewicz/QEM/final_raport.tex)). It is not part of the frozen plan.

### Inferences
- In the paper, confirmatory claims should be limited to H7b and to whatever night B adds. All the cross-topology, DD, twirl-r², κ and ZNE-boundary material should be labelled exploratory or descriptive.
- The r² twirl effect, the most robust signal, is exploratory. It can be raised to a stated deviation or exploratory analysis registered before night B is analysed, as the reviewer suggests.

### Gaps
- Night B completion status beyond 2026-10-25 19:18 local (log end) is unknown. Whether H1/H3/H6 will ever have 32 pairs depends on it.
