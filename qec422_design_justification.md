# Justification: how the `[[4,2,2]]` error-detection arm runs the VQC (Options A + C)

**Status:** design rationale for W5 (the "logical-ish" arm). This document exists because the
choice is **not common practice** — error-detecting codes are normally demonstrated on fixed
logical circuits (state preparation, Clifford memory, small algorithms), *not* on a variational,
data-dependent classifier. Running a VQC "under" a code therefore needs an explicit, honest
defence, which is what follows. It is written to be handed to a supervisor.

---

## 1. The obstruction that forces a creative choice

A variational quantum classifier needs **data-dependent single-qubit rotations** `R_y(x)` and
trainable `R_y(θ)/R_z(θ)`. These are **non-Clifford** and, in the `[[4,2,2]]` code (as in
essentially all small codes), **not transversal**. `[[4,2,2]]` offers only a *limited logical
Clifford set* on its 2 logical qubits (logical Paulis, logical CNOT between the pair, a
simultaneous-Hadamard operation). Consequently there is **no faithful way to encode the exact
non-Clifford VQC** in `[[4,2,2]]` on NISQ hardware:

- A fully faithful logical VQC would require injecting non-Clifford gates via **magic-state
  distillation / post-selected T-gadgets** — orders-of-magnitude qubit and shot overhead, and
  exactly the regime we rejected in Month 1 when we declined full QEC (5×13 = 65 > 54 qubits,
  device 2q error ~1.9 % near threshold, no fast feed-forward).

So "run the VQC under `[[4,2,2]]`" cannot mean "encode the exact model." It must mean something
precise and defensible. We adopt **two complementary constructions** rather than one, because
each answers a different question and neither alone is complete.

---

## 2. What we actually run

### Option A — Encoded near-Clifford surrogate (task-facing arm)

Take the trained VQC and **snap every rotation angle to its nearest Clifford** (multiple of
π/2). This yields a **Clifford surrogate** with the *same circuit structure, the same entangling
pattern, the same transpiled routing, and the same noise profile* as the real classifier — but
whose logical operations are transversally implementable in `[[4,2,2]]` and whose ideal
expectation value is **exactly computable** by stabilizer simulation (Gottesman–Knill), at no
statevector cost.

We run the surrogate as genuine logical operations in `[[4,2,2]]` on 2 logical qubits, with
**stabilizer post-selection** (measure the four data qubits destructively, compute the
`XXXX`/`ZZZZ` parity classically, discard flagged shots — ancilla-free, Vuillot-style). We
compare, at matched routing cost and at optimal vs. adverse placement:

1. unencoded physical surrogate, 2. encoded / detection-off, 3. encoded / detection-on.

**Claim it supports:** "*on the Clifford surrogate of the classifier*, error detection recovers
X of the accuracy/⟨O⟩ lost to routing noise, at an acceptance-rate cost Y." A bounded, honest
claim — explicitly about the surrogate, not the exact non-Clifford model.

### Option C — Detection-wrapped mirror (circuit-facing arm)

Run the **exact, real VQC** `U` (non-Clifford and all) followed by `U†`, so the net operation is
**code-preserving** and the ideal output is exactly `|0…0⟩_L`, *independent of the data and the
decision boundary*. Wrap `[[4,2,2]]` detection + post-selection around it and measure the
survival probability `P(|0…0⟩_L)` with detection off vs. on, at each routing rung and placement.

**Claim it supports:** "detection improves the *effective fidelity of the exact routed circuit*
by Z at routing cost C." This uses the true non-Clifford circuit and its true routing — maximal
faithfulness — at the price of measuring fidelity rather than classification accuracy.

---

## 3. Why this is legitimate, not a fudge

The unusualness is real; the components are not ad hoc. Each rests on accepted methodology:

1. **The classifier is a *vehicle*, not the object of study.** The project's question is *how
   error handling behaves under routing overhead*, measured along the transpiled-2q-cost axis.
   What must be preserved to answer that is the **circuit structure, routing, and noise
   profile** — all of which the near-Clifford surrogate (A) preserves exactly. Task performance
   of the *specific* trained weights is secondary (this is the same stance that made ⟨O⟩-error,
   not accuracy, our primary metric in Month 1).

