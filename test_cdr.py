"""Tests for the CDR library (methodology_month_2.md §3)."""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp, Statevector

from cdr import (
    apply_cdr,
    clifford_ideal_expval,
    fit_cdr,
    is_clifford_angle,
    near_clifford_training_circuits,
    _snap_nearest,
)
from ansatz import build_ansatz


def _bound_ansatz(seed=0):
    circ = build_ansatz(5, 2, num_features=8, entanglement="star", entangling_gate="cz")
    rng = np.random.default_rng(seed)
    wp = [p for p in circ.parameters if p.name.startswith("w[")]
    xp = [p for p in circ.parameters if p.name.startswith("x[")]
    return circ.assign_parameters(
        {**{p: float(rng.normal()) for p in wp}, **{p: 0.3 for p in xp}}
    )


def test_snap_nearest():
    assert _snap_nearest(0.1) == 0.0
    assert abs(_snap_nearest(1.6) - np.pi / 2) < 1e-9
    assert abs(_snap_nearest(3.2) - np.pi) < 1e-9


def test_training_circuits_are_clifford_and_same_structure():
    target = _bound_ansatz()
    n_cz_target = sum(1 for i in target.data if i.operation.name == "cz")
    n_rot_target = sum(1 for i in target.data if i.operation.name in ("rx", "ry", "rz"))
    circuits = near_clifford_training_circuits(target, n_train=20, seed=1)
    assert len(circuits) == 20
    for c in circuits:
        # same 2q count and same number of rotations (structure preserved)
        assert sum(1 for i in c.data if i.operation.name == "cz") == n_cz_target
        rots = [i for i in c.data if i.operation.name in ("rx", "ry", "rz")]
        assert len(rots) == n_rot_target
        # every rotation angle is Clifford
        for i in rots:
            assert is_clifford_angle(float(i.operation.params[0]))


def test_training_set_spans_ideal_values():
    target = _bound_ansatz()
    obs = SparsePauliOp.from_list([("ZIIII", 1.0)])
    circuits = near_clifford_training_circuits(target, n_train=40, seed=2)
    ideals = [clifford_ideal_expval(c, obs) for c in circuits]
    # random Clifford angles should produce a non-degenerate spread
    assert np.std(ideals) > 0.05


def test_clifford_ideal_matches_statevector():
    target = _bound_ansatz()
    obs = SparsePauliOp.from_list([("IIIIZ", 1.0)])
    c = near_clifford_training_circuits(target, n_train=1, seed=3)[0]
    direct = float(np.real(Statevector.from_instruction(c).expectation_value(obs)))
    assert abs(clifford_ideal_expval(c, obs) - direct) < 1e-12


def test_fit_recovers_known_linear_map():
    rng = np.random.default_rng(0)
    ideal = rng.uniform(-1, 1, 200)
    a_true, b_true = 0.7, 0.05
    noisy = (ideal - b_true) / a_true  # so that a_true*noisy + b_true == ideal
    a, b, r2 = fit_cdr(noisy, ideal)
    assert abs(a - a_true) < 1e-6 and abs(b - b_true) < 1e-6
    assert r2 > 0.999
    assert abs(apply_cdr(0.5, a, b) - (a_true * 0.5 + b_true)) < 1e-9


def test_fit_low_r2_on_unlearnable_noise():
    rng = np.random.default_rng(1)
    ideal = rng.uniform(-1, 1, 200)
    noisy = rng.uniform(-1, 1, 200)  # unrelated -> no linear map
    _, _, r2 = fit_cdr(noisy, ideal)
    assert r2 < 0.2
