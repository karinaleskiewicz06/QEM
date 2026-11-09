# Literature map and research gap: when does QEM pay off on a small superconducting processor (IQM 5-qubit star, ODRA) for variational quantum classifiers

How sourcing works in these notes: every bullet has an inline link. Some bullets are marked **[bg]**. Those come from background knowledge of well-known papers, with the canonical arXiv id given. I did not re-fetch them this session, so check the bibliographic details (volume and page) before submission. Unmarked bullets were confirmed by web search or fetch in this session.

---

## Q1. Key papers and numbers on CDR, vnCDR, ZNE, twirling, PEC, DD, combined methods, limits and reviews

### Takeaway
The main methods were all introduced between 2016 and 2021. The best-known benchmark that combines methods (Bultrini et al., Quantum 2023, "UNITED") is mostly a **simulation** study. The vnCDR advantage over CDR was shown with numerical noise models. The theoretical limit papers (Takagi 2022; Quek 2024) give worst-case asymptotic exponential sampling costs. They do not say at what concrete two-qubit-gate budget a given method stops paying off on a given device.

### Cited Findings
**CDR and vnCDR (learning-based)**
- CDR was introduced by Czarnik, Arrasmith, Coles and Cincio in "Error mitigation with Clifford quantum-circuit data", *Quantum* 5, 592 (2021), arXiv:2005.10189. It fits a linear map from noisy to ideal values using near-Clifford training circuits, solved by least squares. — [arXiv:2005.10189](https://arxiv.org/pdf/2005.10189v1)
- **[bg]** The CDR paper reports about an order-of-magnitude error reduction on IBM hardware (a 16-qubit device) and in noisy simulations of up to 64 qubits. — [arXiv:2005.10189](https://arxiv.org/abs/2005.10189)
- vnCDR was introduced by Lowe, Gordon, Sopena, Czarnik, Coles and Cincio in "Unified approach to data-driven quantum error mitigation", *Phys. Rev. Research* 3, 033098 (2021), arXiv:2011.01157. For an 8-qubit Ising energy it reduced error by a factor of **33 relative to unmitigated**, and was **20× better than ZNE and 1.8× better than CDR**. For 64-qubit random circuits it beat both. **These benchmarks used noise-model simulations.** — [arXiv:2011.01157](https://arxiv.org/pdf/2011.01157)
- The same line of work reports that CDR and vnCDR need far more shots than ZNE: about 12–25× in one setting and up to about 25–50× in another, as reported in the search summary of 2011.01157. I did not verify the exact figures in the PDF. — [arXiv:2011.01157](https://arxiv.org/pdf/2011.01157)
- Sopena et al., "Simulating quench dynamics on a digital quantum computer with data-driven error mitigation", *Quantum Sci. Technol.* (2021), arXiv:2103.12680. On IBM hardware, the CDR-based methods were "advantageous in comparison with zero-noise extrapolation". — [arXiv:2103.12680](https://www.arxiv.org/abs/2103.12680)
- Czarnik, McKerns, Sornborger and Cincio, "Improving the efficiency of learning-based error mitigation", *Quantum* 9, 1727 (2025), arXiv:2204.07109. The standard near-Clifford training sets **cluster** in their ideal values, so they need large training sets. Spreading the training values and using symmetries gives the same accuracy as CDR at about **10× lower cost**. On IBM Toronto they got about a 10× improvement over unmitigated results with a total budget of 2·10⁵ shots. **The paper has no CDR error-bar or uncertainty methodology.** — [Quantum 9, 1727](https://quantum-journal.org/papers/q-2025-05-05-1727/)
- CPDR (Clifford Perturbation Data Regression, arXiv:2412.09518) uses training circuits made of small-angle perturbations around Clifford gates. It reports better accuracy than the original mitigation results on the 127-qubit IBM Eagle. — [arXiv:2412.09518](https://arxiv.org/html/2412.09518v1)

**ZNE**
- **[bg]** Temme, Bravyi and Gambetta, "Error mitigation for short-depth quantum circuits", *PRL* 119, 180509 (2017), arXiv:1612.02058. Introduces Richardson extrapolation and PEC. — [arXiv:1612.02058](https://arxiv.org/abs/1612.02058)
- **[bg]** Li and Benjamin, "Efficient variational quantum simulator incorporating active error minimization", *PRX* 7, 021050 (2017), arXiv:1611.09301. — [arXiv:1611.09301](https://arxiv.org/abs/1611.09301)
- **[bg]** Kandala et al., "Error mitigation extends the computational reach of a noisy quantum processor", *Nature* 567, 491 (2019), arXiv:1805.04492. ZNE by pulse stretching on IBM hardware. — [arXiv:1805.04492](https://arxiv.org/abs/1805.04492)
- Giurgica-Tiron, Hindy, LaRose, Mari and Zeng, "Digital zero noise extrapolation for quantum error mitigation", IEEE QCE 2020, arXiv:2005.10921. Introduces unitary (global and local) folding. Its benchmarks are **density-matrix simulations** of random circuits and a variational algorithm, not deep-circuit hardware runs. — [arXiv:2005.10921](https://arxiv.org/pdf/2005.10921)
- Mitiq documentation warns that a device compiler can undo unitary folding, so the noise is never actually amplified. It recommends switching off hardware optimization. — [Mitiq ZNE/IonQ example](https://mitiq.readthedocs.io/en/stable/examples/zne-braket-ionq.html)
- Kim et al., "Scalable error mitigation for noisy quantum circuits produces competitive expectation values", *Nature Physics* 19, 752–759 (2023), arXiv:2108.09197. ZNE on up to 26 qubits. DD and **Pauli twirling** are named as essential ingredients: twirling suppresses the off-diagonal (coherent) error contributions, with averaging over 1–15 twirl instances. — [arXiv:2108.09197](https://arxiv.org/pdf/2108.09197)
- Anand, Temme et al. ran a classical benchmark of ZNE on IBM Eagle circuits with 127 qubits and up to 60 CNOT layers (arXiv:2306.17839). ZNE matched exact values within error bars where exact checks were possible (depth about 15 CNOT layers). It could not be verified beyond that regime. — [arXiv:2306.17839](https://ar5iv.labs.arxiv.org/html/2306.17839)
- Majumdar et al., "Best practices for quantum error mitigation with digital zero-noise extrapolation", arXiv:2307.05203 (IEEE QCE 2023). — [arXiv:2307.05203](https://arxiv.org/pdf/2307.05203v2)
- Pelofske and Russo et al. on ZNE for effective quantum volume (arXiv:2306.15863). They used local folding of a random subset of CNOTs, assuming CNOTs dominate the error. — [arXiv:2306.15863](https://arxiv.org/pdf/2306.15863)

**Pauli twirling / randomized compiling**
- **[bg]** Wallman and Emerson, "Noise tailoring for scalable quantum computation via randomized compiling", *PRA* 94, 052325 (2016), arXiv:1512.01098. Converts coherent errors into stochastic Pauli noise. — [arXiv:1512.01098](https://arxiv.org/abs/1512.01098)
- **[bg]** Hashim et al., "Randomized compiling for scalable quantum computing on a noisy superconducting quantum processor", *PRX* 11, 041039 (2021), arXiv:2010.00215. A hardware demonstration on superconducting qubits. — [arXiv:2010.00215](https://arxiv.org/abs/2010.00215)
- Twirling does not remove every coherent error. An RZZ-type error is "not tailored at all by the twirling group" and needs separate learning (arXiv:2507.09479). — [arXiv:2507.09479](https://arxiv.org/pdf/2507.09479)

**PEC**
- **[bg]** van den Berg, Minev, Kandala and Temme, "Probabilistic error cancellation with sparse Pauli–Lindblad models on noisy quantum processors", *Nature Physics* 19, 1116 (2023), arXiv:2201.09866. — [arXiv:2201.09866](https://arxiv.org/abs/2201.09866)
- **[bg]** Endo, Benjamin and Li, "Practical quantum error mitigation for near-future applications", *PRX* 8, 031027 (2018), arXiv:1712.09271. — [arXiv:1712.09271](https://arxiv.org/abs/1712.09271)

**DD**
- **[bg]** Viola, Knill and Lloyd, "Dynamical decoupling of open quantum systems", *PRL* 82, 2417 (1999), arXiv:quant-ph/9809071. — [arXiv:quant-ph/9809071](https://arxiv.org/abs/quant-ph/9809071)
- **[bg]** Ezzell, Pokharel, Tewala, Quiroz and Lidar, "Dynamical decoupling for superconducting qubits: a performance survey", *Phys. Rev. Applied* 20, 064027 (2023), arXiv:2207.03670. — [arXiv:2207.03670](https://arxiv.org/abs/2207.03670)
- DD+ZNE has been combined on hardware, for example in IBM's tutorial on combining techniques and the Mitiq DDD+ZNE example (the Mitiq example is a simulator). One 2026 study of dynamic circuits found DD+ZNE combined to be best (arXiv:2605.05256). **I found no hardware experiment combining DD with CDR.** — [IBM tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/combine-error-mitigation-techniques); [Mitiq DDD+ZNE](https://mitiq.readthedocs.io/en/stable/examples/combine_ddd_zne.html); [arXiv:2605.05256](https://www.alphaxiv.org/abs/2605.05256)

**Combinations and benchmarks**
- Bultrini, Gordon, Czarnik, Arrasmith, Cerezo, Coles and Cincio, "Unifying and benchmarking state-of-the-art quantum error mitigation techniques", *Quantum* 7, 1034 (2023), arXiv:2107.13470. Introduces UNITED, which combines ZNE, CDR/vnCDR and virtual distillation, and benchmarks which method wins in which regime of shot budget and noise. The benchmark is mainly **simulated with a realistic noise model**. — [Quantum 7, 1034](https://quantum-journal.org/papers/q-2023-06-06-1034/pdf/); [arXiv:2107.13470](https://arxiv.org/pdf/2107.13470.pdf)
- **[bg]** LaRose et al., "Mitiq: a software package for error mitigation on noisy quantum computers", *Quantum* 6, 774 (2022), arXiv:2009.04417. — [arXiv:2009.04417](https://www.arxiv.org/pdf/2009.04417)
- Russo, Mari, Shammah, LaRose and Zeng, "Testing platform-independent quantum error mitigation on noisy quantum computers", *IEEE Trans. Quantum Eng.* (2023), arXiv:2210.07194. Tests ZNE and PEC on IBM, IonQ and Rigetti hardware using a **resource-normalized "improvement factor"**. Mitigation helps on average after cost normalization, and "the performance of quantum error mitigation depends on the underlying computer". The abstract says nothing about breakdown as a function of depth or two-qubit-gate count. — [arXiv:2210.07194](https://arxiv.org/abs/2210.07194)

**Limits**
- **[bg]** Takagi, Endo, Minagawa and Gu, "Fundamental limits of quantum error mitigation", *npj Quantum Inf.* 8, 114 (2022), arXiv:2109.04457. — [arXiv:2109.04457](https://arxiv.org/abs/2109.04457)
- **[bg]** Takagi, Tajima and Gu, "Universal sampling lower bounds for quantum error mitigation", *PRL* 131, 210601 (2023), arXiv:2208.09178. — [arXiv:2208.09178](https://arxiv.org/abs/2208.09178)
- Quek, Stilck França, Khatri, Meyer and Eisert, "Exponentially tighter bounds on limitations of quantum error mitigation", *Nature Physics* 20, 1648 (2024), arXiv:2210.11505. In the worst case, even at poly log log n depth, a super-polynomial number of samples is needed. The framework covers ZNE, CDR, PEC and virtual distillation. The authors also note implications for QML kernel estimation and earlier noise-induced barren plateaus. **The bounds are worst-case.** — [arXiv:2210.11505](https://arxiv.org/abs/2210.11505v3); [MATH+ summary](https://mathplus.de/news/challenging-quantum-error-mitigation-publication-in-nature-physics-jens-eisert-group/)

**Review**
- **[bg]** Cai, Babbush, Benjamin, Endo, Huggins, Li, McClean and O'Brien, "Quantum error mitigation", *Rev. Mod. Phys.* 95, 045005 (2023), arXiv:2210.00921. — [arXiv:2210.00921](https://arxiv.org/abs/2210.00921)

**IQM star hardware**
- Renger et al., "A superconducting qubit-resonator quantum processor with effective all-to-all connectivity", arXiv:2503.10903. Six transmons around a central resonator, with MOVE fidelity about 98.8% and CZ fidelity about 98.3% (figures from a secondary summary). Note: ODRA is a 5-qubit star with a central *qubit* (IQM Spark-type), not the resonator-based "IQM Star". Companion papers: 2503.12869 (error detection in the star architecture) and 2503.11507. — [alphaxiv 2503.10903](https://alphaxiv.org/overview/2503.10903v2); [Quantum Insider](https://thequantuminsider.com/2025/04/30/iqm-star-topology-amplifies-all-to-all-qubit-connectivity-through-a-central-resonator/)
- Work on simulating and benchmarking the IQM 20-qubit device (arXiv:2508.04483) attributes the gap between simulation and hardware to **coherent errors (over-rotations), leakage and crosstalk**. Its worst Hellinger distance is 0.115 (for GHZ-6). — [arXiv:2508.04483](https://arxiv.org/pdf/2508.04483)

### Inferences
- The well-known quantitative comparisons of CDR, vnCDR and ZNE come mostly from simulation (Lowe 2021; Bultrini 2023) or from single physics observables on IBM hardware (Sopena 2021; Czarnik 2025). Finding (d), that vnCDR beats CDR in simulation but not on hardware, directly tests the external validity of the Lowe and Bultrini rankings.
- No source found gives a **measured decay rate of the mitigation gain per added two-qubit gate**. Finding (a), "×0.78 per +10 CZ" for CDR versus a 3.6–4.6× plateau with twirling up to 57 CZ, is that missing empirical quantity.

### Gaps
- I could not confirm the exact numerical CDR improvement factors on hardware from the original 2005.10189 PDF. I also could not tell whether the 12–50× shot overhead figures come from hardware or simulation.
- I found no paper reporting CDR with and without Pauli twirling on the same hardware as a function of depth.

---

## Q2. QEM benchmarks versus circuit depth or two-qubit gate count on real hardware, learning-based QEM, and error bars for CDR

### Takeaway
Hardware benchmarks either normalize by resources across devices without a depth sweep (Russo 2023), or show ZNE working at utility scale with twirling and DD (Kim 2023; Anand/Temme 2023) without mapping where it breaks down. Learning-based QEM is now scaling (Liao 2024, IBM, up to 100 qubits). **There is no established, calibrated uncertainty or error-bar procedure for CDR on hardware.** This is the gap finding (g), the LOO-CV error bar, fills.

### Cited Findings
- Russo et al. 2023 use a resource-normalized improvement factor across IBM, IonQ and Rigetti. Effectiveness depends on the device, and the abstract has no depth or two-qubit-gate-resolved breakdown. — [arXiv:2210.07194](https://arxiv.org/abs/2210.07194)
- ZNE on Eagle was verified only up to about 15 CNOT layers. Deeper results (up to 60 layers) could not be checked classically. — [arXiv:2306.17839](https://ar5iv.labs.arxiv.org/html/2306.17839)
- Kim et al. 2023: the efficacy of ZNE is "greatly enhanced" by error suppression (DD and twirling) and by shorter circuit time. — [arXiv:2108.09197](https://arxiv.org/pdf/2108.09197)
- Liao, Wang, Sitdikov, Salcedo, Seif and Minev, "Machine learning for practical quantum error mitigation", *Nature Machine Intelligence* 6, 1478–1486 (2024), arXiv:2309.17368. They benchmark linear regression, random forests, MLPs and GNNs against digital ZNE on up to 100 qubits, and report a drastic cost reduction without loss of accuracy. — [arXiv:2309.17368](https://arxiv.org/abs/2309.17368v2)
- **[bg]** Strikis, Qin, Chen, Benjamin and Li, "Learning-based quantum error mitigation", *PRX Quantum* 2, 040330 (2021), arXiv:2005.07601. — [arXiv:2005.07601](https://arxiv.org/abs/2005.07601)
- Cantori et al. (EPJ Quantum Technology 2024) report that a deep-learning mitigator beats ZNE on expectation values. — [EPJ QT](https://epjquantumtechnology.springeropen.com/counter/pdf/10.1140/epjqt/s40507-024-00256-8.pdf)
- Czarnik et al. 2025 identify training-set clustering as the reason CDR needs many training circuits. They mitigate it by spreading the training values, but give **no error-bar procedure**. — [Quantum 9, 1727](https://quantum-journal.org/papers/q-2025-05-05-1727/)
- A targeted search for CDR error bars and uncertainty as a function of the number of training circuits found **no dedicated study**. — [search context: Quantum 2025 / QURI Parts CDR tutorial](https://quri-parts.qunasys.com/docs/tutorials/basics/error_mitigation/cdr/)

### Inferences
- Finding (b), that CDR on hardware is limited by the *number of training circuits* rather than shots, fits Czarnik 2025's diagnosis of training-set clustering. As far as I found, it has not been shown as a hardware budget decomposition comparing the number of training circuits with shots per circuit.
- Finding (c), ZNE folding indistinguishable from a "garbage" control beyond about 30 CZ, is a negative control. No hardware ZNE benchmark found uses one. Existing ZNE hardware papers verify against exact values only where those can be simulated.

### Gaps
- I did not find a paper that sweeps CZ count on a single small device and compares CDR, ZNE and twirling with a null control.
- I did not find papers on bootstrap or cross-validation uncertainty for CDR or vnCDR. Statistical analyses of ZNE extrapolation exist, but none were retrieved this session.

---

## Q3. QML classifiers under noise: does mitigation help classification accuracy?

### Takeaway
The theory literature covers **trainability** (noise-induced barren plateaus; whether EM improves trainability) and **robust points or encodings** (LaRose & Coyle). The applied literature focuses on noise-aware *training* (QuantumNAT/RoQNN) or ensembles, not on post-hoc QEM of a frozen classifier. **No hardware study was found that separates "mitigation fixes the value ⟨O⟩" from "mitigation fixes the sign decision".** That separation is the core of finding (f).

### Cited Findings
- **[bg]** Wang, Fontana, Cerezo, Sharma, Sone, Cincio and Coles, "Noise-induced barren plateaus in variational quantum algorithms", *Nat. Commun.* 12, 6961 (2021), arXiv:2007.14384. — [arXiv:2007.14384](https://arxiv.org/abs/2007.14384)
- Wang, Czarnik, Arrasmith, Cerezo, Cincio and Coles, "Can error mitigation improve trainability of noisy variational quantum algorithms?", *Quantum* 8, 1287 (2024), arXiv:2109.01051. EM cannot remove the exponential scaling of noise-induced barren plateaus. Virtual distillation can make cost values *harder* to resolve. CDR can help where cost concentration is mild. — [Quantum 8, 1287](https://quantum-journal.org/papers/q-2024-03-14-1287/); [Sandia summary](https://overqc.sandia.gov/?p=359)
- LaRose and Coyle, "Robust data encodings for quantum classifiers", *PRA* 102, 032420 (2020), arXiv:2003.01695. The encoding determines which points keep their classification under noise ("robust points"). They bound the number of robust points via fidelities, and frame robust encoding as problem-specific error mitigation for classifiers. — [arXiv:2003.01695](https://arxiv.org/abs/2003.01695)
- Wang et al., QuantumNAT (arXiv:2110.11331, DAC 2022): the accuracy gap between noise-free simulation and IBMQ-Yorktown for MNIST-4 is over 60%. Noise-aware training gives over 94%, 80% and 34% accuracy for 2-, 4- and 10-class problems on hardware. — [arXiv:2110.11331](https://arxiv.org/pdf/2110.11331)
- Ensemble-learning error mitigation for shallow-circuit classifiers (bagging and boosting), arXiv:2301.12707. It reports accuracy gains, but I did not verify whether the experiments ran on hardware. — [arXiv:2301.12707](https://arxiv.org/abs/2301.12707)
- Real-time QEM during variational training on superconducting hardware, arXiv:2311.05680, targets training consistency and loss fidelity, not the decisions of a frozen classifier. — [arXiv:2311.05680](https://arxiv.org/abs/2311.05680)
- Error detection for variational QML (arXiv:2504.06775): ancilla error propagation limits the maximum achievable accuracy. — [ResearchGate entry](https://www.researchgate.net/publication/390638667_Variational_Quantum_Machine_Learning_with_Quantum_Error_Detection)
- Quek et al. 2024 extend the QEM limits to QML kernel estimation. — [arXiv:2210.11505](https://arxiv.org/abs/2210.11505v3)

### Inferences
- An observation that follows from LaRose & Coyle is that depolarizing-like noise shrinks ⟨O⟩ toward 0 without changing its sign, so a sign-based classifier is robust except near the margin. Finding (f) (hardware noise rarely flips decisions, and only near the boundary; mitigation fixes values more than decisions) is a direct empirical test of this on hardware, apparently the first.
- The simulation result that CDR restores decisions (132 fixed vs 32 broken across 3 datasets) together with the weaker hardware decision effect is an instance of the gap between simulation and hardware (see Q4). That makes it publishable as a negative or nuanced result.

### Gaps
- I found no paper that reports per-point decision flips (fixed vs broken counts) under ZNE or CDR for a frozen VQC on hardware.
- I did not search the quantum kernel mitigation literature in depth (for example error-mitigated kernel estimation on hardware). A follow-up search is warranted.

---

## Q4. Coherent vs incoherent error, ZZ crosstalk, and mismatch between calibration-based simulators and hardware

### Takeaway
Hardware-modeling papers attribute the residual gap between simulation and hardware to coherent errors, crosstalk and leakage. Calibration-derived digital twins are judged on raw outputs (Hellinger distance or fidelity). **No paper found tests whether such a model predicts the post-mitigation residual.** Finding (e) is exactly that: raw error is predicted well, the post-CDR residual is underestimated 1.9×, the residual is tied to CZ gates and not idle time, and twirling removes it.

### Cited Findings
- IQM 20-qubit simulation and benchmarking (arXiv:2508.04483): the mismatch is attributed to coherent over-rotations, leakage and crosstalk, with a worst Hellinger distance of 0.115. — [arXiv:2508.04483](https://arxiv.org/pdf/2508.04483)
- IBM digital twins built from downloadable calibration CSVs often agree best with hardware, but agreement depends on the device (arXiv:2603.14607). — [arXiv:2603.14607](https://arxiv.org/html/2603.14607v1)
- Calibration-driven transmon emulator ("digital twin") built from calibration data plus extra benchmarking circuits (arXiv:2504.08313). — [arXiv:2504.08313](https://arxiv.org/html/2504.08313v1)
- **[bg]** Georgopoulos, Emary and Zuliani, "Modeling and simulating the noisy behavior of near-term quantum computers", *PRA* 104, 062432 (2021), arXiv:2101.02109. — [arXiv:2101.02109](https://arxiv.org/abs/2101.02109)
- Twirling converts coherent errors into stochastic Pauli noise (Kim 2023 supplement). Coherent errors can accumulate quadratically with depth in the worst case (arXiv:2310.19416). — [arXiv:2108.09197](https://arxiv.org/pdf/2108.09197); [arXiv:2310.19416](https://arxiv.org/pdf/2310.19416)
- **[bg]** ZZ crosstalk in superconducting qubits: Sundaresan et al., "Reducing unitary and spectator errors in cross resonance with optimized rotary echoes", *PRX Quantum* 1, 020318 (2020). The arXiv id is not verified, so check it. — [PRX Quantum 1, 020318](https://journals.aps.org/prxquantum/abstract/10.1103/PRXQuantum.1.020318)

### Inferences
- CDR's linear (a·x+b) model can absorb global depolarizing-like shrinkage but not coherent, observable-dependent bias. That is consistent with a residual that twirling removes, and with the model underestimating the post-CDR residual because Aer calibration models are incoherent (Pauli or thermal-relaxation) by construction.
- Finding (e) gives a mechanistic explanation for why CDR's gain decays with CZ count without twirling and plateaus with it (finding a). This link between the two findings is not in the literature I found.

### Gaps
- I found no source that quantifies, on IQM Spark or ODRA-class hardware, the ZZ or coherent CZ error contribution to mitigation residuals.

---

## Q5. What is NOT yet established that these findings address? (Concrete gap and closest prior work)

### Takeaway
The established literature says that mitigation costs grow exponentially (theory) and that combined suppression and mitigation works at scale (IBM). It does **not** give an empirical, device-resolved **breakdown frontier**: the gain as a function of CZ count, with a null control and a calibrated error bar, separating the coherent and incoherent parts of the residual, and evaluated on the *decisions* of a classifier rather than only on expectation values. Each project finding fills a specific hole, listed below.

### Cited Findings (closest prior work for each gap)
1. **Gain decay per two-qubit gate, with vs without twirling (finding a).** Closest prior work: Kim 2023 (ZNE with twirling at scale, no decay curve) — [arXiv:2108.09197](https://arxiv.org/pdf/2108.09197); Russo 2023 (resource-normalized, not depth-resolved) — [arXiv:2210.07194](https://arxiv.org/abs/2210.07194); Quek 2024 (asymptotic worst case) — [arXiv:2210.11505](https://arxiv.org/abs/2210.11505v3).
2. **Hardware budget dominated by training-circuit count, not shots (finding b).** Closest prior work: Czarnik 2025 (training-set clustering, cost reduction) — [Quantum 9, 1727](https://quantum-journal.org/papers/q-2025-05-05-1727/); Bultrini 2023 (shot-budget regimes, simulation) — [arXiv:2107.13470](https://arxiv.org/pdf/2107.13470.pdf).
3. **ZNE folding vs null/"garbage" control (finding c).** Closest prior work: Giurgica-Tiron 2020 (folding validated in simulation) — [arXiv:2005.10921](https://arxiv.org/pdf/2005.10921); Anand/Temme 2023 (verified only to about 15 CNOT layers) — [arXiv:2306.17839](https://ar5iv.labs.arxiv.org/html/2306.17839); Mitiq warning about compilers undoing folds — [Mitiq](https://mitiq.readthedocs.io/en/stable/examples/zne-braket-ionq.html).
4. **vnCDR beating CDR does not carry over from simulation to hardware (finding d).** Closest prior work: Lowe 2021 (vnCDR 1.8× over CDR, numerical) — [arXiv:2011.01157](https://arxiv.org/pdf/2011.01157); Bultrini 2023 — [arXiv:2107.13470](https://arxiv.org/pdf/2107.13470.pdf).
5. **Calibration model predicts raw error but not the post-mitigation residual; the residual is CZ-coherent and removed by twirling (finding e).** Closest prior work: arXiv:2508.04483 (IQM, coherent errors blamed for the raw mismatch) — [link](https://arxiv.org/pdf/2508.04483); digital-twin studies — [arXiv:2603.14607](https://arxiv.org/html/2603.14607v1).
6. **Mitigation fixes values more than decisions on hardware; decision flips occur only near the margin (finding f).** Closest prior work: LaRose & Coyle 2020 (robust points, theory and simulation) — [arXiv:2003.01695](https://arxiv.org/abs/2003.01695); Wang 2024 (EM and trainability) — [Quantum 8, 1287](https://quantum-journal.org/papers/q-2024-03-14-1287/); QuantumNAT (noise-aware training, not post-hoc QEM) — [arXiv:2110.11331](https://arxiv.org/pdf/2110.11331).
7. **Calibrated LOO-CV error bar for CDR (finding g).** Closest prior work: no dedicated method found. CDR papers report improvement factors without a per-prediction uncertainty — [Quantum 9, 1727](https://quantum-journal.org/papers/q-2025-05-05-1727/); [arXiv:2005.10189](https://arxiv.org/pdf/2005.10189v1).
8. **DD+CDR (finding h, in progress).** Closest prior work: DD+ZNE on hardware — [IBM tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/combine-error-mitigation-techniques), [arXiv:2605.05256](https://www.alphaxiv.org/abs/2605.05256); DD survey **[bg]** — [arXiv:2207.03670](https://arxiv.org/abs/2207.03670). No DD+CDR hardware study found.
9. **Platform: an IQM star / 5-qubit central-qubit device.** Published QEM hardware benchmarks are dominated by IBM (heavy-hex), IonQ and Rigetti — [arXiv:2210.07194](https://arxiv.org/abs/2210.07194). IQM star papers focus on architecture and error detection, not QEM breakdown — [alphaxiv 2503.10903](https://alphaxiv.org/overview/2503.10903v2).

### Inferences
- Suggested gap statement for the paper: *"While the asymptotic cost of QEM is understood (Takagi 2022; Quek 2024) and large-scale demonstrations show mitigation working with error suppression (Kim 2023), no prior work maps, on one device, how the gain of standard mitigators decays with two-qubit gate count against a null control, separates the coherent CZ residual that calibration-based noise models miss, provides a calibrated per-prediction error bar for CDR, or measures whether mitigation changes the decisions (not just the expectation values) of a frozen variational classifier."*
- The strongest novelty claims, given what I could find: (i) the CZ-resolved decay with vs without twirling, together with the null control for ZNE; (ii) the model underestimating the post-CDR residual 1.9×, with the CZ-coherent residual removed by twirling; (iii) values vs decisions for classifiers on hardware. LOO-CV error bars are novel in application, but cross-validation is a standard statistical tool, so present it as a methodological contribution, not a new theory.
- Risk: the vnCDR-vs-CDR hardware result (d) could be specific to the ODRA noise level and depth range. Present it as "did not reproduce", not "vnCDR does not work".

### Gaps
- The search covered about 15 queries. There may be 2024–2026 hardware papers on CDR with twirling or on QML mitigation that these queries missed. Recommended follow-up searches: "error-mitigated quantum kernel hardware", "CDR twirling IBM Eagle depth", "noise-robust classification margin quantum hardware", and a check of the citations of Czarnik 2025 and LaRose & Coyle 2020.
- The **[bg]** bibliographic details (volumes, page numbers, and the Sundaresan and Georgopoulos arXiv ids) need verification.
