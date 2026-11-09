# Noise-informed CDR: using ZNE-style noise scaling or explicitly learned noise in the training stage of Clifford data regression

Scope: does "learn the hardware noise, then use it to train CDR" already exist, what variants exist,
what would be new, and how to test it cheaply on the IQM ODRA 5-qubit star (PRX + CZ, virtual Z). Notes
written 2026-10-25. Every literature claim carries its date and is marked **[sim]** (numerical
evidence only) or **[hw]** (hardware evidence). The local toy study (this work, offline, density-matrix
simulation) is marked **[toy]**. Its code and outputs are in this directory: `nicdr_sim.py`,
`nicdr_addon.py`, `nicdr_results_{coherent,twirl,pauli_only}.json`, `nicdr_addon_twirl.json`.

Campaign facts used below come from the repo (read-only). On w01A, n_train=20, M=6 twirl frames,
S=8192, so the CDR budget is about 1.03 M shots per point per arm and the genuine ZNE budget is
24,576 per point
([repo_inventory.md](/Users/karinaleskiewicz/QEM/research_notes/QEM%20combos%20and%20data%20reuse/repo_inventory.md)).
Training circuits snap **all** PRX angles and drop θ=0 rotations
(`/Users/karinaleskiewicz/QEM/qem/cdr_training.py:126–130`). On the star this leaves 10 PRX against 20
in the target (L13: 27 vs 70), and the serial schedule is 0.2–0.9 µs shorter
([review/recenzja.md](/Users/karinaleskiewicz/QEM/review/recenzja.md) B6, §86). P5 found ×1.434 raw
error per µs at fixed gate count, while post-CDR error scales with CZ count (+0.29 log-error per 10 CZ;
cz52 r² 0.65 vs idle52 0.82)
([review/weryfikacja.md](/Users/karinaleskiewicz/QEM/review/weryfikacja.md),
[repo_inventory.md](/Users/karinaleskiewicz/QEM/research_notes/QEM%20combos%20and%20data%20reuse/repo_inventory.md)).

---

## Q1. Variable-noise CDR (Lowe et al.): how the fit works and how well it performs

### Takeaway
"Fold the training circuits too and regress on the noisy values at several λ" already exists. It is
vnCDR (Lowe et al., arXiv Nov 2020, PRR 2021), and it ships in Mitiq. The fit is an **intercept-free**
linear map ŷ = Σ_j a_j·E(λ_j), learned by least squares on near-Clifford circuits, with the target
corrected as a·(E_1, E_3, E_5). The evidence for its large gains (33× over raw, about 1.8× over CDR)
is **simulation with an IBM Ourense noise model**, using about 80–100 training circuits. Real-hardware
evidence is sparse.

