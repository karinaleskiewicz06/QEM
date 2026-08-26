# Month 2 Work Plan — Topology-aware evaluation of error mitigation and logical-qubit overhead

**Karina Leśkiewicz · KN Axion · September 2026**
Companion to `plan.md` (full project plan) and `raport_month_1.tex` (Month 1 report).

---

## 0. Where Month 1 left off (starting point)

Month 1 already completed most of what the original plan scheduled as the "Tier A"
campaign, so Month 2 is **not** starting the hardware work from scratch — it extends a
working, validated pipeline. Concretely, on ODRA (5-qubit star) we already have:

- A reusable QEM toolchain: calibrated Aer noise model (`noisy_sim.py`), in-repo ZNE
  (`zne_dryrun.py`), REM, per-pattern trained classifiers (`train_patterns.py`),
  frozen noiseless reference (`freeze_reference.py`).
- **Two independent QPU routing ladders** — `two_curves` (`hardware_results.csv`) and
  Banknote (`banknote_hardware_fullfold.csv`, `banknote_hardware_cv_d6.csv`) — each with
  raw → +REM → +ZNE, mirror fidelity, and a DD on/off ablation.
- Established findings: ⟨O⟩-error rises monotonically with transpiled CZ; ZNE recovery
  decays with CZ and becomes marginal around **85–90 CZ**; **DD is a negative result** on
  Spark; a single per-gate fidelity model fits all 13 QPU points (~0.86%/CZ, ~0.61%/1q).

**Key structural fact that shapes Month 2:** the entire pipeline is hardcoded to the star.
`star_coupling_map` is used in `noisy_sim.py` and `routing_sweep.py`; `PHYS=["QB3","QB1",
"QB2","QB4","QB5"]` and the ODRA calibration mapping (hub QB3) are baked into
`run_hardware.py` / `collect_odra_calibration.py`. On a star there is **no layout freedom**
(every outer qubit is distance-1 from the hub, distance-2 from every other), so the
"optimal vs. adverse mapping" experiment that the supervisor plan makes central is
*degenerate on ODRA* and only becomes meaningful once we port to a square-lattice device.
This makes the cross-topology port (W1) a prerequisite for the headline mapping
experiment (W2), not an optional extra.

---

## 1. Objective (Month 2)

Empirically locate where the theoretical gain of error mitigation (and of a near-term
"logical-ish" encoding) is cancelled by hardware routing overhead — and show how that
frontier **moves with topology and with layout choice**. Deliver a relationship with
quantified uncertainty (recovered accuracy / mean-value error / mirror fidelity vs.
transpiled 2q cost and topological distance), across ODRA (star), Garnet (20q lattice)
and Emerald (54q lattice), plus optimal-vs-adverse mapping on the lattice devices.

**Framing — a comparative study of QEM vs. near-term QEC under routing overhead.** The
through-line is not one method but a *comparison* of error-handling strategies as a function
of topology and 2q cost, meant as guidance for **future architectures**: which strategy is
worth its overhead, and where. The methods under comparison:

| Family | Method | Native overhead axis | Status |
|---|---|---|---|
| QEM | REM + ZNE | extra shots (noise-amplified circuits) | validated M1 (star); port to lattice (W4) |
| QEM | CDR | near-Clifford training circuits + shots | **core** (W4b) |
| QEC-lite | `[[4,2,2]]` error **detection** + post-selection | qubits + discarded shots | **core** (W5), on lattice |
| QEM | DD | pulses | **negative result** on Spark (M1) — reported, not a live method |

Each method is scored on the same quality axes — recovered mean-value error / accuracy and
mirror fidelity — **and on one common cost currency: total wall-clock QPU shots to reach a
fixed target accuracy** (see below). Because the native overheads are in different units
(ZNE ⇒ shots, CDR ⇒ training circuits + shots, `[[4,2,2]]` ⇒ qubits + discarded shots),
converting each to "shots-to-target" is what makes the methods commensurable on one figure.
The output is a per-topology "which method pays, and up to what 2q budget" comparison, not a
single threshold.

**Common cost currency — shots-to-target.** For every (method, device, routing level) we
report the **effective QPU shots needed to reach a target accuracy / ⟨O⟩-error tolerance**,
folding in each method's real cost: ZNE's noise-amplified copies, CDR's training-circuit
budget, and `[[4,2,2]]`'s post-selection acceptance rate (kept shots = raw shots ×
acceptance). This single axis lets the final figure rank methods honestly instead of
comparing raw accuracies at unequal cost. Defined once in W3, used in W4/W4b/W5 and plotted
in W7.

