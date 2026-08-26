"""Tests for the [[4,2,2]] error-detection primitives (methodology_month_2.md §4)."""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator

from qec422 import (
    N_DATA,
    Z_LOGICAL1,
    build_detection_mirror,
    codespace_survival,
    encode_422,
    logical_z_expval,
    postselect_z_parity,
    z_parity,
)

_SIM = AerSimulator()


def _counts(qc, shots=8192):
    return _SIM.run(qc, shots=shots).result().get_counts()


def test_encoder_prepares_logical_zero():
    sv = Statevector.from_instruction(encode_422())
    probs = sv.probabilities_dict()
    # only |0000> and |1111>, each ~1/2
    assert set(probs) == {"0000", "1111"}
    assert abs(probs["0000"] - 0.5) < 1e-9
    assert abs(probs["1111"] - 0.5) < 1e-9


def test_z_parity():
    assert z_parity("0000") == 0
    assert z_parity("1111") == 0
    assert z_parity("1000") == 1
    assert z_parity("1100") == 0


def test_noiseless_encode_all_accepted():
    qc = encode_422().copy()
    qc.measure_all()
    kept, acc = postselect_z_parity(_counts(qc))
    assert acc == 1.0  # every logical shot is even parity
    assert all(z_parity(b) == 0 for b in kept)


def test_single_x_error_is_detected():
    qc = QuantumCircuit(N_DATA, N_DATA)
    qc.compose(encode_422(), inplace=True)
    qc.x(0)  # a definite single-qubit X error
    qc.measure(range(N_DATA), range(N_DATA))
    kept, acc = postselect_z_parity(_counts(qc))
    assert acc == 0.0  # every shot flagged (odd parity) -> all discarded


def test_logical_z_on_codestate_is_plus_one():
    qc = encode_422().copy()
    qc.measure_all()
    counts = _counts(qc)
    # Zbar_1 = Z0 Z1 ; |00>_L is its +1 eigenstate
    assert abs(logical_z_expval(counts, Z_LOGICAL1) - 1.0) < 0.05


def test_mirror_survives_noiselessly():
    # a non-trivial code-preserving payload; U U† returns to |00>_L
    payload = QuantumCircuit(N_DATA)
    payload.cx(0, 1)
    payload.cx(2, 3)
    payload.h(0)
    qc = build_detection_mirror(payload, detect=True)
    counts = _counts(qc)
    kept, acc = postselect_z_parity(counts)
    assert acc == 1.0
    assert abs(codespace_survival(counts) - 1.0) < 1e-9  # perfect survival, no noise


def test_acceptance_folds_into_shots_to_target():
    from shots_to_target import qec_effective_shots
    # 50% acceptance -> need 2x raw shots to keep the same usable count
    assert abs(qec_effective_shots(1000, 0.5) - 2000) < 1e-6
