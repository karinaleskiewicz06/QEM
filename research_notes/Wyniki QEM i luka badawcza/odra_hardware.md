# ODRA 5 (star) hardware campaign — inventory of results (state 2026-11-09 ~17:00)

Scope: windows w01A, w01B, w01P5, w02vn, w03dd (running), w04m in `runs/odra_campaign/`, IQM ODRA 5
(star, hub QB3), frozen L3 classifiers from `trained_models_hard`, observable mean-Z over 5 qubits,
error ε = |⟨O⟩ − O_ideal|. Numbers marked **[recomputed]** were produced by me read-only
(`python -m analysis.prereg_w01 --out <scratch>`, `python -m analysis.depth_regression ... --out <scratch>`,
small pandas snippets on the committed/uncommitted CSVs); no repo file was changed except this note.
Night B (w01B) finished today 15:49 local, so the pre-registered w01 family is being reported here for the
first time on the complete 32-pair data set; the repo's own `paper_analysis/out/summary.md` used
preliminary night-B rows.

## Q1. Windows: what each measured, design, status, pre-registration

### Takeaway
Six ODRA windows exist; three pre-registrations were frozen by git tags (prereg-v1 for w01A/B/P5,
prereg-vn1 for w02vn, prereg-dd1 for w03dd). w04m and all `paper_analysis/` offline analyses are
exploratory. w03dd is still running (incomplete, no conclusions).

### Cited Findings
- Git tags: `prereg-v1` → commit ecaa139 (2026-10-24 10:38 +0200), `prereg-vn1` → c2f87f6 (2026-11-04 23:12 +0100), `prereg-dd1` → 56370c8 (2026-11-09 08:35 +0100). No tag for w04m. — [git tag -l / git log](/Users/karinaleskiewicz/QEM/.git)
- prereg-v1 is honestly labelled a *pre-analysis* plan, not pre-data: night A started 09:56 local 2026-10-24, before the file existed; no w01 error/test had been computed. Pilot windows p1–p3 (2026-10-23/24) were analysed and are exploratory. — [preregistration.md](/Users/karinaleskiewicz/QEM/preregistration.md)
- w01 design: 8 eval points per window (2 per quartile of |O_ideal|, point set 0), n_train 20 (spread 120), M = 6 frames/copies, S = 8192, equal budget (n_train+1)·M·S per point and arm (= 1,032,192 shots per point for CDR), block-randomised; CDR arms off_copies:near_target, twirl_native:near_target, spread:near_target, twirl_logical:shared_random, twirl_native:shared_random; ZNE scales {1,3,5}, Richardson, folding genuine/identity/garbage. Shots/point: raw 8,192, ZNE 24,576, CDR 1,032,192. — [preregistration.md](/Users/karinaleskiewicz/QEM/preregistration.md); [slide_numbers.txt](/Users/karinaleskiewicz/QEM/runs/odra_campaign/slide_numbers.txt)
- **w01A (night A)**: rungs star (12 CZ) and circular (39 CZ); manifest started 2026-10-24T19:31Z, finished 20:39Z (last attempt), single calibration set b1b5d2a8 start = end. Independent review notes night A actually ran 12.3 h (08:19–20:39 UTC) with a resume, so each arm of a rung is one block at a different time. — [w01A/manifest.json](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01A/manifest.json); [review/weryfikacja.md](/Users/karinaleskiewicz/QEM/review/weryfikacja.md) (F-section on night A)
- **w01B (night B)**: rungs linear (30 CZ) and all_to_all (57 CZ), 12 blocks, 10,192 circuits, 83.5 M shots. First attempt 2026-10-25 aborted (kept aside in `w01B_aborted_20261103/`); the analysed run executed 2026-11-09 01:37–15:49 local in several attempts (FAIL at 12:07 on a missing measurement_counts artifact, resumed; interrupted by w04m; 9,128 circuits already recorded at final resume), DONE 15:49:09. — [w01B.log](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01B.log); [queue.log](/Users/karinaleskiewicz/QEM/runs/odra_campaign/queue.log)
- w01B blocks span **two calibration sets**: 36b9e58f (all_to_all spread/twirl_logical/twirl_native, linear off_copies/spread) and d13a40e8 (all_to_all off_copies, linear twirl_logical/twirl_native). Hence the H1 pair (twirl_native vs off_copies) crosses calibration sets in both night-B rungs. **[recomputed from w01B/cdr.csv calibration_set_id]** — [w01B/cdr.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01B/cdr.csv)
- **w01P5 (P5 night)**: star L3 12 CZ; star + 6/12/20 CZ·CZ identity pairs (24/36/52 CZ, PRX fixed at 20); star + matched idle (12 CZ, same scheduled durations 1.52/2.24/3.20 µs vs 0.80 µs base); star L6/L9/L13 (24/36/52 CZ, PRX 35/50/70, different trained classifiers). off_copies:near_target only, no ZNE. Calibration changed during block star_cz52 (b1b5d2a8 → 0642097d). — [w01P5/manifest.json](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01P5/manifest.json); [w01P5/cdr.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01P5/cdr.csv)
- **w02vn**: 2-axis variable-noise CDR on star L3, 8 points, n_train 20, levels base / +12 CZ·CZ pairs (36 CZ) / +matched idle, M = 6 at every level, S = 32,768 → 4.1 M shots per point per method; levels interleaved within jobs. Ran 2026-11-08T14:31Z–11-09T00:37Z, single calibration set 36b9e58f; one earlier abort (2026-11-05). — [preregistration_w02_vncdr.md](/Users/karinaleskiewicz/QEM/preregistration_w02_vncdr.md); [w02vn/manifest.json](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w02vn/manifest.json)
- **w03dd**: CDR with vs without IQM server-side DD (STANDARD_DD_STRATEGY), star L3 + circular L3, 8 points each, M = 6, S = 8192, arms interleaved copy by copy; primary H_dd two-sided Wilcoxon on 16 pairs. Started 2026-11-09T14:49Z, no finished_utc; counts.jsonl had 1,197 records at 16:57 (design ≈ 16 blocks × 2 arms × 6 copies × 21 circuits = 4,032) → **in progress, ~30 %; no result.** — [preregistration_w03_dd.md](/Users/karinaleskiewicz/QEM/preregistration_w03_dd.md); [w03dd/manifest.json](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w03dd/manifest.json); [w03dd.log](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w03dd.log)
- **w04m**: raw decisions only, all 100 points of the frozen reference set, 13 rungs (star/linear/circular/all_to_all L3; star L6/L9/L13; star+CZ pairs 24/36/52; star+idle 24/36/52), M = 2, S = 8192, plus readout references |00000⟩ and |11111⟩ (4 copies each). Ran 2026-11-09 08:19–12:46Z, calibration d13a40e8 start = end. Not pre-registered. — [campaign/margin_odra_window.py docstring](/Users/karinaleskiewicz/QEM/campaign/margin_odra_window.py); [w04m/manifest.json](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w04m/manifest.json)

