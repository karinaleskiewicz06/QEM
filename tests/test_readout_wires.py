"""Readout wires survive every pass that rebuilds the native circuit.

On ODRA the histogram is indexed by physical wire, and ``odra_backend`` maps it back to
logical qubits with ``noisy_sim.logical_final_wires``. That function used to read only
``circuit.layout``; ``compile_native`` (1q merging), ``twirl_native_merged`` and the folds
rebuild the circuit and drop it, and the identity fallback then read routed qubits off
the wrong wires. Invisible for mean-Z (a permutation-invariant observable), wrong for
anything per qubit -- REM, hub-Z, marginals.
"""

from __future__ import annotations

import numpy as np
import pytest
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import SparsePauliOp, Statevector

from ansatz import HardwareEfficientAnsatz
from noisy_sim import IQM_BASIS_GATES, logical_final_wires
from odra_backend import iqm_counts_to_qiskit
from qem.compile import compile_native
from qem.twirl import twirl_native_merged
from topology import star_coupling_map

PATTERNS = ["star", "linear", "circular", "all_to_all"]


def bound(pattern: str, seed: int = 3) -> QuantumCircuit:
    rng = np.random.default_rng(seed)
    ans = HardwareEfficientAnsatz(5, 3, num_features=8, entanglement=pattern)
    c = ans.build()
    wp, xp = ans.weight_parameters(c), ans.feature_parameters(c)
    return c.assign_parameters({**dict(zip(wp, rng.uniform(-np.pi, np.pi, len(wp)))),
                                **dict(zip(xp, rng.uniform(-1, 1, len(xp))))})


def z_each(circ: QuantumCircuit) -> np.ndarray:
    c = circ.copy()
    c.remove_final_measurements(inplace=True)
    sv = Statevector.from_instruction(c)
    return np.array([np.real(sv.expectation_value(
        SparsePauliOp("I" * (4 - q) + "Z" + "I" * q))) for q in range(5)])


def reference_wires(logical: QuantumCircuit) -> list[int]:
    m = logical.copy()
    m.measure_all()
    raw = transpile(m, basis_gates=IQM_BASIS_GATES, coupling_map=star_coupling_map(5),
                    initial_layout=[0, 1, 2, 3, 4], optimization_level=1, seed_transpiler=42)
    return [int(w) for w in raw.layout.final_index_layout()[:5]]


@pytest.mark.parametrize("pattern", PATTERNS)
def test_wires_survive_merging_and_twirling(pattern):
    logical = bound(pattern)
    ref = reference_wires(logical)
    measured = compile_native(logical, measure=True).circuit
    unmeasured = compile_native(logical).circuit
    twirled = twirl_native_merged(measured, np.random.default_rng(1)).circuit
    for c in (measured, unmeasured, twirled):
        assert logical_final_wires(c, 5) == ref


def test_routing_actually_permutes_on_the_ladder():
    """Otherwise the tests above would be vacuous."""
    assert any(reference_wires(bound(p)) != [0, 1, 2, 3, 4] for p in PATTERNS)


@pytest.mark.parametrize("pattern", PATTERNS)
def test_wire_q_carries_logical_qubit_q(pattern):
    """Physics: <Z> on wire wires[q] of the executed circuit equals logical <Z_q>."""
    logical = bound(pattern)
    want = z_each(logical)
    for c in (compile_native(logical, measure=True).circuit,
              twirl_native_merged(compile_native(logical, measure=True).circuit,
                                  np.random.default_rng(2)).circuit):
        wires = logical_final_wires(c, 5)
        got = z_each(c)[wires]
        np.testing.assert_allclose(got, want, atol=1e-10)


def test_iqm_histogram_round_trip():
    """A wire-ordered IQM histogram maps back to the logical Qiskit key."""
    wires = [2, 1, 3, 0, 4]
    logical_bits = {0: "1", 1: "0", 2: "1", 3: "1", 4: "0"}   # logical qubit -> bit
    wire_bits = ["0"] * 5
    for q, w in enumerate(wires):
        wire_bits[w] = logical_bits[q]
    out = iqm_counts_to_qiskit({"".join(wire_bits): 7}, 5, wires)
    key = "".join(logical_bits[q] for q in reversed(range(5)))   # Qiskit: qubit 0 rightmost
    assert out == {key: 7}
