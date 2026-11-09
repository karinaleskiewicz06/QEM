# Literature map: combining QEM (ZNE, CDR) with error suppression (DD, Pauli twirling / RC) and their hybrids

Scope note: compiled 2026-10-25 from about 20 searches and fetches. "HW" means a hardware result; "SIM" means a simulation. Each claim carries its source date. Where I read only an abstract, I say so.

## Q1. vnCDR / unified data-driven QEM (Lowe, Hunter Gordon, Czarnik, Arrasmith, Coles, Cincio)

### Takeaway
vnCDR runs each near-Clifford training circuit and the target circuit at several noise levels (CNOT identity insertion, c ∈ {1,3,5}). It then fits a linear model with no intercept, which maps the vector of noisy values to the exact value. In practice this is a Richardson-like combination whose coefficients are learned from Clifford data rather than fixed by a polynomial. All results are SIM only. vnCDR beat ZNE by 2.7–20× and CDR by 1.5–1.8×. It costs about 100× ZNE in circuits and pays off only at ≥10⁴–10⁵ shots per circuit.

### Cited Findings
- arXiv 2011.01157 (v1 Nov 2020, v2 Aug 2021). Published as Phys. Rev. Research 3, 033098 (2021). Authors: Lowe, Hunter Gordon, Czarnik, Arrasmith, Coles, Cincio — [arXiv abs](https://arxiv.org/abs/2011.01157)
- Model. Each training circuit i gives features x_i = (x_{i,0..n}), the noisy expectations at the n+1 noise levels. The target y_i is the exact value of the near-Clifford circuit. The ansatz is g(x) = a·x with no constant term, fit by least squares. The mitigated estimate is a*·μ, where μ holds the target circuit's noisy values at each level. The authors motivate the missing intercept by analogy with Richardson combinations and by a Clifford-span argument (App. B), which they say is not a rigorous guarantee — [ar5iv 2011.01157](https://ar5iv.labs.arxiv.org/html/2011.01157)
- Noise scaling uses fixed identity insertion (FIIM): pairs of CNOTs are added after each CNOT. The levels are {1,3,5} for Ising/QAOA and {1,3,5,7,9} for random circuits. Levels above 5 did not help on Ising — [ar5iv](https://ar5iv.labs.arxiv.org/html/2011.01157)
- Training sets: 80 near-Clifford circuits with N=16 non-Clifford gates (Ising), and 100 circuits with N=20 (random circuits) — [ar5iv](https://ar5iv.labs.arxiv.org/html/2011.01157)
- Gains (SIM). The noise model comes from gate-set tomography of IBM Ourense, with no measurement error and no crosstalk.
  - 8-qubit QAOA/Ising energy (p=4, 27 instances): 33× better than unmitigated, 20× better than ZNE, 1.8× better than CDR.
  - 64-qubit hardware-efficient ansatz (p=6, MPO simulator): improvement over noisy of 2.7× for vnCDR, 1.8× for CDR and 1.0× for ZNE.
  - At p=16 the vnCDR improvement drops to 2.4×.
  — [ar5iv](https://ar5iv.labs.arxiv.org/html/2011.01157)
- Shot cost. On random circuits the totals are 5·N_s for ZNE, 101·N_s for CDR and 501·N_s for vnCDR, where N_s is shots per circuit. vnCDR systematically wins only for N_s ≳ 10⁴ (shallow circuits) or ≳ 10⁵ (deep). The main results assume infinite shots; App. F tests 10³–10⁵. The authors say hardware tests are still needed — [ar5iv](https://ar5iv.labs.arxiv.org/html/2011.01157)
- UNITED: Bultrini et al., arXiv 2107.13470 (Jul 2021); Quantum 7, 1034 (2023-06-06).
  - It unifies ZNE, CDR, vnCDR and virtual distillation (VD).
  - SIM uses a trapped-ion noise model, ≤10 qubits, and up to 128 Mølmer–Sørensen layers.
  - The best method depends on total shots. On random circuits: ZNE at 10⁵, vnCDR at 10⁶–10⁸, UNITED at 10¹⁰. On QAOA, VD is best at low budgets.
  - vnCDR and UNITED give about 20× over noisy on random circuits with Q=10, L=Q. At Q=4, L=64 they give 5–10× for 10⁷–10¹⁰ shots, where ZNE and VD barely help.
  - At Q=6–8, depth 16Q, no method improves on noisy.
  - Shots are split equally across all circuits: (n+1)(N_t+1) circuits for vnCDR. The authors state equal splitting is likely suboptimal.
  - Learning-based methods are fragile to shot noise at high noise, because the noisy training values cluster together.
  — [ar5iv 2107.13470](https://ar5iv.labs.arxiv.org/html/2107.13470); [Quantum](https://quantum-journal.org/papers/q-2023-06-06-1034/)

### Inferences
- For a 5-qubit star device with about 10⁴ shots per circuit, vnCDR is near its break-even. The ~100× circuit multiplier is the binding cost. Data reuse could cut that multiplier: the same training set at several noise levels, shared across the frozen classifier's evaluation points.
- vnCDR's noise scaling (CNOT insertion) is the same knob as the project's P5 identity insertion. A vnCDR variant on the frozen star therefore reuses existing infrastructure.

### Gaps
- I found no vnCDR hardware demonstration in this search. Such demonstrations may exist, but none surfaced.
- I found no study of non-uniform (Neyman-style) shot allocation across noise levels and training circuits for vnCDR. Bultrini et al. explicitly leave it open.

## Q2. Other CDR / learning-based extensions

### Takeaway
CDR has been made cheaper (frugal CDR, about 10× fewer shots, HW on IBM Toronto, 2022/2025). It has been combined with echo verification (EVCDR, HW, 35 sites, 2025) and generalized by ML-QEM (random forests beat ZNE on HW with about 2× less runtime, 2024). None of these benchmark CDR with twirling or DD as a controlled factor.

### Cited Findings
- Frugal CDR: Czarnik, McKerns, Sornborger, Cincio, "Improving the efficiency of learning-based error mitigation". arXiv 2204.07109 (Apr 2022); Quantum 9, 1727 (2025).
  - Training circuits are chosen carefully and problem symmetries are exploited.
  - Cost is about an order of magnitude below original CDR at the same accuracy, and 10× better than unmitigated with a total budget as small as 2×10⁵ shots.
  - HW: XY-model long-range correlators on IBM Toronto. LiH is SIM (Ourense noise model).
  - Source: abstract only.
  — [arXiv](https://arxiv.org/abs/2204.07109)
- Echo-Verified CDR (EVCDR): Weaving, Ralli, Love, Succi, Coveney. Quantum 9, 1732 (2025-05-05).
  - HW on a superconducting device: Ising time evolution, up to 35 sites, up to 173 entangling layers.
  - The page gives no error-reduction numbers, and twirling and DD are not reported as used.
  — [Quantum](https://quantum-journal.org/papers/q-2025-05-05-1732/)
- ML-QEM: Liao, Wang, Sitdikov, Salcedo, Seif, Minev (IBM). Nature Machine Intelligence 6, 1478–1486 (2024); arXiv 2309.17368.
  - Models: OLS, random forest (RF), MLP and GNN. Features are noisy expectations, gate counts, the observable and device noise parameters.
  - RF was best and significantly beat digital ZNE (p-values down to 10⁻⁷¹ in SIM).
  - HW on ibm_algiers (Trotter TFIM): RF beat ZNE at every step (max p = 3.1×10⁻¹⁰). Overall cost was about 40% lower (about 3,000 vs 5,000 circuits) and runtime about 50% lower, against ZNE with 2 noise factors.
  - Break-even: n_train/n_test < (m−1)/m, where m is the number of ZNE executions per test circuit.
  - Training data on HW: 50 training circuits per Trotter step, 10⁴ shots each.
  - Training on fewer than about 2% of 4,095 Pauli observables beat ZNE on unseen observables (SIM, 6 qubits).
  - With coherent noise added in the extrapolation regime, no model mitigated well (SIM).
  - "Mimicry" ran on 100 qubits on ibm_brisbane, with Pauli twirling (5 twirls) and ZNE+TREX as reference. It reproduced ZNE at about 25% lower total cost and 50% lower runtime, but cannot beat the method it mimics.
  - CDR was not benchmarked. The authors argue CDR is single-circuit and single-observable.
  — [arXiv html v2](https://arxiv.org/html/2309.17368v2)
- Finite-shot CDR vs PEC (arXiv 2606.21686, 2026). CDR can have lower target-shot variance than PEC. It keeps a calibration floor when the training and target noise responses differ. Source: search snippet only — [emergentmind](https://www.emergentmind.com/papers/2606.21686)
- Original CDR: Czarnik et al., arXiv 2005.10189 (2020) — [arXiv](https://arxiv.org/pdf/2005.10189)

### Inferences
- A frozen classifier is a natural fit for ML-QEM/CDR-style amortization. The circuit structure is fixed and only the features change, so one learned map can serve many evaluation points. This is the strongest "data reuse" angle, and it corresponds directly to Liao's break-even inequality.
- Coherent-error sensitivity of learned models (Liao) argues for twirling the training and target circuits together. In "twirled CDR", twirling converts the noise to Pauli form so the linear CDR ansatz is better justified. I found no paper that tests this.

### Gaps
- Not covered by fetched sources: Strikis et al. 2021 (learning-based QEM, PRX Quantum), energy-sampling CDR, Bayesian or regularized CDR, multi-observable CDR, and noise-aware training. Those searches returned nothing usable. The report writer should not cite specifics for these without verification.

## Q3. DD + twirling, and DD/twirling inside ZNE stacks (IBM resilience)

### Takeaway
Correction to the brief: Kim et al. 2023 (Nature, 127 qubits) used Pauli twirling, a learned sparse Pauli–Lindblad model and ZNE by amplifying the learned rates (the forerunner of PEA). Dynamical decoupling is not mentioned in its methods. The best DD+twirling+ZNE evidence is Kim et al. 2021 (26 qubits). There, twirling added value on top of DD, but the contributions were shown only qualitatively. IBM documentation states DD can hurt densely packed circuits.

### Cited Findings
- Kim et al. 2023, Nature 618, 500–505 (127-qubit Eagle, HW).
  - Pauli twirling around every CNOT layer, and a sparse Pauli–Lindblad model learned per twirled layer, including crosstalk.
  - ZNE by scaling the learned Pauli rates, with gain G = 1+α ∈ {1, 1.2, 1.6} or {1, 1.3, 1.6}. Exponential extrapolation is the main method and linear is shown for comparison.
  - About 2,400 twirl instances per gain × 64 shots, about 614k samples in total, about 5 min of device time.
  - DD is not mentioned, and PEC was rejected on sampling-overhead grounds.
  - At the Clifford point, ZNE "greatly improves agreement, albeit with a small bias" out to 60 CNOT layers.
  — [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC10266970/)
- Kim et al. 2021, arXiv 2108.09197 (HW, ibmq_kolkata, 26-qubit quench).
  - Stack: DD + Pauli twirling + ZNE with pulse stretching (c = 1, 1.6, 2.0, linear extrapolation).
  - DD extends visible coherent dynamics; more elaborate DD sequences gave no discernible gain.
  - Twirling improves agreement further and saturates at about 8 instances.
  - Contributions are qualitative only (Figs. S2–S4). Shots: 10⁵ per stretch factor.
  - Mitigated magnetization beat PEPS (D=4) after more than 6 Trotter steps; the weight-2 ⟨ZZ⟩ observable showed no clear advantage.
  — [ar5iv](https://ar5iv.arxiv.org/html/2108.09197)
- IBM Qiskit Runtime documentation (current, accessed 2026-10).
  - DD helps circuits with idle gaps and "may worsen performance" on densely packed ones.
  - Twirling samples randomized instances. TREX adds a small calibration overhead.
  - ZNE defaults to 3 noise factors (about 3× overhead) using digital gate folding of two-qubit gates.
  - PEA needs a noise-learning stage and is "often the best choice" at utility scale.
  - PEC overhead scales as γ², and γ grows exponentially with depth.
  — [IBM guide](https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-and-suppression-techniques); [configure EM](https://quantum.cloud.ibm.com/docs/guides/configure-error-mitigation); [combine-techniques tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/combine-error-mitigation-techniques)
- 2026 HW stacks:
  - arXiv 2605.05256 (dynamic circuits, IBM): DD+ZNE is effective against mid-circuit-measurement and feed-forward errors. The authors note that noise scaling for dynamic circuits needs care — [alphaxiv](https://www.alphaxiv.org/abs/2605.05256)
  - arXiv 2606.19027 (mid-circuit resets): the full DD+TREX+ZNE+twirling stack, with twirling used to turn coherent over-rotations into Pauli noise — [arXiv](https://arxiv.org/pdf/2606.19027)
  - Both are search snippets only, with no per-component ablation numbers.
- Effective quantum volume study: global and local unitary folding with fractional scale factors, combined with DD, gave gains over the vendor value. Search snippet only — [arXiv 2306.15863](https://arxiv.org/abs/2306.15863)
- DD and topology: arXiv 2506.18010 (UMD, Jun 2025) reports that DD-protected fixed-coupler devices can outperform tunable-coupler devices, on bipartite topologies. Snippet only — [QuICS](https://quics.umd.edu/publications/crosstalk-robust-dynamical-decoupling-bipartite-topology-quantum-processors)
- DD control-error pitfall: arXiv 2511.12227 (Nov 2025) finds DD with control errors can misestimate decoherence times, and proposes Hadamard phase cycling — [arXiv](https://arxiv.org/abs/2511.12227v2)

### Inferences
- **DD × folding conflict (my inference; I found no paper that tests it).** Gate folding multiplies the two-qubit gates. Inserted DD then sees different idle windows at each scale factor, so idle noise does not scale by the same factor as gate noise. This breaks the ZNE assumption of uniform scaling. On a star device, the hub serializes CZs and the leaf qubits idle, so this effect is likely large. Pulse stretching (Kim 2021) or PEA-style rate scaling avoids it.
- On IQM, DD is a pulse-level or idle-gate insertion. Whether Resonance exposes it for the 5-qubit star is a practical question I did not verify.

### Gaps
- I found no paper that quantitatively ablates DD × twirling × ZNE on equal shots: the gain of each layer, per depth.
- I found no DD experiments on IQM star (central-resonator) hardware. IQM's Star reports use NRE and ZNE and do not mention DD — [TQI 2025-04-30](https://thequantuminsider.com/2025/04/30/iqm-star-topology-amplifies-all-to-all-qubit-connectivity-through-a-central-resonator/)

## Q4. Twirling + ZNE (PEA) and twirling + CDR

### Takeaway
Twirling plus ZNE is now standard at utility scale: Kim 2023, IBM PEA, Liao's mimicry runs, and the 2026 benchmark-circuit work. Twirling plus CDR or vnCDR appears to be untested. I found no paper that combines them with a controlled comparison.

### Cited Findings
- PEA and Pauli–Lindblad learning: van den Berg & Wocjan, "Techniques for learning sparse Pauli-Lindblad noise models", Quantum 2024-12-10, arXiv 2311.15408. It adds Pauli-rotation twirling, graph-coloring basis selection and covering arrays, which make learning higher-weight noise terms cheaper — [Quantum](https://quantum-journal.org/papers/q-2024-12-10-1556/)
- Harris, Lively, Schuhmacher, arXiv 2603.10224 (Mar 2026).
  - "Verifiable benchmark circuits" mirror the native-gate structure of the application circuit. They are used to measure and remove the bias of ZNE; a related variant is benchmarked-noise ZNE (bnZNE).
  - The stack includes twirling (32 twirls per noise-scaled circuit), minimal XX DD and TREX, according to the search snippet.
  - Up to 15% fidelity improvement over standard QEM, on 100-qubit IBM circuits with ≤2,000 entangling gates (HW).
  - Conceptually this is close to CDR: classically verifiable, structure-matched training circuits used to correct ZNE.
  — [arXiv abs](https://arxiv.org/abs/2603.10224); [pdf snippet](https://arxiv.org/pdf/2603.10224)
- A search for "CDR + Pauli twirling" returned no direct combination paper (search 2026-10) — [frugal CDR](https://arxiv.org/abs/2204.07109), [EVCDR](https://quantum-journal.org/papers/q-2025-05-05-1732/)

### Inferences
- bnZNE (2026) is the closest prior art to "vnCDR with twirling" on hardware. Any proposal must distinguish itself from it. Possible differences: a small star topology, a classifier workload, equal-shot controls, and DD on idle leaves.

### Gaps
- I did not read the bnZNE results section: the per-component contributions and the exact extrapolation correction.

## Q5. Known pitfalls and cost bounds

### Takeaway
There are four relevant cautions:
- Deep-circuit ZNE can show artefactual "improvement" that a matched-cost garbage-folding control reproduces (IQM HW, 2026).
- Richardson ZNE has a finite-shot MSE boundary that depends on the class of observable (2026).
- Worst-case sample cost of all these methods is superpolynomial even at shallow depth (Quek et al. 2024).
- Learning-based methods are fragile to shot noise at high noise (UNITED).

### Cited Findings
- Köster & Mauerer, "Benchmarking Error Mitigation: Artefactual Improvements in Zero-Noise Extrapolation", arXiv 2607.09360 (Jul/Aug 2026, IEEE QCE 2026).
  - Once noise amplification destroys the signal, Richardson ZNE "collapses into a fixed rescaling of a single noisy measurement". The apparent gain then does not depend on the amplification level.
  - A matched-cost garbage-folding control showed a larger apparent gain than genuine folding.
  - On IQM Euro-Q-Exa HW, ordinary folding overshot the ideal value by up to 21% as depth eroded the signal.
  - The authors propose a garbage-folding negative control, a zero-cost diagnostic and a reporting checklist.
  — [arXiv](https://arxiv.org/abs/2607.09360)
- Scavino Alfaro, "A finite-shot mean-squared-error boundary for Richardson zero-noise extrapolation", arXiv 2605.08251 (May 2026, v2 Oct 2026).
  - Gives the noise strength at which ZNE beats unmitigated MSE at a fixed budget B.
  - The boundary shrinks as B⁻¹ for deterministic stabilizer measurements and as B⁻¹ᐟ² for nonzero-variance (Hamiltonian or variational) measurements.
  - Shot allocation across scales changes only constants, not the exponent.
  - SIM: GHZ and QAOA on Aer. HW: on IBM, ZNE lowered MSE at equal shots in 75/101 instances.
  — [arXiv](https://arxiv.org/abs/2605.08251)
  - Note: the abstract does not mention "kappa" or "Neyman" allocation. If the brief's "kappa/Neyman" framing comes from the body text, I did not verify it.
- Quek, Stilck França, Khatri, Meyer, Eisert, Nature Physics 20, 1648–1658 (2024); arXiv 2210.11505.
  - In the worst case, superpolynomially many samples are needed even at shallow depth.
  - This covers ZNE, CDR, PEC and VD, and is exponentially tighter than earlier bounds.
  - It is a worst-case result and does not apply to QEC.
  — [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11473368/); [arXiv](https://arxiv.org/abs/2210.11505v3)
- Takagi, Endo, Minagawa, Gu, "Fundamental limits of quantum error mitigation", npj Quantum Information 8, 114 (2022). Not fetched in this session; the citation is from background knowledge and should be verified. Commonly cited for sampling-overhead lower bounds — [arXiv 2109.04457](https://arxiv.org/abs/2109.04457)
- Learning-based QEM is fragile to shot noise when noisy training values cluster at high noise (UNITED, 2023) — [ar5iv](https://ar5iv.labs.arxiv.org/html/2107.13470)
- vnCDR's zero-error argument is "motivational" and not rigorous (2021) — [ar5iv](https://ar5iv.labs.arxiv.org/html/2011.01157)

### Inferences
- A frozen variational classifier measures a nonzero-variance observable (Z on hub, or mean-Z). On Scavino Alfaro's results, the ZNE benefit boundary therefore shrinks only as B⁻¹ᐟ², which is unfavorable at the project's small credit budget.
- vnCDR, which is linear in multi-scale features, could be checked for the same Köster–Mauerer collapse. If its learned coefficients put all weight on one scale with a fixed rescaling, it is the same artefact. A garbage-training-data control would be a novel check.

### Gaps
- Kappa/Neyman shot allocation is not confirmed in the 2605.08251 abstract. I found no paper that does optimal allocation for vnCDR.

## Q6. Untested combinations on small star/hub topologies with equal-shot controls

### Takeaway
In the fetched sources, no study:
1. runs vnCDR or CDR with Pauli twirling on hardware;
2. resolves DD's interaction with gate-folding ZNE on a star (hub-serialized) device;
3. applies any of these to a frozen variational classifier;
4. reports equal-total-shot comparisons with a garbage-folding negative control on IQM star hardware.

Each of these is a candidate novelty.

### Cited Findings
- The hardware studies of combinations found here run on IBM heavy-hex devices (Kim 2021/2023, Liao 2024, bnZNE 2026). The UNITED benchmark is a trapped-ion SIM. — [Kim 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10266970/), [Kim 2021](https://ar5iv.arxiv.org/html/2108.09197), [Liao](https://arxiv.org/html/2309.17368v2), [bnZNE](https://arxiv.org/abs/2603.10224), [UNITED](https://ar5iv.labs.arxiv.org/html/2107.13470)
- IQM HW appears for the ZNE artefact study (Euro-Q-Exa) and in IQM Star reports using NRE+ZNE. Neither uses DD or twirling with CDR. — [Köster & Mauerer](https://arxiv.org/abs/2607.09360), [TQI](https://thequantuminsider.com/2025/04/30/iqm-star-topology-amplifies-all-to-all-qubit-connectivity-through-a-central-resonator/)
- Equal-shot controls exist in Bultrini (total-shot budgets), Scavino Alfaro (equal-budget MSE) and Köster–Mauerer (matched-cost garbage folding). None combines DD, twirling and CDR. — sources above
- ML-QEM's break-even inequality gives a ready cost criterion for amortized training — [Liao](https://arxiv.org/html/2309.17368v2)

### Inferences (candidate novel combinations for the 5-qubit IQM star, PRX/CZ, virtual Z)
1. **Twirled vnCDR with shared training data.** CZ twirling is Clifford, and Paulis on PRX are cheap. Twirl both the near-Clifford training circuits and the target circuits, scale noise by CZ-pair insertion (the existing P5 infrastructure), and amortize one training set over all classifier evaluation points.
   - Controls: equal total shots against ZNE alone, CDR alone and untwirled vnCDR, plus garbage-folding and garbage-training negative controls.
2. **DD-aware noise scaling on the hub.** Compare gate-folding ZNE with and without leaf-qubit DD, and with DD re-inserted per scale factor. This tests the uniform-scaling assumption, and the hub serialization of a star topology makes it likely to matter there.
3. **Neyman-type shot allocation across (noise level × training circuit) for vnCDR.** The open item named by Bultrini et al.
4. **Classifier-specific metric.** Report the sign or accuracy flip rate alongside the ⟨O⟩ error. No prior paper covers combination-QEM for QML classifiers.

### Gaps
- I did not verify which IQM Resonance features (DD, twirling) the star backend exposes natively, or whether they must be inserted manually as gates.
- Possible prior art not surfaced in this search: QML-classifier QEM papers, and Mitiq-based CDR+DDD studies. Mitiq supports both CDR and DDD, but I did not fetch any paper that combines them.