### Inferences
- Confirmatory = H1, H3, H6, H7a, H7b (Holm family of 5), with H4/H5 as pre-registered *secondary*; H_vn (only confirmatory test of w02vn); H_dd (only confirmatory test of w03dd, pending). Everything else is exploratory.
- prereg §3 says a sensitivity analysis should drop rungs with a calibration change; for night B that is both rungs (cross-block calibration change), leaving only night A. No such sensitivity output exists yet.

### Gaps
- `results/prereg_w01_*.csv` (the official confirmatory output path) does not exist in the repo; the w01 numbers below are my read-only rerun of the frozen script into a scratch dir.
- Exact wall-clock span of the night-B blocks measured before 01:37 Nov 9 (if any) is not in the manifest (only last attempt timestamps).

## Q2. Pre-registered w01 family (H1, H3, H6, H7a, H7b) — full 32-pair result

### Takeaway
Only **H7b (duration raises raw error) is supported**; H1 (twirling lowers CDR error) is
directionally favourable but not significant (Holm p = 0.37); H3, H6, H7a are not supported.

### Cited Findings (all **[recomputed]**, `analysis/prereg_w01.py` frozen at prereg-v1, run on w01A+w01B+w01P5)
- **H1** twirl_native:near_target vs off_copies:near_target: n = 32 pairs, twirl better in 20/32, one-sided Wilcoxon p = 0.0919, Holm p = 0.3676, geo ratio 0.745 [95 % bootstrap CI 0.484, 1.140] → **NOT SUPPORTED (null)**. Per-rung geo ratios: star 1.41, linear 0.931, circular 0.683, all_to_all 0.344. — [analysis/prereg_w01.py](/Users/karinaleskiewicz/QEM/analysis/prereg_w01.py); consistent with [slide_numbers.txt](/Users/karinaleskiewicz/QEM/runs/odra_campaign/slide_numbers.txt) ("20 z 32 par, Wilcoxon p = 0.092, test znaków p = 0.108, iloraz 0.75")
- Slide per-rung H1 (mean err CDR off vs CDR+twirl, wins, ratio, one-sided p): 12 CZ 0.022 vs 0.015, 4/8, 1.41, p 0.770; 30 CZ 0.076 vs 0.053, 4/8, 0.93, p 0.422; 39 CZ 0.053 vs 0.040, 7/8, 0.68, p 0.074; 57 CZ 0.152 vs 0.053, 5/8, 0.34, p 0.074. — [slide_numbers.txt](/Users/karinaleskiewicz/QEM/runs/odra_campaign/slide_numbers.txt)
- Night A only (16 pairs, computed before night B existed): H1 p = 0.353, ratio 0.981. — [review/weryfikacja.md](/Users/karinaleskiewicz/QEM/review/weryfikacja.md)
- **H3** native vs logical twirl (shared_random): 13/32 native better, p = 0.865, Holm 1.0, geo 1.237 [0.834, 1.831] → **NOT SUPPORTED** (if anything logical twirl lower: per-rung means logical/native 0.019/0.031, 0.029/0.036, 0.025/0.032, 0.082/0.088 at 12/30/39/57 CZ). — [slide_numbers.txt](/Users/karinaleskiewicz/QEM/runs/odra_campaign/slide_numbers.txt)
- Caveat on H3: training-circuit ideals were nearly identical across points (same seed per point; 135–140/140 equal, values 0, ±0.2), so H3 pairs are not independent. — [review/weryfikacja.md](/Users/karinaleskiewicz/QEM/review/weryfikacja.md)
- **H6** spread vs twirl_native (near_target): 15/32, p = 0.750, Holm 1.0, geo 1.171 [0.715, 1.899] → **NOT SUPPORTED**. Per rung: star 0.710, linear 0.533, circular 1.751, all_to_all 2.841 (spread loses at deep rungs).
- **H7a** (more CZ at fixed duration raises raw error; P5, L3 rungs, point FE, clustered SE, n = 56): factor per 10 CZ 0.955 [0.770, 1.186], one-sided p = 0.660, Holm 1.0 → **NOT SUPPORTED (null)**.
- **H7b** (longer duration at fixed gates raises raw error): factor 1.434 per µs [1.300, 1.581], p = 2.6e-13, Holm 1.3e-12 → **SUPPORTED (positive)**. — [analysis/depth_regression.py](/Users/karinaleskiewicz/QEM/analysis/depth_regression.py)
- Deviation flagged by review: the code uses one-sided p/2 for H7a/H7b while the plan says two-sided (anti-conservative ×2); H7b survives either way; under wild bootstrap with G = 8 clusters Holm×5 gives ≈ 0.05 (borderline); calibration change during star_cz52 makes the cz24-vs-idle24 contrast confounded, but old-calibration-only data still give dur 1.478/µs (p = 0.002), cz10(raw) 1.029 (p = 0.87). — [review/weryfikacja.md](/Users/karinaleskiewicz/QEM/review/weryfikacja.md) (B2, F5)
- Review's power estimate for H1 after night B: ≈0 % (B like 12 CZ) to ≈16–17 % (B like 39 CZ); H1 effectively needed p < 0.0125 because H7b takes the first Holm step. — [review/weryfikacja.md](/Users/karinaleskiewicz/QEM/review/weryfikacja.md) (F8)