2. **The near-Clifford surrogate is the *same* principle as CDR** — an accepted QEM technique
   (Czarnik et al. 2021). We already use near-Clifford training circuits for the CDR arm; reusing
   them for the QED arm gives **one coherent methodology across the QEM and QEC arms**, not a
   one-off trick. Clifford / near-Clifford surrogates are also the backbone of randomized
   benchmarking and Clifford-volume benchmarks, so they carry established legitimacy.

3. **The mirror construction (C) is a standard task-agnostic tool.** Mirror circuits (`U U†`,
   known ideal output) underpin mirror randomized benchmarking (Proctor et al.) and are already
   our Month-1 fidelity yardstick. Adding detection around one is a natural, defensible extension
   — it measures the exact routed circuit, removing the surrogate caveat that A carries.

4. **A + C triangulate the claim.** A is *faithful-to-task but Clifford*; C is
   *faithful-to-circuit but task-agnostic*. A reviewer's two obvious objections — "that's not the
   real circuit" (answered by C) and "that's not classification" (answered by A) — are each
   covered by the other arm. This is the same triangulation the project already uses between
   coarse accuracy and the continuous ⟨O⟩-error signal.

5. **Error detection on 5-qubit-class superconducting hardware has direct precedent.** Vuillot
   (2018) and Linke et al. (2017) demonstrate `[[4,2,2]]` detection + post-selection on small
   devices, including honest net-negative outcomes. We inherit their protocol and their standard
   of honesty.

---

## 4. Honest limitations (stated up front)

- **Neither arm is a fully faithful non-Clifford logical classifier.** That needs magic-state
  injection / post-selected T-gadgets — out of NISQ scope, and rejected for the same reasons as
  full QEC. We do not claim otherwise.
- **`[[4,2,2]]` is distance 2: it detects, it cannot correct.** Post-selection discards flagged
  shots, so it buys fidelity at a **shot-rate cost**. We report the **acceptance rate** as the
  honest overhead and fold it into the shots-to-target cost currency, so QED is compared to ZNE
  and CDR on equal footing.
- **A carries a surrogate gap**; **C measures fidelity, not accuracy.** Each caveat is explicit,
  and each is the reason the *other* arm exists.
- **Results are device-, calibration-, and topology-specific** — as with every arm in this study.
- **A clean negative is a valid result.** If detection's post-selection overhead outweighs its
  benefit at these error rates (plausible at ~1–2 % two-qubit error), that is itself the finding
  — consistent with the precedent literature.

---

## 5. How it fits the report's framing

This arm is positioned exactly like the rest of the study: **QEC-lite as characterization under
routing overhead**, compared against ZNE and CDR on a common cost axis, anchored by
task-agnostic yardsticks. The non-standard move (running a classifier under a code) is
acknowledged, bounded, and built from accepted components (near-Clifford surrogates as in
CDR/RB; mirror circuits as in mirror RB) reused in a new comparison. The contribution is not
"we encoded a classifier" but "**we place error detection on the same routing-cost/topology axis
as the mitigation methods and report, honestly, where it pays and where its post-selection
overhead does not.**"

---

## References

- C. Vuillot, *Is error detection helpful on IBM 5Q chips?*, Quantum Inf. Comput. 18, 949 (2018);
  arXiv:1705.08957.
- N. M. Linke et al., *Fault-tolerant quantum error detection*, Sci. Adv. 3, e1701074 (2017);
  arXiv:1611.06946.
- P. Czarnik, A. Arrasmith, P. J. Coles, L. Cincio, *Error mitigation with Clifford
  quantum-circuit data*, Quantum 5, 592 (2021); arXiv:2005.10189.
- T. Proctor et al., *Scalable randomized benchmarking of quantum computers using mirror
  circuits*, Phys. Rev. Lett. 129, 150502 (2022); arXiv:2112.09853.
- D. Gottesman, *The Heisenberg representation of quantum computers* (Gottesman–Knill), 1998;
  arXiv:quant-ph/9807006.