---

## 2. Coverage of the official Month-2 deliverables (supervisor PDF)

| Official deliverable (PDF §4, Miesiąc 2) | Covered by | Status entering M2 |
|---|---|---|
| Run **optimal-mapping** experiment (physically close qubits) | W1 + W2 | needs lattice port |
| Run **adverse-mapping** experiment (dispersed allocation) | W1 + W2 | needs lattice port |
| Measure/estimate **SWAP count, depth, 2q count, mean value, fidelity** | W2 + W3 | pipeline exists (star); generalize |
| Quantify **correlation: topological distance ↔ SWAP ↔ degradation** | W3 | new analysis |
| Results for physical / encoded-logical / optimal / adverse variants | W2 + W5 | encoded-logical = [[4,2,2]] post-selection **on Garnet/Emerald**; placement fused with optimal/adverse |
| **Quantitative topological-overhead analysis** | W3 | new |
| **Publication-ready figure set** (qubit distance ↔ SWAP ↔ quality) | W7 | extend `make_figures.py` |
| **Final report** on practical limits of mitigation/encoding | W7 | extends M1 report |

The richer framing from `plan.md` (ZNE breakdown region, collapse toward the maximally
mixed state / barren-plateau connection) is folded into W4; the ZNE-vs-CDR-vs-[[4,2,2]]
method comparison is now core (W4b, W5), scored on the common shots-to-target axis.

---

## 3. Workstreams

### W1 — Cross-topology port: generalize the pipeline from star to square lattice *(enabler; do first)*
The single biggest engineering task. Replace star-specific assumptions with a
device-driven coupling map so the *same* logical VQC runs on Garnet/Emerald.

- Generalize `star_coupling_map` → a `device_coupling_map(name)` (star | lattice-4×5 |
  lattice-6×9) and thread it through `noisy_sim.py` (noise model + AerSimulator
  `coupling_map`) and `routing_sweep.py` (transpile target).
- Generalize `run_hardware.py`: replace the hardcoded `PHYS` list with a per-device
  logical→physical layout, and drive `native_transpile` with an explicit `initial_layout`
  (needed for W2). Keep the mean-Z readout (permutation-invariant); for single-Z readouts
  keep deriving the wire from `final_index_layout()` (the Month-1 banknote bug fix).
- Generalize calibration collection: `collect_odra_calibration.py` hardcodes QB1–5 and the
  QB3 hub edges. Add `collect_iqm_calibration.py` (or parameterize) to pull Garnet/Emerald
  T1/T2, 1q/2q/readout error and the real coupling map from the device.
- **Deliverable:** identical `two_curves` VQC transpiled + simulated on all three devices;
  `routing_ladder_{odra,garnet,emerald}.csv` with (layout → transpiled CZ, SWAP, depth).

### W2 — Optimal vs. adverse mapping experiment *(official headline)*
On the lattice devices, layout choice is a real knob. Hold the logical payload fixed and
vary only the initial layout:

- **Optimal:** compact, physically adjacent qubit set (minimal routing / SWAP).
- **Adverse:** dispersed allocation across the lattice (forces long routing paths / SWAPs).
- Transpile each at fixed optimization level & seed; record transpiled CZ, **inserted SWAP
  count**, depth. Run inference + REM + ZNE on QPU; also mirror fidelity per layout.
- Run on Garnet at bracketing points; reserve Emerald for 1–2 confirmatory points (queue-limited).
- **Deliverable:** paired optimal/adverse results per device — mean-value error, accuracy,
  mirror fidelity — quantifying the quality cost of ignoring native topology.

### W3 — Topological-overhead quantification *(official analysis deliverable)*
Turn the mapping data into the correlation the plan asks for.

- Define a **topological-distance metric** for a layout (e.g. sum/mean of shortest-path
  distances over the logical edges the ansatz needs), computed from the device coupling map.
- Regress degradation (ΔF, Δ⟨O⟩-error) against topological distance and against transpiled
  SWAP/CZ count; report correlation coefficients with uncertainty.
- Cross-check against the Month-1 per-gate fidelity model (0.86%/CZ, 0.61%/1q): does the
  same model predict the lattice points, or does topology add a residual?
- **Define the common cost currency here** (`shots_to_target(method, device, level)`): the
  effective QPU shots to reach a fixed accuracy / ⟨O⟩-error tolerance, folding in ZNE's
  amplified copies, CDR's training-circuit budget, and `[[4,2,2]]`'s acceptance rate. One
  helper, reused by W4/W4b/W5 so every method reports cost in the same unit.