### Inferences
- The H1 null is a power/heterogeneity result rather than evidence of no effect: twirling helps at 39 and 57 CZ (ratios 0.68, 0.34) and hurts at 12 CZ (1.41). The strongest per-rung gain (all_to_all 0.344) compares blocks measured under different calibration sets (twirl_native 36b9e58f vs off_copies d13a40e8), so it is partly confounded with drift.

### Gaps
- No pre-registered sensitivity analysis (dropping calibration-changed rungs) has been produced for night B.

## Q3. Pre-registered secondary: H4 (ZNE window) and H5 (decisions); ZNE vs garbage

### Takeaway
H4 "ZNE pays" is **false at all four rungs**. Genuine ZNE beats garbage folding clearly only at
12 CZ; at 39 and 57 CZ garbage folding is as good or better → the ZNE "gain" there is an artefact
of folding-induced extrapolation, not mitigation. The pilot-based prediction "pays at 12 CZ, not at 57" was half wrong (fails at 12 too, on criterion (i)).

### Cited Findings ([recomputed] via prereg_w01.zne_window; raw here = λ1 ZNE circuit, 8192 shots)
| rung | CZ | raw | ZNE genuine | ZNE garbage | p(ZNE<raw) | median W_neg | median SNR λ5 | pays |
|---|---|---|---|---|---|---|---|---|
| star | 12 | 0.0690 | 0.0452 | 0.1373 | 0.4727 | 0.0045 | 23.36 | False |
| linear | 30 | 0.1094 | 0.0643 | 0.0676 | 0.0977 | 0.0007 | 14.41 | False |
| circular | 39 | 0.1584 | 0.1115 | 0.1028 | 0.0039 | 0.0000 | 4.09 | False |
| all_to_all | 57 | 0.2224 | 0.1701 | 0.1613 | 0.1562 | 0.0000 | 7.34 | False |
— [analysis/prereg_w01.py](/Users/karinaleskiewicz/QEM/analysis/prereg_w01.py); [w01A/zne.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01A/zne.csv); [w01B/zne.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01B/zne.csv)
- Slide version (raw = CDR-table raw): raw 0.074/0.110/0.161/0.223; ZNE 0.045/0.064/0.112/0.170; garbage 0.137/0.068/0.103/0.161; ZNE<garbage one-sided p 0.012 (12 CZ), 0.371 (30), 0.844 (39), 0.988 (57); ZNE<raw p 0.473/0.098/0.004/0.156; "H4 niespełnione" at every rung. — [slide_numbers.txt](/Users/karinaleskiewicz/QEM/runs/odra_campaign/slide_numbers.txt)
- Identity folding is worse than raw: 0.1657 (30 CZ), 0.3194 (57 CZ); W_neg identity 0.0368/0.0905. — [w01B.log](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01B.log)
- Review caveat: "ZNE<raw" compares 24,576-shot ZNE with an 8,192-shot λ1 raw; "ZNE<garbage" in H4 is a comparison of means without a test. — [review/weryfikacja.md](/Users/karinaleskiewicz/QEM/review/weryfikacja.md) (B8)
- **H5** (McNemar raw vs twirl_native:near_target, 32 pairs): raw agrees with ideal decision 0.906, mitigated 0.969; 0 broken, 2 fixed, exact p = 0.5; both changes below median margin → **NOT SIGNIFICANT** (margin structure consistent, tiny n). [recomputed]

