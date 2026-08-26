# QEM — Topology-Aware Breakdown of Quantum Error Mitigation

## What This Is

A publishable research study characterizing **where** quantum error-mitigation and
near-term error-detection methods (ZNE, CDR, `[[4,2,2]]` detection) **stop paying off**
under hardware routing overhead — resolved **across superconducting topologies** (IQM ODRA
star, Garnet 20-qubit lattice, Emerald 54-qubit lattice) — plus a **meta-analysis** of the
methods on a common shots-to-target cost axis. For the KN Axion research group (Politechnika
Wrocławska). Month 1 was a warm-up that validated the sim↔hardware pipeline; Month 2 delivers
the cross-topology, cross-method breakdown characterization aimed at publication.

## Core Value

A publishable, defensible, **device- and topology-resolved characterization of the
method-breakdown frontier under routing cost** — which method pays up to what two-qubit-gate
budget, and which breaks down first — anchored by a task-agnostic fidelity yardstick.

## Requirements

### Validated

<!-- Month 1 — shipped and confirmed. -->

- ✓ Reproducible sim↔hardware QEM pipeline (calibrated Aer noise sim → REM+ZNE inference) — M1
- ✓ Two independent routing ladders (`two_curves` + Banknote) measured on real ODRA — M1
- ✓ ZNE error-reduction decays monotonically with transpiled CZ; breakeven ~85–90 CZ on the star — M1
- ✓ Dynamical Decoupling is a measured **negative** result on IQM Spark — M1
- ✓ Single per-gate fidelity model fits all QPU points (~0.86%/CZ, ~0.61%/1q) — M1

### Active

<!-- Month 2 — building toward publishable results. -->

- [ ] Port the pipeline to lattice topologies (Garnet 20q, Emerald 54q)
- [ ] Optimal-vs-adverse placement mapping experiment on real lattices (topological-overhead analysis)
- [ ] Method meta-analysis: ZNE vs CDR vs `[[4,2,2]]` on a common shots-to-target cost axis
- [ ] Characterize the breakdown/collapse region with calibration-drift error bands
- [ ] Task-agnostic mirror-fidelity backbone (classifier-independent generalization)
- [ ] Accuracy-recovery test at high real routing cost (hardware, targeted high-statistics point)
- [ ] Final report + publication plan (venue, figures, narrative)

### Out of Scope

- Full QEC / fault-tolerant logical qubits — below-threshold requirement + qubit budget infeasible on these devices
- Quantum-advantage claims — the VQC is a vehicle, not the object of study
- More classification datasets — generalization rides on the task-agnostic mirror, not dataset breadth

## Context

- Brownfield Python codebase (see `.planning/codebase/`): qiskit + qiskit-aer + torch +
  qiskit-machine-learning + qiskit-iqm; separated sim and hardware runners; `trained_models/`
  (easy) + `trained_models_hard/` (offset-0.1 hard config).
- Hardware access: **IQM Resonance** (Garnet/Emerald) via `qiskit-iqm`; ODRA historically via
  `iqm-client`. Fixed **credit budget ~3700** (time-billed, ~0.0002 cr/shot); ~312 spent so far.
- Datasets: `two_curves` (synthetic; easy config accuracy-saturated, hard config near-boundary)
  + Banknote (used in M1, dropped for M2 focus). Accuracy is high-variance → **⟨O⟩-error is the
  sensitive primary metric**; accuracy/F1 are secondary.
- Framing (see `plan_month_2.md`, `methodology_month_2.md`, `hardware_runbook.md`,
  `qec422_design_justification.md`): the cost axis is **routing overhead (SWAP/CZ), not raw
  depth**; the same logical circuit crosses the breakdown at different points on different
  topologies. Hardware confirms the calibrated sim is a conservative (pessimistic) proxy.

## Constraints

- **Budget**: ~3700 IQM Resonance credits total — campaign must fit with Emerald reserved.
- **Simulability**: Emerald (54q) is classically unsimulable (2^54); cross-topology must come
  from the QPU. Garnet REM is off (Resonance backend exposes no per-qubit readout calibration).
- **Environment**: torch+aer OpenMP conflict (needs `KMP_DUPLICATE_LIB_OK=TRUE`); git commits are
  signed with a passphrase-protected SSH key (interactive — blocks non-interactive commits).
- **Statistics**: accuracy is high-variance → cheap ⟨O⟩-error is primary; error bands come from
  ≥2 calibration (drift) windows, not in-window repetitions.
- **Timeline**: two-month research cycle; Month 1 (warm-up) done, Month 2 in progress.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| ⟨O⟩-error as primary metric | Continuous, low-variance; accuracy saturated/noisy | ✓ Good |
| `[[4,2,2]]` via A (near-Clifford surrogate) + C (detection-wrapped mirror) | Non-Clifford `Ry(x)` not transversal; can't encode exact VQC | ✓ Good |
| shots-to-target common cost currency | Methods have different native overhead units | ✓ Good |
| Everything on hard `two_curves` (offset 0.1) | One coherent narrative; regime where accuracy *can* respond | — Pending (hardware) |
| 15 pts hardware + one 100-pt accuracy point | ⟨O⟩-error robust at 15; accuracy needs 100 only where it can appear (96 CZ) | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-25 after project initialization (brownfield onboarding)*