- **Deliverable:** quantitative topological-overhead analysis + the shots-to-target
  helper + figures (W7).

### W4 — Threshold characterization with drift *(uncertainty, not a constant)*
- Repeat the ODRA routing ladder over **≥3 separate calibration windows** to turn the
  85–90 CZ breakdown estimate into a band, not a point (Month 1 already saw a fold-1
  baseline swing 0.673→0.607 across two days — direct evidence drift matters).
- Locate the **breakdown region** (ZNE fit residuals / error bars diverge) and the
  **collapse** toward the maximally mixed state (output/mean-value variance → 0), tying the
  endpoint to noise-induced barren-plateau theory (Wang et al. 2021).
- Compare linear / Richardson / exponential extrapolators; report which breaks first.
- **Deliverable:** "recovered accuracy & variance vs. 2q cost" curves with error bands and
  a documented breakdown/collapse region per topology.

### W4b — Clifford Data Regression (CDR) *(promoted to core: the second QEM method)*
The natural counterpart to ZNE: unlike ZNE it does **not** amplify noise, so "which method
breaks first under routing" is a genuine result rather than a foregone conclusion.

- Scaffold near-Clifford training-circuit generation (replace non-Clifford `R_y(x)` with
  nearby Clifford angles so the ideal value is classically computable) and fit the CDR
  regression that maps noisy → corrected ⟨O⟩. Reuses the existing routed circuits and the
  frozen noiseless reference.
- Run CDR under the **identical routing sweep** as ZNE on ODRA (full) and at 1–2 Garnet
  points; score on the same quality axes **and** the shots-to-target currency (W3), counting
  the training-circuit budget as part of CDR's cost.
- Report **which extrapolation/regression breaks first** with routing cost, and whether CDR
  buys resilience at high CZ where ZNE fades (M1 showed ZNE → ~1.04× by 87 CZ).
- **Deliverable:** ZNE-vs-CDR resilience comparison vs. 2q cost, on the common cost axis.

### W5 — "Logical-ish" layer: [[4,2,2]] error detection + post-selection **on Garnet/Emerald (not ODRA)**
The report's chosen near-term stand-in for logical protection (full QEC rejected: 5×13=65 >
54 qubits, device 2q error ~1.9% near threshold, non-Clifford rotations not transversal).

**Why the lattice devices, not the star.** `[[4,2,2]]` needs 4 data qubits (+ ancilla) —
on the 5-qubit star that leaves no slack, and every data–data gate routes through the hub,
so the star's forced-SWAP overhead would swamp any encoding benefit and pre-decide research
question 2 as a negative (an unfair test). On a **square lattice** the 4 data qubits sit in
a **compact 2×2 plaquette** with native nearest-neighbor gates, giving the encoding a fair
chance; Garnet/Emerald also have the qubit budget for the code block *plus* payload
(Emerald can host several blocks — the "strong success" direction).

- **Scope (mid):** embed **one code block inside the small VQC** so a couple of qubits are
  protected **end-to-end** (state-prep → the Clifford parts of the payload → readout), with
  detection + post-selection around that segment. **Garnet = primary**, **Emerald = 1–2
  confirmatory points**. Honest framing: the data-dependent `R_y(x)` rotations are
  non-Clifford and stay **unprotected**, so the encoded region is the Clifford envelope, not
  the whole VQC — but the comparison is now against the *same* running VQC, not a toy segment.
- Implement the `[[4,2,2]]` circuit; **detect (not correct)** errors and discard flagged
  shots. Prefer the **ancilla-free** variant: measure the 4 data qubits destructively and
  compute the `XXXX`/`ZZZZ` parity classically, post-selecting on it (Vuillot,
  arXiv:1705.08957). Falls back to an explicit parity ancilla if needed.
- **Fuse with W2:** run the code block at **optimal** placement (compact plaquette) vs.
  **adverse** placement (dispersed across the lattice) — so physical-vs-encoded and
  optimal-vs-adverse become one 2×2 experiment, not two.
- **Prototype in the calibrated simulator first** (and optionally an ODRA dry run using the
  hub as a weight-4 ancilla) so scarce Garnet/Emerald time is spent only on the final
  comparison. **Report the post-selection acceptance rate** as the encoding's cost, and
  budget extra shots to keep statistics after discards.