### Inferences
- ZNE positive only in a narrow sense at 12 CZ (beats garbage, p = 0.012) but does not significantly beat raw there; deeper rungs show ZNE ≈ garbage = negative/artefact.

### Gaps
- None beyond n = 8 per rung.

## Q4. CDR vs raw, spread, readout — exploratory but strong positives

### Takeaway
Every CDR arm reduces error vs raw strongly when pooled (exploratory, not in the confirmatory
family): CDR+twirl 27/32 wins, geo 0.284, p = 1.6e-5. The gain with twirling holds at 57 CZ (0.053 vs raw 0.223) while untwirled CDR degrades (0.152).

### Cited Findings
- Slide table (mean error, 8 pts each): raw 0.074/0.110/0.161/0.223; CDR+twirl 0.015/0.053/0.040/0.053; spread 0.012/0.056/0.068/0.137 at 12/30/39/57 CZ. — [slide_numbers.txt](/Users/karinaleskiewicz/QEM/runs/odra_campaign/slide_numbers.txt)
- [recomputed, one-sided Wilcoxon on log ε vs own raw, OLS]: twirl_native:near_target pooled 27/32, geo 0.284, p = 1.6e-5 (per rung p 0.027/0.012/0.020/0.074); off_copies pooled 24/32, geo 0.375, p = 8.9e-5 (per rung 0.039/0.020/0.008/0.273, 57 CZ n.s.); spread pooled 30/32, geo 0.338, p = 2.6e-6 (57 CZ p = 0.098). — [w01A/cdr.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01A/cdr.csv), [w01B/cdr.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01B/cdr.csv)
- Night-B CDR means: linear off 0.0756, spread 0.0564, twirl_logical 0.0287, twirl_native near 0.0532, twirl_native shared 0.0359; all_to_all 0.1518/0.1368/0.0821/0.0529/0.0883; raw 0.1246 (linear), 0.2281 (all_to_all). — [w01B.log](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01B.log)
- Offline (exploratory, used preliminary night B): CDR is limited by number of training circuits not shots (copies 1→6: CDR/raw 0.385→0.381; n_train 5→10→20: 0.57→0.43→0.38); untwirled CDR gain ~5× at 12 CZ, 1.1–1.6× at 52 CZ, ×0.73 per +10 CZ; LOO error is a calibrated error bar (true ≤ LOO-rms in 71 %, ≤ 2·LOO in 91 %; ρ = 0.43 per point, p = 1e-7); sim↔hw ⟨O⟩ r ≈ 0.99, device model gets raw error right (×1.1) but underestimates post-CDR error ×1.9. — [paper_analysis/out/summary.md](/Users/karinaleskiewicz/QEM/paper_analysis/out/summary.md)

