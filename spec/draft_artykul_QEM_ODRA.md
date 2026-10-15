# Shot-matched Pauli twirling as a precondition for Clifford data regression, and the finite-shot window of zero-noise extrapolation, on a 5-qubit star superconducting processor

*Draft v0.1 — Karina Leśkiewicz (KN Axion) — target: IEEE QCE 2027 (full paper), extended version IEEE TQE.*
*Numbers marked [EXISTING] come from the repository CSVs (commit 81e0f97). Numbers marked [TODO-ODRA] / [TODO-SIM] are placeholders for the pre-registered campaign.*

## Abstract

Error-mitigation methods are usually compared on expectation-value accuracy at whatever shot budget each method happens to use. This hides two effects: averaging gains that come from extra shots alone, and regime boundaries beyond which a method stops paying for its overhead. We evaluate raw estimation, digital zero-noise extrapolation (ZNE), Clifford data regression (CDR), and CDR with Pauli twirling on a frozen five-qubit variational classifier. The workload is compiled along a routing ladder from 12 to 54 CZ gates on the IQM ODRA 5 star-topology processor, with replication on IQM Garnet. With the total shot budget held equal across arms, logical-level twirling lowered the CDR error in 16 of 17 hardware pairs (sign test p = 2.7·10⁻⁴; geometric-mean error ratio 0.42 on ODRA and 0.59 on Garnet). An incoherent-only simulation shows only a weak effect (ratio 0.86), whereas injecting a coherent CZ phase reproduces the hardware gain (0.33) [EXISTING]. In a pre-registered campaign over [TODO-ODRA: 12] calibration windows we find [TODO-ODRA: effect by CZ, drift variance ratio, native-vs-logical twirl]. For ZNE, the finite-shot help–harm intercept follows a constant κ that depends only on the extrapolation nodes. We confirm this for three node sets on two devices (e.g. κ{1,3,5} = 14.4 ± 0.9 measured vs 14.66 predicted) and test the reduced constant under Neyman shot allocation [TODO-ODRA]. A matched-cost garbage-folding control bounds the upper edge of the ZNE window [TODO-ODRA]. Finally, we show that expectation-value gains translate into decision changes of the classifier only near the decision margin [TODO-ODRA]. Together these yield a regime map, raw → ZNE → twirled CDR, whose boundaries are predicted before the main run.

## 1 Introduction