- Treat a clean negative (overhead > benefit at these error rates) as a valid outcome.
- **Deliverable:** encoded-vs-physical comparison on the lattice (optimal & adverse
  placement), with acceptance rate — answering research question 2.

### W6 — Close Month-1 loose ends
- **Native-ring collapse double-check** (report §5.6 flags this explicitly as "wymaga
  double-checku" / to be resolved in Month 2): re-measure the `native`/`odra` ansatz at L=6
  to settle whether the source-paper ring collapse reproduces once drift is controlled.
- Fold in the 5-fold CV artifacts already produced (`banknote_hardware_cv_d6.csv`,
  `run_cv_banknote.py`) and confirm the uncommitted `run_cv_banknote.py` is finalized.
- Repo hygiene: commit outstanding changes, archive stale degree=2 models, `.mplcache/`.

### W7 — Synthesis: figures, report, reproducible release
- Extend `make_figures.py`: per-tier accuracy vs. 2q cost, cross-topology overlay,
  optimal-vs-adverse panels, topological-distance correlation plot, variance-collapse plot.
- Write the **hardware-aware compilation guideline** (recommended 2q budget per topology
  for ZNE to remain worthwhile) — the practical takeaway.
- Final report (extends `raport_month_1.tex`): methodology, cross-topology results,
  limitations, reproduction instructions; reproducible code release + archived datasets.

---

## 4. Indicative schedule (4 weeks)

| Week | Focus | Concrete output |
|---|---|---|
| 1 | W1 port + W6 loose ends | lattice coupling maps wired into sim/transpile/hardware; Garnet/Emerald calibration pulled; native-ring re-check queued |
| 2 | W2 mapping on Garnet + W4 extra ODRA window + W3 shots-to-target helper + **W4b CDR scaffold** + **W5 prototype in sim** | optimal/adverse ladders on Garnet; drift window #2; common cost currency defined; CDR fitting on the ODRA sweep; `[[4,2,2]]` + post-selection validated in simulator |
| 3 | W2 Emerald bracketing + W3 analysis + **W4b CDR on Garnet point** + **W5 on Garnet (optimal & adverse)** | cross-topology dataset; topological-distance correlation; ZNE-vs-CDR resilience; encoded-vs-physical + acceptance rate |
| 4 | W5 Emerald confirmatory point + W4 close drift bands + W7 synthesis | method-comparison figures on the shots-to-target axis; compilation guideline; final report draft; code release |

*(Tier B/C queue access is the main scheduling risk — see below. Do full sweeps on ODRA;
use Garnet/Emerald only for bracketing/confirmatory points.)*

---

## 5. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Limited Garnet/Emerald queue time | Full ladders on ODRA; lattice devices only for bracketing optimal/adverse points |
| Calibration drift confounds the threshold | ≥3 windows, report error bands not a constant (already evidenced in M1) |
| Port introduces silent layout/readout bugs | Reuse M1 discipline: smoke test prints raw counts + bit order; derive readout wire from transpiled layout |
| [[4,2,2]] overhead swamps benefit | Run it on the lattice (compact plaquette), not the star; pre-register as possibly-negative; report acceptance rate; keep to 1–2 logical qubits |
| Post-selection discards inflate shot cost on scarce Garnet/Emerald | Prototype + tune acceptance in simulator first; budget extra shots; prefer ancilla-free classical post-selection |
| CDR now core → added scope | Bound it: CDR on the *existing* ODRA sweep + 1–2 Garnet points only; reuse routed circuits + frozen reference; MNIST / extra ansätze stay optional |
| Methods not comparable (different overhead units) | Convert every method to the shots-to-target currency (W3) before plotting; never compare raw accuracy at unequal cost |

## 6. Definition of done (Month 2)

- Identical logical VQC executed on ≥2 topologies (star + Garnet lattice; Emerald if queue allows).
- Optimal-vs-adverse mapping results with SWAP/depth/2q, mean-value error and fidelity.
- Quantified topological-distance ↔ SWAP ↔ degradation relationship with uncertainty.
- ZNE breakdown/collapse region characterized with drift bands (≥3 ODRA windows).
- Encoded-logical ([[4,2,2]] post-selection) vs. physical comparison **on Garnet (and an Emerald confirmatory point)**, at optimal and adverse placement, with acceptance rate — including a clean negative if that is the result.
- **Method comparison (ZNE vs. CDR vs. [[4,2,2]]) on the common shots-to-target axis**, per topology — the headline "which method pays, up to what 2q budget" figure.
- Publication-ready figure set + final report + reproducible release.