### Inferences
- The robust positive is "CDR (any arm) ≫ raw at 1 M shots/point", ~3–4× error reduction, at a ~126× shot cost vs raw (1,032,192 vs 8,192).

### Gaps
- `paper_analysis` outputs were generated with partial night B and must be rerun (summary.md says so).

## Q5. P5: CZ vs idle insertion (w01P5)

### Takeaway
At matched duration, inserting CZ pairs vs idle does **not** raise the *raw* error (H7a null),
but it does raise the *CDR* error (exploratory) and shrinks the signal more (w04m slopes).

### Cited Findings
- Mean errors (OLS, 8 pts): star 12 CZ raw 0.0672 / CDR 0.0209; cz24 0.0938/0.0220; cz36 0.1588/0.0723; cz52 0.1765/0.0741; idle24 0.0899/0.0139; idle36 0.1121/0.0313; idle52 0.1467/0.0374; L6 0.1156/0.0367; L9 0.2266/0.1348; L13 0.2511/0.1847. [recomputed] — [w01P5/cdr.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w01P5/cdr.csv)
- [recomputed, exploratory, two-sided Wilcoxon on log ε] CZ vs matched idle, pooled 24 pairs: raw geo 0.891, CZ worse 18/24, p = 0.29 (null); CDR geo 2.40, CZ worse 19/24, p = 0.00074. Per level CDR: 24: 2.11 (p 0.31), 36: 2.82 (8/8, p 0.0078), 52: 2.33 (p 0.11).
- Depth regression, CDR outcome (secondary): cz10 factor 1.339 [p = 0.002], dur 1.32/µs (p = 0.31) on L3 rungs; review notes CDR cz10 does not survive Holm m = 5 and is not primary. — [depth_regression.py](/Users/karinaleskiewicz/QEM/analysis/depth_regression.py); [review/weryfikacja.md](/Users/karinaleskiewicz/QEM/review/weryfikacja.md)
- Offline: excess hw−sim CDR error 0.037 (+CZ) vs 0.006 (+idle), paired Wilcoxon p = 0.0003 (exploratory). — [paper_analysis/out/summary.md](/Users/karinaleskiewicz/QEM/paper_analysis/out/summary.md)
- P5 vnCDR (exploratory, from P5 night): k = 36, 2 axes, geo 1.12, 2/8 — not better than CDR; levels measured hours apart. — [preregistration_w02_vncdr.md](/Users/karinaleskiewicz/QEM/preregistration_w02_vncdr.md)

### Inferences
- Raw error on ODRA is driven by duration (idle decoherence, H7b), while the residual CDR cannot remove is tied to CZ gates (consistent with twirling helping at deep rungs). This is exploratory and partly confounded by the mid-night calibration change (cz24 block).

## Q6. w02vn — vnCDR (H_vn)

### Takeaway
**NEGATIVE, pre-registered**: 2-axis vnCDR is not better than CDR at equal budget on hardware.