### Cited Findings
- vnCDR steps [sim, 2020/2021]. Pick noise levels 1 = c_0 < … < c_n. For each of the m training circuits V_i,
  measure x_i = (x_i0 … x_in) and compute the exact value y_i classically. Fit g(x; a) = a·x by
  a* = argmin Σ_i (y_i − a·x_i)². Correct the target as μ̂ = a*·(μ̂_0 … μ̂_n). The authors drop the
  intercept on purpose for two reasons. It mirrors ZNE's linear combination of noisy values. And if
  the map is exact on all Clifford circuits, it is exact on every circuit, because Cliffords span the
  1q unitaries (their App. B) — [Lowe et al., arXiv:2011.01157 / PRR 3, 033098 (2021)](https://arxiv.org/abs/2011.01157)
- The authors frame vnCDR as "choosing the best possible extrapolation of the noisy data … using
  examples from Clifford circuits". Richardson-ZNE is the special case with fixed a_j — [Lowe et al. 2021](https://arxiv.org/abs/2011.01157)
- Noise scaling was done by fixed identity insertion: CNOT pairs after each CNOT, with λ defined as the
  CNOT-count ratio. Levels were C={1,3,5} for the Ising/QAOA case and {1,3,5,7,9} for random circuits.
  Levels above 5 did not help on Ising — [Lowe et al. 2021](https://arxiv.org/abs/2011.01157)
- Performance [sim, Ourense noise model]. On the 8-qubit Ising energy, vnCDR improved the mean
  absolute energy error 33× over raw, against 19× for CDR and 1.7× for ZNE. That works out to about
  20× better than ZNE and about 1.8× better than CDR. Training used 80 circuits with N=16 non-Clifford
  gates left, out of 60. On 64-qubit random circuits it was about 2.7× better than ZNE and about 1.5×
  better than CDR. About 100 training circuits gave "substantial error reduction" — [Lowe et al. 2021](https://arxiv.org/abs/2011.01157)
- In Mitiq, `execute_with_cdr(..., num_training_circuits=10, fraction_non_clifford=0.1,
  fit_function=linear_fit_function, scale_factors=(1,))` gives plain CDR. Any `scale_factors` > 1
  turns it into vnCDR. The default `linear_fit_function` has 1+len(scale_factors) parameters, so it
  **keeps an intercept**, while `linear_fit_function_no_intercept` reproduces Lowe's form. Mitiq's
  default therefore differs from the paper — [Mitiq cdr.py source](https://raw.githubusercontent.com/unitaryfund/mitiq/main/mitiq/cdr/cdr.py)
- UNITED (Bultrini et al., arXiv Jul 2021, Quantum Jun 2023) [sim, trapped-ion noise model] folds ZNE,
  CDR and virtual distillation into one framework. Its central finding is that the ranking depends
  strongly on the shot budget: more powerful methods need more shots. vnCDR beat VD and ZNE in most
  regimes, and UNITED was best only at the largest budget — [Bultrini et al., Quantum 7, 1034 (2023)](https://doi.org/10.22331/q-2023-06-06-1034); [arXiv:2107.13470](https://arxiv.org/pdf/2107.13470)
- [hw] Sopena et al. (arXiv Mar 2021) applied Clifford-regression methods to 1-D Ising quench data on a
  superconducting device: 9 qubits, depth up to 176, hundreds of CNOTs. They reported quantitative
  agreement and that these methods "consistently outperform ZNE". Their simplified pmCDR variant
  struggled at depth. The snippets did not confirm which vnCDR variants ran on hardware — [Sopena et al., arXiv:2103.12680](https://arxiv.org/abs/2103.12680)
- Czarnik et al. (arXiv Apr 2022, Quantum 2025) showed CDR can be made about 10× cheaper in shots at
  equal accuracy through better training-set choice and symmetries. With a 2·10⁵-shot total budget
  they still got about 10× over raw. Hardware: XY-model correlators on IBM Toronto [hw]. LiH:
  Ourense noise model [sim] — [Czarnik et al., arXiv:2204.07109 / Quantum 9, 1727 (2025)](https://arxiv.org/abs/2204.07109)
- Extension paper (arXiv Nov 2024) [sim, 3 qubits]: an "insertion-map" CDR variant, alone or combined
  with ZNE, lowers RMSE relative to CDR and "ZNE-based CDR" — [arXiv:2411.16653](https://arxiv.org/pdf/2411.16653)

### Inferences
- For ODRA, plain vnCDR is **not new**. A hardware replication on a native-skeleton training set,
  with matched-skeleton folds already in the code path (`qem/folding.py`), is a legitimate
  "replication + doprecyzowanie" item, but not a headline result.
- The intercept question matters for us. Readout error (Garnet REM is off, and ODRA readout is not
  mitigated in CDR arms) adds an affine offset that a pure a·x cannot absorb unless the λ-dependence
  supplies it. Both forms should be reported, as the repo already does for OLS/EIV.
- [toy] vnCDR has the **lowest infinite-shot bias** of all variants (about 0.001–0.0035, against
  0.007–0.017 for CDR). At the toy's equal budget of 42k shots per target, however, it has the
  **highest variance**. Three nearly collinear regressors from 20 points inflate the coefficient
  variance. Under near-global noise, E_3 and E_5 are roughly scaled copies of E_1 across the training
  set. See Q3 for the crossover.

### Gaps
- I did not retrieve a hardware vnCDR benchmark with controlled shot budgets. Sopena 2021 is the
  closest, but its arm-level details were not checked.
- Lowe et al. report no regularisation or conditioning diagnostics for the multi-λ regression.

---

## Q2. Prior work that injects learned or scaled noise into learning-based QEM: is "learn the noise, then train CDR with it" already done?

### Takeaway
Every component exists. **Noise scaling inside CDR training** is vnCDR (2020). **Learning a
mitigation map from Clifford training circuits instead of a noise model** is Strikis et al. (2020/21,
learning-based PEC quasi-probabilities). **Learned SPL Pauli noise for amplification** is PEA
(Kim et al. 2023; Qiskit Runtime). **Training ML-QEM on noisy-simulator data and transferring to
hardware** is Liao et al. (2023/24), plus 2024–26 transfer-learning works. **Noise-agnostic data
augmentation that keeps the 2q skeleton** is DAEM (2023/25). I found **no paper that fits an
explicit twirled Pauli noise model to the CDR training set itself and then uses that model as a
prior on, or replacement for, the CDR regression**, nor one that uses separate CZ-count and
duration noise axes as vnCDR features. Those are the open niches. They are modest
methodological contributions, not new paradigms.

### Cited Findings
- **SPL noise learning** (van den Berg, Minev, Kandala, Temme; arXiv Jan 2022; Nature Physics 19,
  1116–1121, 2023) [hw]. Each twirled 2q-gate layer's noise is modelled as a sparse Pauli-Lindblad
  channel with weight-1 and weight-2 generators that follow the topology. The parameter count is
  linear in qubits. It is learned with cycle-benchmarking-style fidelity decays and non-negative
  least squares, then used for PEC on a superconducting processor with crosstalk — [arXiv:2201.09866](https://arxiv.org/abs/2201.09866v1); [APS MM23 abstract](https://archive.aps.org/mar/2023/t69/1); [IBM docs citation](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/results-pauli-lindblad-error)
- Extensions to higher-weight and longer-range SPL terms (van den Berg & Wocjan, arXiv Nov 2023,
  Quantum Dec 2024). The paper notes that SPL-based noise amplification was used "to great effect"
  on the 127-qubit Ising utility experiment — [arXiv:2311.15408](https://arxiv.org/pdf/2311.15408)
- **PEA** (Kim et al., Nature 618, 2023; Qiskit Runtime experimental) [hw]. Gate layers are twirled.
  Noise is learned from repeated identity pairs of layers, with depths [0,1,2,4,6,12,24], 40
  randomisations and 64 shots each in the tutorial. The learned model is then amplified by
  stochastically inserting Paulis, at noise factors [1, 1.3, 1.6], followed by exponential/linear
  extrapolation. The tutorial also enables XY4 DD. The options are marked "not finalized", and
  runtime mitigation is not supported on simulators — [IBM PEA tutorial](https://quantum.cloud.ibm.com/docs/tutorials/probabilistic-error-amplification)
- PEA in a 2025 72-qubit Fermi–Hubbard experiment [hw]. A local Pauli noise model is learned by
  fitting tomographic decay rates under twirling, amplified by stochastic Paulis, and extrapolated
  linearly or exponentially — [arXiv:2510.26845](https://arxiv.org/pdf/2510.26845)
- **Pauli-channel learning theory**. Flammia & Wallman give efficient estimation of Pauli channels
  (arXiv 1907.12976, 2019). Cycle benchmarking is Erhard et al. (arXiv 1902.08543, 2019). Both are
  the foundation of SPL learning. **Not re-fetched in this session**; cited from the SPL paper's lineage — [Flammia & Wallman arXiv:1907.12976](https://arxiv.org/abs/1907.12976); [Erhard et al. arXiv:1902.08543](https://arxiv.org/abs/1902.08543)
- **Learning-based QEM** (Strikis, Qin, Chen, Benjamin, Li; arXiv May 2020; PRX Quantum 2, 040330)
  [hw IBM + sim]. Each non-Clifford gate in the target is replaced by a classically efficient gate to
  make training variants. Those variants are then used to **learn the quasi-probability compensation
  strategy** directly, rather than characterising the noise first. Spatially and temporally
  correlated noise was tested. This is the closest precedent to "learn noise-correction parameters
  from the Clifford training set" — [arXiv:2005.07601](https://arxiv.org/abs/2005.07601)
- **Noise-estimation circuits** (Urbanek et al., arXiv Mar 2021, PRL 127, 270502) [sim Heisenberg].
  An auxiliary circuit with the same structure as the target, and a known ideal output, estimates a
  global depolarizing rate that rescales the target. This is effectively a one-point, intercept-free
  CDR. Combined with readout correction, randomised compiling and ZNE, it gave near-exact results at
  hundreds of CNOTs, and ZNE improved when applied to its output — [Urbanek et al. PRL 2021](https://link.aps.org/accepted/10.1103/PhysRevLett.127.270502); [arXiv:2103.08591](https://www.arxiv.org/abs/2103.08591)
- **ML-QEM** (Liao et al., IBM/UC Berkeley; arXiv Sep 2023, v2 Nov 2024; NeurIPS-23 workshop). The
  journal venue is unconfirmed; I found no Nature Machine Intelligence listing. Features are counts of
  each native gate (angles binned), the noisy expectation value, and optionally device calibration
  (GNN nodes: gate errors, T1/T2, readout). **Noise-scaled values are not features**: λ ∈ {1,3}
  appears only in the ZNE baseline. Training data: FakeLima simulator [sim] and ibm_algiers hardware
  [hw]. On ibm_algiers, a random forest beat ZNE at every Trotter step with about 50% lower runtime
  overhead (3,000 vs 5,000 circuits). On 100-qubit ibm_brisbane, the RF learned to *mimic ZNE*.
  Simulator→simulator fine-tuning (FakeLima→FakeBelem) converged in about 300 circuits. The paper has
  no direct sim→hardware transfer test — [arXiv:2309.17368v2 (HTML)](https://arxiv.org/html/2309.17368v2); [abs](https://arxiv.org/abs/2309.17368v2)
- **DAEM** (Liao, Zhu, Chiribella, Yang; arXiv Nov 2023; npj QI 11, 8, 2025) [sim + hw OriginQ]. The
  method is noise-agnostic and does not train on noise-free data. "Fiducial" circuits **keep the CNOT
  skeleton** and replace each 1q gate R with √R†·√R. That is ideally the identity, but it **keeps the
  1q pulse count and timing**. The fiducial circuits run at several noise levels without knowing the
  noise values. On the hardware test (4-qubit TFIM VQE, 10 circuits, one noise level), mean absolute
  error was 0.247 raw, 0.067 DAEM, 0.259 ZNE and 0.095 CDR — [arXiv:2311.01727 (HTML v2)](https://arxiv.org/html/2311.01727v2)
- **Transfer learning sim→hw** [hw, abstract only]. Q-CTRL (APS MM 2024) learns an approximate
  inverse noise map on efficiently simulable related circuits and transfers it to target circuits.
  Its runtime is claimed far below PEC/ZNE. Not verified beyond the abstract — [APS MM24 D52.1](https://meetings-archive.aps.org/mar/2024/d52/1)
- Cross-device transfer is fragile [hw, 2026]. Zero-shot transfer of a learned noise model between
  IBM devices raised KL from 0.30 to 1.67. K=20 fine-tuning samples brought it to 1.19. The mismatch
  was attributed mostly to CX error — [arXiv:2604.24397](https://arxiv.org/html/2604.24397). A deep-learning QEM comparison (Jan 2026) found transfer across same-architecture devices works without full retraining [sim+hw, ≤5 qubits] — [arXiv:2601.14226](https://arxiv.org/abs/2601.14226v1)
- **Clifford-validated noise models** [hw, Jul 2026]. Barron et al. (48 authors, IBM) propose
  validating quantum estimates without classical verification by characterising and manipulating
  device noise, which shifts validation onto validating the noise model. A search snippet said they
  use Clifford versions of the target (angles → 0 or π/4) to calibrate and validate noise models, but
  **only the abstract was confirmed** — [arXiv:2607.25998](https://arxiv.org/abs/2607.25998)
- Kim et al. (arXiv Aug 2021; Nat. Phys. 2023) [hw, up to 26 qubits, 1080 CNOTs] combine DD,
  Pauli twirling and pulse-stretch ZNE. Clifford circuits are used to benchmark the ZNE scaling — [arXiv:2108.09197](https://arxiv.org/abs/2108.09197); combination detail via [search snippet of arXiv:2108.09197](https://arxiv.org/pdf/2108.09197)
- Noise-aware folding uses calibration data to fold non-uniformly [hw IBM]: arXiv Jan 2024 — [arXiv:2401.12495](https://arxiv.org/pdf/2401.12495), and May 2025 adaptive scaling — [arXiv:2505.04463](https://arxiv.org/pdf/2505.04463)
- CPDR (arXiv Dec 2024) [sim]. Training circuits are *perturbed* Cliffords (small angles about
  Clifford values), with ideal values from sparse Pauli dynamics. This narrows the target–training
  gap without a noise model — [arXiv:2412.09518](https://arxiv.org/pdf/2412.09518)
- Energy-sampling / non-Clifford-extrapolation CDR (arXiv Nov 2025) [sim, ibm_torino noise model]
  adds the **number of non-Clifford parameters as an extra regressor**. This is precedent for
  structural features in the CDR fit — [arXiv:2511.03556](https://arxiv.org/abs/2511.03556)

### Inferences
- "Use ZNE's noise scaling in CDR training" = vnCDR (2020). "Use learned noise in a simulator to
  make synthetic training data" is close to Liao et al. and to the Q-CTRL transfer abstract, but
  those learn a *black-box* map from simulator data. Neither, as far as I found, fits a low-parameter
  **physical** (twirled Pauli + idle-relaxation) model to the CDR training measurements already taken,
  then uses it either to (i) predict the target's bias or (ii) regularise or augment the regression.
  Strikis et al. learn PEC coefficients from Clifford data, which is the same spirit with a different
  estimator.
- DAEM's √R†√R trick is direct precedent for **keeping 1q pulse count and timing in training
  circuits**, which is formulation 3.

### Gaps
- I could not confirm any 2025–26 hardware demonstration of a ZNE+CDR pipeline with learned noise
  factors. The extended search (Oct 2026) returned none, but search coverage is not exhaustive.
- Several 2026 items (2601.14226, 2604.24397, 2607.25998) were checked only at the abstract or
  aggregator level.
- "NOx / noise-extrapolated ML" under that name: **no reliable source found**.

---

## Q3. Formulation 1 — folded-training CDR (vnCDR on E_1, E_3, E_5)

### Takeaway
vnCDR removes most of CDR's bias **[toy]**, but at equal shot budget it loses to plain CDR until about
2.7 M shots per target in the toy, which is about 2.6× the campaign's per-arm CDR budget. The cause is
the variance of a 3-coefficient fit on 20 nearly collinear points. A two-level variant (λ 1, 3) is
the better compromise. On ODRA it costs **40 extra training circuits per target** if the existing
training data is reused. Prototype it offline first; it is low-risk and fully reuses the existing
folding code.

### Cited Findings
- Fit form, levels and training count: see Q1 — [Lowe et al. 2021](https://arxiv.org/abs/2011.01157)
- UNITED found budget-dependence: high-capacity mitigators need more shots — [Bultrini et al. 2023](https://doi.org/10.22331/q-2023-06-06-1034)
- [toy] Main run: 8 targets, 5q star with 3 layers (12 CZ, 20 PRX, 800 ns ASAP), n_train=20, budget
  42k shots/target (CDR 2k per circuit; vnCDR 667 per circuit per λ), 300 shot-noise draws. Mean
  absolute error at equal budget (infinite-shot |bias| in brackets) —
  [nicdr_results_*.json](/Users/karinaleskiewicz/QEM/research_notes/QEM%20combos%20and%20data%20reuse/nicdr_results_twirl.json):

  | truth noise | raw | CDR | vnCDR (no int.) | vnCDR (+int.) | ZNE lin | model-sub* | model-CDR* |
  |---|---|---|---|---|---|---|---|
  | Pauli only (depol CZ 1.2 %, T1 40/T2 25 µs, ro 2 %) | 0.032 | 0.012 (0.007) | 0.018 (0.001) | 0.018 (0.0006) | 0.016 (0.016) | 0.008 (0.000) | 0.011 (0.005) |
  | + coherent ZZ ε=0.10 rad per CZ, **twirled** | 0.033 | 0.013 (0.009) | 0.019 (0.001) | 0.019 (0.0007) | 0.016 (0.016) | 0.008 (0.0006) | 0.011 (0.006) |
  | + coherent ZZ ε=0.10, **untwirled** | 0.044 | 0.021 (0.017) | 0.027 (0.0035) | 0.026 (0.0036) | 0.022 (0.022) | 0.016 (0.014) | 0.018 (0.014) |

  *model-* rows in this table use a noise model fitted to infinite-shot training data, so their MAE
  is optimistic. The add-on below refits on noisy data.
- [toy] Budget scan, twirled truth, 6 new targets, 400 draws. MAE for CDR / vnCDR / vnCDR+int /
  vnCDR(λ1,3) / ZNE:
  42k: 0.0105 / 0.0157 / 0.0156 / 0.0134 / 0.0094;
  168k: 0.0064 / 0.0100 / 0.0098 / 0.0086 / 0.0093;
  672k: 0.0049 / 0.0061 / 0.0058 / 0.0057 / 0.0094;
  2.69M: 0.0044 / 0.0038 / **0.0033** / 0.0036 / 0.0094 —
  [nicdr_addon_twirl.json](/Users/karinaleskiewicz/QEM/research_notes/QEM%20combos%20and%20data%20reuse/nicdr_addon_twirl.json)

### Inferences
- **Cost on ODRA.** The campaign already has target folds at λ∈{1,3,5}: genuine ZNE, 24,576 shots
  per point. It does **not** have folded training circuits. Extra cost per target is 20 circuits at
  λ3 plus 20 at λ5. At M=6 and S=8192 that is about 2.0 M extra shots per point per arm. At a matched
  budget (S/3 per circuit) it is free, but noisier. Folded training circuits are Clifford whenever the
  base training circuit is (U·U†·U), so y_i is unchanged and no new classical simulation is needed.
- **Fair comparison.** Report three things side by side: (a) equal *total* shots, where vnCDR gets
  S/3 per circuit; (b) equal *per-circuit* S, where vnCDR costs 3×; (c) the infinite-shot bias,
  estimated by bootstrap extrapolation. The toy says vnCDR wins only on (b) and (c) at our budget.
  The repo's EIV correction (`qem/cdr_fit.py`) generalises to multivariate regression by subtracting
  the diagonal measurement-covariance matrix from XᵀX. This is needed, because attenuation is worse
  with several noisy regressors.
- **Risks.** (i) Collinearity: report the condition number of [E_1, E_3, E_5]. (ii) λ5 on circular
  (195 CZ, 15.5 µs) is near the signal floor, so use λ∈{1,3} for routed rungs. (iii) Ridge shrinkage
  toward Richardson coefficients (a_R = (15/8, −5/4, 3/8) for {1,3,5}) is a principled
  regulariser. It interpolates between ZNE and vnCDR, and it is new as far as I found, though minor.
  (iv) The garbage/identity-fold degeneracy found in the review would also contaminate vnCDR if
  identity folds were used, so use genuine folds only.
- The toy's raw errors (0.03–0.04) are smaller than w01A star raw (0.069), so the hardware crossover
  could sit at a lower budget, because bias matters more. This is unverified.

### Gaps
- The toy noise model has no time-correlated drift, no leakage and no spectator crosstalk. Real
  folds may scale non-uniformly (see the noise-aware folding papers), and the toy does not test that.

---

## Q4. Formulation 2 — model-informed CDR (learn a twirled per-CZ Pauli channel from the training circuits themselves)

### Takeaway
This is the most promising "new" element, and it costs **zero extra QPU shots** because it reuses
the 20 Clifford training circuits and the P5 identity-insertion data. In the toy it beat CDR at equal
budget: MAE 0.0071 with the model refit on shot-noisy data, against 0.0105 for CDR (twirled truth,
42k shots, n=12 draws). But its fully-correct form needs to simulate the *noisy target*, which is
only feasible because ODRA has 5 qubits. The scalable version (the fitted model generates synthetic
Clifford training points) gained less: MAE 0.011, bias 0.006. It is also biased when the model is
mis-specified, for example with untwirled coherent ZZ.

### Cited Findings
- Under Pauli twirling, a Clifford circuit's noisy ⟨P⟩ for a Pauli observable is an exactly
  computable product or sum of Pauli-channel fidelities. That is why SPL/cycle-benchmarking learning
  works and why PEA can amplify the learned noise — [van den Berg et al. 2023](https://arxiv.org/abs/2201.09866v1); [IBM PEA tutorial](https://quantum.cloud.ibm.com/docs/tutorials/probabilistic-error-amplification)
- Learning correction parameters from Clifford variants of the target (rather than from dedicated
  learning circuits) was done for PEC by Strikis et al. 2020/21 [hw+sim] — [arXiv:2005.07601](https://arxiv.org/abs/2005.07601)
- PEC/PEA are unbiased only to the extent that the learned model matches the device — [arXiv:2607.25998 (abstract framing)](https://arxiv.org/abs/2607.25998); [PEA tutorial caveats](https://quantum.cloud.ibm.com/docs/tutorials/probabilistic-error-amplification)
- [toy] Fit model: 3 parameters (CZ depolarizing p, idle-rate scale κ on T1/T2, readout factor r).
  It is least-squares fitted to the 20 training values by re-simulation. With Pauli-only truth it
  recovers the true parameters exactly (p=0.012, κ=1, r=0.96) and gives zero model-sub bias. With
  twirled ZZ (not in the model), the fit absorbs it into p and κ, and the bias stays small (0.0006).
  With **untwirled coherent ZZ**, the fitted parameters wander (κ hits bound 0.05 for some targets)
  and the bias is 0.014, barely better than CDR's 0.017 —
  [log_coherent.txt](/Users/karinaleskiewicz/QEM/research_notes/QEM%20combos%20and%20data%20reuse/log_coherent.txt), [nicdr_results_coherent.json](/Users/karinaleskiewicz/QEM/research_notes/QEM%20combos%20and%20data%20reuse/nicdr_results_coherent.json)

### Inferences
- **Formulation options** (in increasing generality):
  1. *Model subtraction*: Ê = E_tgt − [E_model(tgt) − E_ideal(tgt)]. This needs a classical noisy
     simulation of the non-Clifford target. It is fine at 5q, and at scale it needs Pauli propagation.
     It is closest to PEC-by-post-processing.
  2. *Model-predicted CDR line*: the fitted model generates N≫20 synthetic Clifford circuits
     (stabilizer simulation with stochastic Paulis is efficient at any size) and yields (a_m, b_m).
  3. *Shrinkage CDR* (recommended, new): a Bayesian/ridge fit of (a, b) on the 20 hardware points
     with prior mean (a_m, b_m) and prior covariance from the model fit's uncertainty. A misspecified
     model is overruled by the data, and a good one cuts variance.
  4. *Hierarchical identification*: fit p_CZ and the idle rate jointly from the training set **plus
     the P5 `star_cz*` / `star_idle*` circuits**. Those are Clifford-snappable and separate the CZ and
     duration components, which in the toy were partly degenerate.
- **Parameterisation for ODRA.** Use the per-edge twirled CZ Pauli channel (15 rates per edge × 4
  edges is too many for 20 points). Instead: a per-edge depolarizing p_e (4), a per-qubit
  idle-dephasing/relaxation rate (5), and a readout factor (1 or 5). That is 10–14 parameters, so
  pool across the 8 targets of a window (160 training circuits). This uses the fact that noise is
  shared across targets within a calibration window, which plain per-target CDR ignores. **Pooling
  across targets is the main statistical lever.**
- **Risks.** Misspecification (coherent residuals after finite M=6 twirling; the review notes that
  merge1q changes PRX angles, so twirling is only "in expectation"), drift within the night, and
  leakage. Mitigation: always report the model's goodness-of-fit on held-out training circuits and on
  the λ3/λ5 folds, which act as validation data the model must predict.
- **Offline prototyping.** Fully possible in Aer or the toy simulator, and on *existing* ODRA
  `counts.jsonl`: fit the model to the w01A/P5 training records, predict each target, and compare
  against stored ideals. Zero new QPU time. This is the cheapest high-value experiment in these notes.

### Gaps
- The toy's model-informed numbers have small n (12 noisy-fit draws), and the targets differ from the
  main run. Treat them as directional only.
- I have no evidence on how well a 10–14 parameter model identifies from 160 star training circuits
  that all share one skeleton. Identifiability of κ vs p was weak in the toy (fitted κ varied
  0.05–1.2 under twirled truth).

---

## Q5. Formulation 3 — duration-aware CDR (matching training-circuit PRX count and duration to the target)

### Takeaway
On ODRA the repo's training circuits are systematically **shorter and lighter** than their targets
(10 vs 20 PRX on star, 0.2–0.9 µs shorter), and raw error grows ×1.43/µs. CDR's slope is therefore
calibrated on circuits that saw less decoherence. The fix is cheap and precedented (DAEM keeps 1q
pulses as √R†√R): replace each dropped θ=0 rotation with a matched `delay(20 ns)` or a PRX(π)·PRX(π)
pair, so the schedule is identical. In the toy the mismatch was tiny (17 vs 20 PRX, 792 vs 800 ns),
so the toy shows **no effect**. The hardware effect has to be measured.

### Cited Findings
- Repo mismatch: star 10 vs 20 PRX, L13 27 vs 70, serial schedule 0.2–0.9 µs shorter; twirled
  targets have more PRX than untwirled ones (24.5 vs 20) and are longer (1.21 vs 1.12 µs) — [review/recenzja.md](/Users/karinaleskiewicz/QEM/review/recenzja.md)
- P5: raw duration factor 1.434 per µs. Small-cluster p = 1.7e-4 (t₇) and 0.010 (wild bootstrap).
  Duration is *computed* ASAP time, and IQM rounds delays up — [review/weryfikacja.md](/Users/karinaleskiewicz/QEM/review/weryfikacja.md); [recenzja C8/B9](/Users/karinaleskiewicz/QEM/review/recenzja.md)
- DAEM fiducial circuits keep each 1q gate as √R†·√R. That preserves the gate count and the CNOT
  skeleton, so training "ideally" sees the target's noise pattern — [arXiv:2311.01727](https://arxiv.org/html/2311.01727v2)
- Urbanek et al.: the noise-estimation circuit is built with the same structure as the target — [PRL 127, 270502](https://link.aps.org/accepted/10.1103/PhysRevLett.127.270502)
- Precedent for structural regressors: non-Clifford-count feature in CDR [sim] — [arXiv:2511.03556](https://arxiv.org/abs/2511.03556); native gate counts as ML-QEM features — [Liao et al.](https://arxiv.org/html/2309.17368v2)
- [toy] cdr_drop vs cdr_matched: identical to 3 decimals in all three noise settings, because the
  toy's random angles rarely snap to θ=0 and the hub-serial schedule absorbs the gaps — [nicdr_results_*.json](/Users/karinaleskiewicz/QEM/research_notes/QEM%20combos%20and%20data%20reuse/nicdr_results_twirl.json)

### Inferences
- **Back-of-envelope.** Under a global-depolarizing caricature, CDR's slope is a = 1/f_train, while
  the target needs 1/f_target. If raw error multiplies by about 1.43 per µs, a 0.5 µs shorter
  training schedule lets training see roughly 20% less degradation. The corrected value then keeps a
  multiplicative bias of order ±(f_train/f_target − 1)·|ideal|. That is a few × 10⁻² for |ideal|
  ≈ 0.3, the same order as the observed 0.02 residual at 12 CZ. This is a hypothesis, not a
  measurement.
- **Three implementation options**, cheapest first:
  (a) *Timing match*: θ=0 → `delay(t_PRX)`, which gives an identical ASAP schedule but not identical
      1q-pulse error;
  (b) *Pulse match*: θ=0 → PRX(π,φ)·PRX(π,φ+π), which is identity and Clifford. This doubles the
      pulses at that spot, so use PRX(π/2)·PRX(−π/2) or a √R†√R analogue to keep one pulse-time. All
      are Clifford, so y_i is unchanged;
  (c) *Partial snapping* (actual near-Clifford, as in Czarnik's original): keep k non-Clifford
      rotations at their true angles. This needs a stabilizer-rank or small-statevector simulator,
      trivial at 5q but not scalable.
- **Feature-augmented CDR**: y = a·x + b + c·(Δt_i) + d·(ΔCZ_i), where Δ is the training circuit's
  deviation from its target. This only works if the training set spans Δ. Deliberately add a few
  training circuits with inserted idle (P5's `idle_matched`) or CZ pairs. These are Clifford and
  reuse `qem/identity_insertion.py`. Then the regression *learns* the duration and CZ sensitivity,
  and evaluating at Δ=0 targets the actual target. This is effectively a **two-axis vnCDR**, with
  noise scaled separately along CZ count and duration. That maps P5's mechanistic finding directly
  into the estimator. I found no precedent for two-axis noise scaling inside CDR. Multi-parameter
  Richardson over independently scaled noise sources exists in the ZNE literature (Otten & Gray 2019,
  PRA 99, 012338; **not re-checked in this session**).
- **Cost.** Option (a) or (b) replaces the existing training set at equal cost (re-measure 20
  circuits per target). Two-axis vnCDR adds, for example, 10 training circuits with +k CZ pairs and
  10 with matched idle per target. A 5-parameter regression on 40 points is borderline, so pool the
  sensitivities (c, d) across targets in a window.
- **Fair test.** Same window, interleaved blocks: `cdr_drop` vs `cdr_matched` vs `cdr_pulse_matched`
  at the same n_train and S, star and circular rungs. The pre-registerable prediction: the matched
  arm has lower |bias| and an unchanged r², and the gain grows with the dropped duration (largest on
  L13 and circular).

### Gaps
- The toy cannot reproduce the hardware's 0.2–0.9 µs gap, because the compiled native star has a
  schedule structure the toy lacks. Re-running the toy with the repo's actual native circuits
  (`qem/compile.py`) would fix that. I did not do it, to stay within read-only use of the repo.
- Whether IQM's compiler or firmware drops or merges `delay` or zero-angle PRX is unknown. It must be
  verified from the executed QASM in `counts.jsonl`.

---

## Q6. Formulation 4 — twirling + DD + CDR stack

### Takeaway
Combining DD and Pauli twirling has hardware precedent with extrapolation (Kim et al. 2021/23; IBM
PEA tutorial uses XY4 + twirling). I found **no published CDR + twirl + DD stack**. On the star,
spokes idle while the hub runs serial CZs, so DD is well motivated. X/Y DD pulses are Cliffords and
keep training circuits Clifford, so CDR's classical simulability survives. The main interactions:
twirling linearises the noise in expectation (good for CDR), DD lengthens nothing but changes which
noise the training sees, and DD must be applied identically to targets and training circuits.

### Cited Findings
- Kim et al. (arXiv 2021, Nat. Phys. 2023) [hw]: DD and Pauli twirling as complementary ingredients
  with stretch-ZNE — [arXiv:2108.09197](https://arxiv.org/pdf/2108.09197)
- IBM PEA tutorial enables XY4 DD together with gate twirling (700 randomisations × 64 shots) [hw] — [IBM PEA tutorial](https://quantum.cloud.ibm.com/docs/tutorials/probabilistic-error-amplification)
- 72-qubit Fermi–Hubbard: twirling makes the noise transfer matrix diagonal in the Pauli basis, and is
  paired with spin-echo DD on idles [hw] — [arXiv:2510.26845](https://arxiv.org/pdf/2510.26845)
- Twirling does not tailor every coherent error. An RZZ-type error was not tailored by the twirl group
  in a 2025 plasma-wave hardware paper, and needed separate learning — [arXiv:2507.09479](https://arxiv.org/pdf/2507.09479)
- Repo review: "twirled channel becomes Pauli" only in the full-average limit (M→∞) with
  gate-independent 1q errors. merge1q changes PRX angles, and M=6 is a finite sample — [review/recenzja.md C14](/Users/karinaleskiewicz/QEM/review/recenzja.md)
- [toy] Twirling coherent ZZ (exact average) cut CDR bias from 0.017 to 0.009 and made the
  model-informed estimators work (bias 0.014 → 0.0006). This is consistent with "twirling makes CDR
  and noise models linear and Pauli" — [nicdr_results_coherent.json](/Users/karinaleskiewicz/QEM/research_notes/QEM%20combos%20and%20data%20reuse/nicdr_results_coherent.json), [nicdr_results_twirl.json](/Users/karinaleskiewicz/QEM/research_notes/QEM%20combos%20and%20data%20reuse/nicdr_results_twirl.json)

### Inferences
- **Order of operations**: compile → insert DD on idle windows (X–X or XY4 as PRX(π,0)/PRX(π,π/2)) →
  twirl the CZ layers → merge1q. Twirl Paulis next to DD pulses merge into the same PRX, so the pulse
  count does not grow much. Insert DD *before* snapping, so training circuits inherit identical DD.
  DD pulses are Clifford, so `is_clifford` still holds.
- **Linearity.** DD suppresses quasi-static dephasing and static ZZ toward spokes. Those are coherent
  errors whose effect on ⟨O⟩ depends on the state, which differs between Clifford and non-Clifford
  circuits, and that breaks CDR transfer. So DD should mostly *raise r²* rather than lower raw error.
  This is a testable prediction aligned with P5 (CZ count hurts r²).
- **Cost.** One extra arm (DD on/off) × rungs, at equal shots. Twirl frames are already M=6. No extra
  classical cost.
- **Offline prototyping.** Needs a noise model with coherent idle terms (detuning/static ZZ) that the
  current repo device model may lack. The toy simulator can add Z-rotation-during-idle easily. Without
  that term the simulation will show DD as useless.
- **Risks.** DD pulse errors on IQM PRX (20 ns) add 1q error and can *lower* raw fidelity on short
  idles. Idle windows on the star are 60–180 ns, which fits only 1–2 DD pairs. Month-1 ODRA had DD
  arms ([repo_inventory.md](/Users/karinaleskiewicz/QEM/research_notes/QEM%20combos%20and%20data%20reuse/repo_inventory.md)), and their outcome should be read before spending budget.

### Gaps
- I found no source quantifying DD's effect on CDR's r² or slope transfer, on hardware or in
  simulation.
- I have no IQM-specific DD documentation (how qiskit-iqm or the IQM compiler handle `delay`
  splitting).

---

## Q7. What would be genuinely new, and how to test it cheaply and fairly on ODRA

### Takeaway
Not new: vnCDR, PEA/SPL learning, ML-QEM trained in simulation, DAEM-style skeleton-preserving
augmentation, or DD+twirl stacks. Plausibly new, and cheap on existing data: **(1)**
pooled-across-targets, model-informed shrinkage CDR, where a twirled Pauli + idle model is fitted to
the CDR training set and the P5 identity-insertion circuits and used as a prior on (a, b); **(2)**
two-axis vnCDR, with noise scaled separately in CZ count and duration, directly operationalising P5;
**(3)** a duration/pulse-matched training set as a controlled fix, with a pre-registered prediction.
Each needs to be judged at equal total shots with drift-window error bars.

### Cited Findings
- Budget-dependence of method rankings — [Bultrini et al. 2023](https://doi.org/10.22331/q-2023-06-06-1034)
- CDR frugality ×10 by training-set design — [Czarnik et al. 2025](https://arxiv.org/abs/2204.07109)
- [toy] At 42k shots per target, the ordering under twirled truth is model-sub (0.007–0.008) < model-CDR (0.011) ≈ CDR (0.011–0.013)
  < ZNE (0.009–0.016) < vnCDR (0.016–0.019). ZNE beat CDR in the add-on target set but not in
  the main set, so target-to-target variance is large — [nicdr_results_twirl.json](/Users/karinaleskiewicz/QEM/research_notes/QEM%20combos%20and%20data%20reuse/nicdr_results_twirl.json), [nicdr_addon_twirl.json](/Users/karinaleskiewicz/QEM/research_notes/QEM%20combos%20and%20data%20reuse/nicdr_addon_twirl.json)

### Inferences
- **Zero-QPU step (do first).** On w01A + w01P5 `counts.jsonl`:
  (i) fit the pooled twirled-Pauli + idle model to all training circuits in a window. Validate it on
  held-out training circuits and on the genuine λ3/λ5 target folds, which the model must predict
  without being fitted to them;
  (ii) compute model-subtraction and shrinkage-CDR estimates for each target against stored ideals;
  (iii) in P5, check whether the model's CZ vs idle components reproduce the regression's ×1.43/µs
  and +0.29/10 CZ. That gives a mechanistic cross-check of H7a/H7b from a different estimator. All
  of it is analysis code only, with no circuits.
- **Next QPU step (cheapest new data, one window).** Star and circular, 8 points, interleaved:
  `cdr_matched` (θ=0→delay), `cdr_pulse_matched`, and folded training at λ3 for vnCDR(1,3). λ5 is
  skipped because of the variance and signal floor. Fold the existing target λ1/λ3 data. That is
  about 20+20 circuits per point per arm. At the current M=6 × S=8192, it roughly doubles the CDR
  arm. Halving S keeps the budget equal.
- **Fair evaluation protocol.**
  (1) Equal total shots per target, *including* training and folds, with the shots_to_target cost
  axis already in the project.
  (2) Report bias and variance separately (bootstrap over shots and frames).
  (3) Error bands from ≥2 calibration windows, not in-window repeats (project rule).
  (4) Pre-register the primary comparison (e.g. |err| of shrinkage-CDR vs OLS-CDR, star and circular,
  Holm across rungs).
  (5) Report the condition number for vnCDR and the held-out fit quality for the model-based arms.
  (6) Never tune σ, the λ set or the prior strength on the evaluation targets. Tune on a separate
  set of points or windows.
- **Overfitting with 20 points.** CDR (2 parameters) is fine. vnCDR+int (4) is marginal. Feature
  CDR (5) and per-edge models (10–14) **must** pool across targets. A window has 8 targets × 20 =
  160 training circuits sharing one calibration, and pooling is legitimate only within a window.
- **Biggest single risk.** Every model-informed gain depends on the twirled Pauli model being
  adequate. With M=6 frames and merge1q, residual coherent error is plausible, and in the toy
  untwirled ZZ wiped out most of the model-informed gain. The held-out λ-fold prediction test in step
  (i) is the go/no-go criterion.

### Gaps
- The toy uses a random star ansatz with near-zero-mean ideals, not the frozen two_curves classifier.
  Its absolute numbers do not transfer. Re-running the toy on the repo's actual native circuits and
  P7 device model is the natural next offline step and was not done here.
- I found no published equal-budget hardware comparison of CDR vs vnCDR vs a model-informed CDR.
