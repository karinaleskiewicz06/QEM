"""Clifford Data Regression (CDR) — QEM method #2 (methodology_month_2.md §3, W4b).

A learning-based mitigator that, unlike ZNE, does NOT amplify noise. It builds
near-Clifford "training" circuits with the *same structure and routing* as the
target, runs them noisy, learns a correction ``ideal ≈ a·noisy + b`` from the
(noisy, ideal) pairs, and applies it to the target's raw expectation value.

Ref: Czarnik, Arrasmith, Coles, Cincio, *Error mitigation with Clifford
quantum-circuit data*, Quantum 5, 592 (2021); arXiv:2005.10189.

Method fidelity vs. cost: at the study size (n = 5) the ideal value of a training
circuit is computed EXACTLY by statevector — cheap and unambiguous. The
near-Clifford construction is retained anyway because it is the essence of CDR and
what makes the ideal efficiently computable (Gottesman–Knill) at scale.
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

# The four single-qubit Clifford rotation angles (multiples of π/2).
CLIFFORD_ANGLES = np.array([0.0, np.pi / 2, np.pi, 3 * np.pi / 2])
_ROTATIONS = {"rx", "ry", "rz"}


def _snap_nearest(angle: float) -> float:
    """Nearest Clifford angle (multiple of π/2) to ``angle``, wrapped to [0, 2π)."""
    a = float(angle) % (2 * np.pi)
    return float(CLIFFORD_ANGLES[int(np.argmin(np.abs(CLIFFORD_ANGLES - a)))])


def _rebuild(circ: QuantumCircuit, angle_fn) -> QuantumCircuit:
    """Copy ``circ`` replacing every rx/ry/rz angle via ``angle_fn(old_angle)``.

    Non-rotation gates (cz, cx, h, ...) are copied unchanged, so the circuit's
    structure, gate count, and routing are identical to the target — only the
    single-qubit rotation angles change. Requires a parameter-bound circuit.
    """
    out = QuantumCircuit(circ.num_qubits)
    for inst in circ.data:
        op = inst.operation
        idxs = [circ.find_bit(q).index for q in inst.qubits]
        if op.name in _ROTATIONS:
            new_angle = angle_fn(float(op.params[0]))
            getattr(out, op.name)(new_angle, idxs[0])
        else:
            out.append(op, idxs)
    return out


def near_clifford_training_circuits(
    bound_circuit: QuantumCircuit,
    n_train: int = 100,
    seed: int = 42,
) -> list[QuantumCircuit]:
    """Build ``n_train`` near-Clifford circuits from a parameter-bound target.

    Circuit 0 is the target with every rotation snapped to its *nearest* Clifford
    (the anchor closest to the real circuit). Circuits 1..n_train-1 snap each
    rotation to a *random* Clifford angle, spanning a range of ideal values while
    keeping the structure/routing (hence the noise profile) identical to the target.
    """
    rng = np.random.default_rng(seed)
    circuits = [_rebuild(bound_circuit, _snap_nearest)]
    for _ in range(max(0, n_train - 1)):
        circuits.append(_rebuild(bound_circuit, lambda _a: float(rng.choice(CLIFFORD_ANGLES))))
    return circuits


def clifford_ideal_expval(circuit: QuantumCircuit, observable) -> float:
    """Exact noiseless ⟨O⟩ of a (near-Clifford) circuit via statevector.

    At n = 5 this is exact and cheap; at scale, replace with a stabilizer simulator
    (the training circuits are Clifford by construction, so it stays efficient).
    ``circuit`` must be measurement-free.
    """
    sv = Statevector.from_instruction(circuit)
    return float(np.real(sv.expectation_value(observable)))


def fit_cdr(noisy_vals, ideal_vals) -> tuple[float, float, float]:
    """Least-squares fit of ``ideal ≈ a·noisy + b``; returns ``(a, b, r2)``.

    ``r2`` is the coefficient of determination of the fit (1.0 = perfect); a low
    ``r2`` flags that the device's noise map is not well described by a single
    linear rescale for this circuit — itself a useful signal.
    """
    noisy = np.asarray(noisy_vals, float)
    ideal = np.asarray(ideal_vals, float)
    A = np.vstack([noisy, np.ones_like(noisy)]).T
    (a, b), *_ = np.linalg.lstsq(A, ideal, rcond=None)
    pred = a * noisy + b
    ss_res = float(np.sum((ideal - pred) ** 2))
    ss_tot = float(np.sum((ideal - ideal.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    return float(a), float(b), float(r2)


def apply_cdr(noisy_target: float, a: float, b: float) -> float:
    """Apply the learned CDR correction to a target's raw noisy ⟨O⟩."""
    return float(a * float(noisy_target) + b)


def is_clifford_angle(angle: float, tol: float = 1e-9) -> bool:
    """True if ``angle`` is (numerically) a multiple of π/2."""
    a = float(angle) % (2 * np.pi)
    return bool(np.min(np.abs(CLIFFORD_ANGLES - a)) < tol
                or abs(np.min(np.abs(CLIFFORD_ANGLES - a)) - 2 * np.pi) < tol)