### Cited Findings
- 8 complete points, none excluded. PRIMARY H_vn: vnCDR wins 4/8, mean error 0.0172 vs CDR 0.0145, geo ratio 1.212 [0.432, 3.430], one-sided Wilcoxon p = 0.6289 → NOT SUPPORTED. — [w02vn/vncdr_summary.txt](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w02vn/vncdr_summary.txt)
- Secondary variants vs CDR: geo ratios 0.850–1.219, p 0.42–0.63, none significant (e.g. vn_t 1.051 p 0.47; vn_cz_noint 0.850 p 0.42; vn_2ax_fullbudget 1.005 p 0.53). Raw vs CDR: raw wins 2/8, geo 3.514 [1.384, 9.595] (CDR ~3.5× better than raw). — same file
- Pre-registered power was 0.84 (no coherent error) / 1.00 (coherent ZZ θ = 0.05) in simulation at 4.1 M shots, 8 points; sim rehearsals with other seeds did not reach significance. In simulation 2-axis vnCDR beat CDR (geo 0.52, 6/8, p = 0.055); sim CDR error 0.007 ≈ 2× below hardware. — [preregistration_w02_vncdr.md](/Users/karinaleskiewicz/QEM/preregistration_w02_vncdr.md); [paper_analysis/out/summary.md](/Users/karinaleskiewicz/QEM/paper_analysis/out/summary.md)

### Inferences
- Sim-predicted vnCDR gain does not transfer; a clean null with single stable calibration set (36b9e58f start = end) and interleaved levels — the P5 confound (levels hours apart) was removed and the result is still null.

## Q7. w04m — decision flips vs margin, readout offsets (exploratory)

### Takeaway
Noise mostly contracts ⟨O⟩ toward 0 (slope 0.85 at 12 CZ → 0.24 at 57 CZ) with a small positive
readout offset (+0.032); decision flips are confined to low-margin points, but they reach |O_ideal| up
to ~0.30, i.e. far beyond the readout offset — so "flips only where |O_ideal| < readout shift" is not
supported; contraction + shot noise matters. Raw accuracy vs labels is unchanged (0.7115 ideal vs 0.72 raw pooled).

### Cited Findings
- Readout references: ⟨Z⟩|00000⟩ = 0.9888, ⟨Z⟩|11111⟩ = −0.9256; offset +0.0316; contraction 0.9572. — [w04m/margin_summary.txt](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w04m/margin_summary.txt)
- Per rung (CZ, acc ideal, acc raw, agree, flips/100, slope, offset, max |ideal| flipped): star 12 0.70/0.72/0.98/2/0.845/+0.0020/0.033; linear 30 0.69/0.73/0.88/12/0.514/+0.0562/0.112; circular 39 0.65/0.74/0.87/13/0.304/+0.0295/0.093; all_to_all 57 0.75/0.69/0.92/8/0.240/+0.0343/0.101; star_L6 24 0.67/0.68/0.93/7/0.548/+0.0109/0.145; star_L9 36 0.77/0.76/0.91/9/0.486/+0.0199/0.149; star_L13 52 0.82/0.80/0.96/4/0.312/+0.0501/0.060; star_cz24 0.70/0.73/0.95/5/0.673/+0.0012/0.098; star_cz36 0.70/0.72/0.92/8/0.561/−0.0096/0.197; star_cz52 0.70/0.71/0.89/11/0.420/−0.0256/0.298; star_idle24 0.70/0.70/0.98/2/0.746/−0.0018/0.097; star_idle36 0.70/0.70/0.96/4/0.641/−0.0091/0.097; star_idle52 0.70/0.68/0.94/6/0.532/−0.0015/0.191. — [w04m/margin_summary.txt](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w04m/margin_summary.txt)
- [recomputed from margin.csv, 1,300 rung-points]: 91 flips (7.0 %), 37 distinct points; flips by |O_ideal|: ≤0.0316: 29/97; 0.0316–0.05: 14/39; 0.05–0.1: 35/133; 0.1–0.2: 12/177; >0.2: 1/854. All 91 flips below the pooled median |O_ideal|; by pooled quartile Q1 80/330, Q2 11/320, Q3 0, Q4 0. Flip direction balanced (ideal −1: 48, +1: 43). — [w04m/margin.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w04m/margin.csv)
- Matched-duration contrast of contraction slopes: cz24/36/52 0.673/0.561/0.420 vs idle24/36/52 0.746/0.641/0.532; flips 5/8/11 vs 2/4/6. — same file (descriptive, no test)
- Earlier 8-point offline result: raw gives the ideal decision in 92 %; above-median-margin points agree 100 %; CDR breaks 7, fixes 3 (McNemar p = 0.34); CDR+twirl and ZNE fix 2, break 0 (n = 16, p = 0.5). — [paper_analysis/out/summary.md](/Users/karinaleskiewicz/QEM/paper_analysis/out/summary.md)