Quantum error mitigation (QEM) trades additional circuit executions for reduced bias in estimated observables ([Temme et al. 2017](https://doi.org/10.1103/physrevlett.119.180509); [Cai et al. 2023](https://doi.org/10.1103/revmodphys.95.045005)). The trade is not free. Sampling-cost lower bounds grow exponentially with circuit size ([Takagi et al. 2022](https://doi.org/10.1038/s41534-022-00618-z); [Quek et al. 2024](https://doi.org/10.1038/s41567-024-02536-7)), and at a fixed budget the variance penalty can outweigh the bias reduction ([Scavino Alfaro 2026](https://arxiv.org/abs/2605.08251)). A useful comparison of mitigation methods therefore has to fix the budget, not only the circuit.

Learning-based mitigation is attractive because its training circuits are classically simulable. Clifford data regression (CDR) fits a linear map from noisy to ideal values on near-Clifford training circuits ([Czarnik et al. 2021](https://doi.org/10.22331/q-2021-11-26-592)), and its variants combine training with noise scaling ([Lowe et al. 2021](https://doi.org/10.1103/physrevresearch.3.033098); [Bultrini et al. 2023](https://doi.org/10.22331/q-2023-06-06-1034)). The linear ansatz is exact for global depolarizing noise but not for coherent errors, which do not commute with the circuit and differ between training and target circuits. Pauli twirling and randomized compiling convert coherent errors into stochastic Pauli channels ([Wallman & Emerson 2016](https://doi.org/10.1103/physreva.94.052325); [Hashim et al. 2021](https://doi.org/10.1103/physrevx.11.041039)). Their combination with extrapolation has been studied numerically ([Kurita et al. 2023](https://doi.org/10.22331/q-2023-11-20-1184)). Twirled circuits are, however, averaged over M random instances. If the untwirled baseline uses M times fewer shots, any gain may simply reflect averaging. To our knowledge, no hardware study has measured the effect of twirling on CDR under a shot-matched control.

A second gap concerns where each method pays off. The lower edge of the ZNE window is set by variance amplification ([Krebsbach et al. 2022](https://doi.org/10.1103/physreva.106.062436); [Scavino Alfaro 2026](https://arxiv.org/abs/2605.08251)). The upper edge is set by signal collapse, where Richardson extrapolation degenerates into a rescaling of one noisy measurement ([Köster & Mauerer 2026](https://arxiv.org/abs/2607.09360)). These boundaries have been described separately and largely in simulation; they have not been measured jointly with CDR on one workload and one device. Finally, accuracy gains need not change downstream decisions ([Scavino 2026](https://arxiv.org/abs/2607.02888)), which matters for classifiers.

**Contributions.**
1. A shot-matched hardware test showing that logical Pauli twirling lowers CDR error on two IQM processors, with null and coherent simulation controls; a pre-registered replication on ODRA over ≥ 12 calibration windows with native twirling made overhead-free by single-qubit merging.
2. Experimental validation of the node-only variance constant κ of the ZNE help–harm boundary for three node sets on two devices, and of its reduced value under Neyman allocation.
3. A regime map along a controlled CZ ladder of one frozen workload, with boundaries predicted from pilot quantities, and a decision-level evaluation of the classifier.

## 2 Methods

### 2.1 Devices
ODRA 5 (IQM Spark-class, 5 transmons, star coupling, hub QB3; native PRX and CZ) is the primary platform. All new data in this paper come from ODRA. IQM Garnet (20 qubits, square lattice) is used for replication with existing data. Calibration snapshots (T1, T2, PRX/CZ randomized-benchmarking fidelities, readout assignment matrix) are recorded for every job.

### 2.2 Workload and routing ladder
The workload is a 5-qubit hardware-efficient variational classifier ("two curves" dataset, 8 features, 3 layers, mean-Z readout), trained noiselessly and frozen. The same logical classifier is built with entangling patterns star / linear / circular / all-to-all. Routed onto the star, these give 12 / 27 / 36 / 54 CZ [EXISTING; the exact counts depend on the Qiskit version, so the pinned version and transpiled QASM are archived]. A no-routing control uses the star pattern at depth L = 6 / 9 / 13 (24 / 36 / 52 CZ). [TODO-ODRA: identity-insertion control, CZ·CZ pairs at fixed L, separating CZ count from 1q count and duration.]

### 2.3 Mitigation arms
- **Raw:** mean-Z estimate, M·S shots.
- **ZNE:** global folding, scale factors Λ, Richardson extrapolation. Λ ∈ {1,3}, {1,3,5}, {1,3,5,7}; equal and Neyman allocation.
- **CDR:** linear fit on n_train training circuits that keep the gate skeleton and snap a random subset of rotations to the nearest Clifford angle, drawn independently per target. [Note: the earlier campaigns used a shared, fully Clifford training set; see Limitations.]
- **CDR + twirl:** every training and target circuit is replaced by M random Pauli-twirled instances, each measured with S shots. Two variants are used. *Logical* twirling wraps logical entangling gates before routing. *Native* twirling wraps every physical CZ after routing, including SWAP-derived CZs, and is then followed by merging all single-qubit gates between consecutive CZs into one PRX, with virtual-Z rotations commuted through CZ.
- **Shot-matched control:** the untwirled arm averages M identical copies (M·S shots), so every arm uses the same budget.

### 2.4 ZNE finite-shot boundary
For a fixed point with ideal value O, raw bias B and single-shot variance V, uniform allocation of S shots over |Λ| nodes gives
MSE_ZNE − MSE_raw ≈ (κ V)/S + (B²_ZNE − B²),  κ = |Λ| Σᵢ cᵢ² − 1,
where cᵢ are the Richardson coefficients. ZNE helps only above S* = κV/(B² − B²_ZNE). Under Neyman allocation nᵢ ∝ |cᵢ|σᵢ, the constant becomes κ_opt = (Σᵢ |cᵢ| σᵢ/σ₁)² − 1. With equal σᵢ this gives 3.0 / 11.25 / 35.0 for the three node sets, compared with 4.0 / 14.66 / 44.56 under uniform allocation ([Scavino Alfaro 2026](https://arxiv.org/abs/2605.08251), Remark 3). κ is estimated as the intercept of (MSE_ZNE − MSE_raw)·S regressed on budget S across R repetitions.

### 2.5 Upper edge of the ZNE window
At each ladder point we report the signal-to-noise ratio |⟨O⟩(λ_max)|/SE and the normalized retention |⟨O⟩(1)|/|O_ideal|. We also run the matched-cost garbage-folding control of [Köster & Mauerer 2026](https://arxiv.org/abs/2607.09360). The thresholds are fixed in simulation before the hardware campaign.

### 2.6 Device-calibrated simulation
Noise models are built per window from the ODRA calibration. Thermal relaxation and dephasing follow the measured T1, T2 and gate durations, depolarizing rates follow the RB fidelities, and readout uses the assignment matrix. A coherent ZZ phase θ on each CZ and a PRX over-rotation ε are added on top. We fit θ, ε by approximate Bayesian computation to the hardware r²_OFF and twirl ratios, then validate on held-out ladder points [TODO-SIM].

### 2.7 Experimental design and statistics
The design is pre-registered: hypotheses, criteria and analysis code are tagged in git before data collection [TODO: tag]. Each of ≥ 12 windows on ≥ 10 days runs all arms at all ladder points. Arm order is block-randomized within a window, and 24 evaluation points are stratified by |O_ideal| and identical across windows. Raw counts are archived per circuit. The primary analysis is a linear mixed model for log ε with fixed effects arm × CZ and random intercepts for window and evaluation point; CIs come from a cluster bootstrap over windows. Holm correction is applied across RQ1–RQ4. Drift robustness is tested with a bootstrap ratio of between-window variances. Decision agreement is tested with McNemar's test on ≥ 200 test points, stratified by margin. The power analysis (Supplement) uses the existing ODRA log-ratio SD of 0.55 at 4 evaluation points. A ratio of 0.45 is detectable with ≈ 9 windows per ladder point at α = 0.0125, and a 4× between-window variance reduction requires ≈ 15 windows.

## 3 Results

### 3.1 Twirling improves CDR at equal shot budget
[EXISTING] Under shot matching (M = 6), logical twirling lowered the CDR error in 8/8 ODRA pairs (2 windows × 12/30/39/57 CZ, 8192 shots; geometric-mean ratio 0.42, Wilcoxon p = 0.008) and in 8/9 Garnet pairs (3 windows × 12/57/96 CZ, 1024 shots; ratio 0.59, p = 0.012). In simulation the incoherent-only model gave 10/15 (ratio 0.86, p = 0.28), and the coherent model gave 15/15 (θ = 0.05: ratio 0.33) and 9/9 (θ = 0.10: ratio 0.30) (Fig. 1a). The weak gain in the incoherent model is expected: twirling also Pauli-izes amplitude damping, so the twirl effect must be judged against this null, not against unity.
[TODO-ODRA] Pre-registered replication: ratio by CZ with 95% CI; logical vs merged native twirl; drift variance ratio.

### 3.2 Native twirling needs single-qubit merging
[EXISTING] The unmerged native twirl inserted Paulis as separate PRX gates. This raised the PRX count 2.3–2.7× (e.g. 356 vs 130 at 54 CZ) and gave no gain (3/4 pairs, ratio 0.93). Merging single-qubit runs between CZs restores the count to the untwirled level (85.7 vs 63 merged at 54 CZ; 75.8 vs 75 at 36 CZ) with unchanged ideal values (Fig. 1c). Merging also halves the PRX count of the untwirled circuits (40 → 20 at 12 CZ).
[TODO-ODRA] Hardware comparison with merged circuits in all arms.

### 3.3 The ZNE window
[EXISTING] Measured κ agreed with the node-only prediction in all five configurations (Fig. 1b; {1,3}: 3.54 ± 0.56 and 3.23 ± 0.58 vs 4.00; {1,3,5}: 14.42 ± 0.95 and 13.29 ± 1.73 vs 14.66; {1,3,5,7} on ODRA: 48.1 ± 6.0 vs 44.56). The break-even budgets S* scaled as B⁻²: the B² ratio between the two Garnet points was 3.07, and the S* ratio was 2.91. On ODRA with 100 evaluation points, the ZNE gain fell from 3.30× at 12 CZ to 1.27× at 54 CZ. CDR overtook ZNE between 12 and 27 CZ (ε 0.090 vs 0.071 at 27 CZ; 0.142 vs 0.105 at 36 CZ).
[TODO-ODRA] Neyman allocation κ; garbage-folding control; SNR-based upper edge.

### 3.4 What drives degradation
[EXISTING] Unrouted deeper circuits degraded at least as fast as routed circuits at equal CZ: r² was 0.719 vs 0.792 at 36 CZ, and raw error 0.238 vs 0.186. [TODO-ODRA] The identity-insertion control separates CZ count, 1q count and duration.

### 3.5 Decisions vs expectation values
[EXISTING] Readout mitigation changed no classifier decision. Raw accuracy exceeded the noiseless test accuracy at 96 CZ on Garnet (0.78 vs 0.767), so accuracy is not a valid mitigation metric. [TODO-ODRA] Decision agreement by margin.

## 4 Discussion

Twirling should be treated as part of CDR, not as an optional add-on, once coherent error accumulates. The appropriate test is against an incoherent null at equal budget. The ZNE boundary constant is a property of the estimator; its hardware value is a consistency check on the independence and stationarity of shots, so deviations would indicate within-campaign drift. Together with signal collapse at large scales, this yields a ZNE window that can be computed from a short pilot.

**Limitations.**
- The existing campaigns used 4 evaluation points per ladder point and a CDR training set shared across targets, made of fully Clifford circuits. The pre-registered campaign removes both issues.
- Logical twirling leaves SWAP-derived CZs untwirled.
- Garnet data come from earlier campaigns and are not part of the pre-registered design.
- All results concern one workload class (mean-Z of a shallow classifier, 5 qubits).

## 5 Conclusion
[TODO after campaign]

## References
- Bultrini et al. 2023, Quantum — doi:10.22331/q-2023-06-06-1034
- Cai et al. 2023, Rev. Mod. Phys. — doi:10.1103/revmodphys.95.045005
- Czarnik et al. 2021, Quantum — doi:10.22331/q-2021-11-26-592
- Czarnik et al. 2025, Quantum — doi:10.22331/q-2025-05-05-1727
- Ezzell et al. 2023, Phys. Rev. Applied — doi:10.1103/physrevapplied.20.064027
- Figueroa-Romero et al. 2024 — arXiv:2409.02110
- Giurgica-Tiron et al. 2020, IEEE QCE — doi:10.1109/qce49297.2020.00045
- Hashim et al. 2021, Phys. Rev. X — doi:10.1103/physrevx.11.041039
- Kim et al. 2023, Nature — doi:10.1038/s41586-023-06096-3
- Köster & Mauerer 2026 — arXiv:2607.09360
- Krebsbach, Trauzettel & Calzona 2022, Phys. Rev. A — doi:10.1103/physreva.106.062436
- Kurita et al. 2023, Quantum — doi:10.22331/q-2023-11-20-1184
- LaRose et al. 2022, Quantum (Mitiq) — doi:10.22331/q-2022-08-11-774
- Lowe et al. 2021, Phys. Rev. Research — doi:10.1103/physrevresearch.3.033098
- Majumdar et al. 2023, IEEE QCE — doi:10.1109/qce57702.2023.00102
- Prodius et al. 2023 — arXiv:2307.05302
- Quek et al. 2024, Nature Physics — doi:10.1038/s41567-024-02536-7
- Russo et al. 2023, IEEE TQE — doi:10.1109/tqe.2023.3305232
- Scavino 2026 — arXiv:2607.02888
- Scavino Alfaro 2026 — arXiv:2605.08251
- Sopena et al. 2021 — arXiv:2103.12680
- Takagi et al. 2022, npj Quantum Inf. — doi:10.1038/s41534-022-00618-z
- Temme, Bravyi & Gambetta 2017, PRL — doi:10.1103/physrevlett.119.180509
- van den Berg et al. 2023, Nature Physics — doi:10.1038/s41567-023-02042-2
- Wallman & Emerson 2016, Phys. Rev. A — doi:10.1103/physreva.94.052325