### Inferences
- POSITIVE (descriptive): "mitigation fixes the number, not the decision" holds on 100 points — decisions are robust above |O_ideal| ≈ 0.2. NEGATIVE for the specific mechanism "flips only below readout offset".
- Pooled quartiles mix different classifiers (L6/L9/L13 have their own ideals), so the quartile split is approximate.

### Gaps
- No pre-registration and no formal test of the margin mechanism exists for w04m.

## Q8. POSITIVE vs NEGATIVE/NULL classification

### Takeaway
Pre-registered confirmatory: 1 positive (H7b), 5 null/negative (H1, H3, H6, H7a, H_vn); H_dd pending.
Pre-registered secondary: H4 negative at all 4 rungs, H5 null. Strong exploratory positives: CDR ≫ raw; twirling preserves CDR gain at 39/57 CZ; LOO error bar calibrated; CDR residual tied to CZ.

### Cited Findings
| result | status | stat / n / p | prereg? | source |
|---|---|---|---|---|
| H7b duration ↑ raw error | **POSITIVE** | ×1.434/µs, n=56, Holm p=1.3e-12 (borderline ≈0.05 under wild bootstrap) | yes (v1, primary) | [depth_regression.py](/Users/karinaleskiewicz/QEM/analysis/depth_regression.py), [weryfikacja.md](/Users/karinaleskiewicz/QEM/review/weryfikacja.md) |
| H1 twirl lowers CDR error | NULL (directional) | 20/32, geo 0.745 [0.48,1.14], p=0.092, Holm 0.368 | yes (primary) | [slide_numbers.txt](/Users/karinaleskiewicz/QEM/runs/odra_campaign/slide_numbers.txt) |
| H3 native ≥ logical twirl | NEGATIVE/NULL | 13/32, geo 1.237, p=0.865 | yes (primary) | [prereg_w01.py](/Users/karinaleskiewicz/QEM/analysis/prereg_w01.py) |
| H6 spread beats twirl CDR | NULL | 15/32, geo 1.171, p=0.750 | yes (primary) | idem |
| H7a CZ ↑ raw error at fixed duration | NULL | ×0.955/10 CZ, p=0.660 | yes (primary) | idem |
| H4 ZNE pays | NEGATIVE (all 4 rungs); artefact (ZNE≈garbage) at 30/39/57 CZ | see Q3 table | yes (secondary) | idem |
| H5 decisions McNemar | NULL | 0 vs 2, p=0.5, n=32 | yes (secondary) | idem |
| H_vn vnCDR < CDR | NEGATIVE | 4/8, geo 1.212 [0.43,3.43], p=0.629 | yes (prereg-vn1) | [vncdr_summary.txt](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w02vn/vncdr_summary.txt) |
| H_dd DD changes CDR error | IN PROGRESS | ~1,197/≈4,032 circuits | yes (prereg-dd1) | [w03dd/](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w03dd/manifest.json) |
| CDR (any arm) < raw | POSITIVE | twirl 27/32 geo 0.284 p=1.6e-5; spread 30/32 p=2.6e-6 | no | [recomputed] |
| CZ vs idle: CDR residual | POSITIVE (exploratory) | geo 2.40, 19/24, p=0.00074 | no | [recomputed] |
| Decisions robust above margin | POSITIVE (descriptive) | 91/1300 flips, 0 in upper half | no | [margin.csv](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w04m/margin.csv) |
| Flips limited to |O_ideal| < readout offset | NEGATIVE | flips up to 0.298 vs offset 0.032 | no | [margin_summary.txt](/Users/karinaleskiewicz/QEM/runs/odra_campaign/w04m/margin_summary.txt) |

### Gaps
- H2 (stability across calibration windows) and κ/Neyman allocation were explicitly not tested in w01. — [preregistration.md](/Users/karinaleskiewicz/QEM/preregistration.md)
- Single window per rung; drift variance is inside every pair (Wilcoxon assumes independence). — [review/weryfikacja.md](/Users/karinaleskiewicz/QEM/review/weryfikacja.md)
