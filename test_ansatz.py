"""Unit tests for :mod:`ansatz` (Month-1 deliverable: builds for n = 2..5)."""

from __future__ import annotations

import numpy as np
import pytest

from ansatz import (
    ENTANGLEMENT_PATTERNS,
    HardwareEfficientAnsatz,
    build_ansatz,
    entangling_pairs,
    two_qubit_gate_count,
)


@pytest.mark.parametrize("n", [2, 3, 4, 5])
@pytest.mark.parametrize("pattern", ENTANGLEMENT_PATTERNS)
def test_circuit_builds(n: int, pattern: str) -> None:
    """The circuit must build for n = 2..5 and every entangling pattern."""
    qc = build_ansatz(n, num_layers=2, entanglement=pattern)
    assert qc.num_qubits == n
    assert qc.depth() > 0


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_parameter_counts(n: int) -> None:
    """Weight/feature parameter counts match the analytic formula."""
    L = 3
    ansatz = HardwareEfficientAnsatz(num_qubits=n, num_layers=L, entanglement="star")
    qc = ansatz.build()

    expected_weights = L * n + L * 2 * n + 2 * n  # embed + rot + final
    assert ansatz.num_weights == expected_weights
    assert len(ansatz.weight_parameters(qc)) == expected_weights
    assert len(ansatz.feature_parameters(qc)) == n  # default num_features == n
    assert qc.num_parameters == expected_weights + n


@pytest.mark.parametrize("n", [2, 3, 4, 5])
def test_star_two_qubit_count(n: int) -> None:
    """Star pattern entangles n-1 pairs per layer (hub-and-spoke)."""
    L = 2
    qc = build_ansatz(n, num_layers=L, entanglement="star")
    assert two_qubit_gate_count(qc) == (n - 1) * L


@pytest.mark.parametrize("n", [2, 3, 4, 5])
def test_all_to_all_two_qubit_count(n: int) -> None:
    """All-to-all entangles C(n, 2) pairs per layer -> maximal routing cost."""
    L = 2
    qc = build_ansatz(n, num_layers=L, entanglement="all_to_all")
    assert two_qubit_gate_count(qc) == (n * (n - 1) // 2) * L


@pytest.mark.parametrize("n", [3, 4, 5])
def test_all_to_all_costs_more_than_star(n: int) -> None:
    """The core premise of the study: all-to-all >> star in two-qubit gates."""
    star = build_ansatz(n, num_layers=2, entanglement="star")
    a2a = build_ansatz(n, num_layers=2, entanglement="all_to_all")
    assert two_qubit_gate_count(a2a) > two_qubit_gate_count(star)


def test_entangling_pairs_star_hub() -> None:
    assert entangling_pairs(4, "star", hub=0) == [(0, 1), (0, 2), (0, 3)]
    assert entangling_pairs(4, "star", hub=1) == [(1, 0), (1, 2), (1, 3)]


def test_single_qubit_has_no_entanglers() -> None:
    qc = build_ansatz(1, num_layers=2, entanglement="all_to_all")
    assert two_qubit_gate_count(qc) == 0


def test_binding_produces_concrete_circuit() -> None:
    """Assigning features + weights must yield a fully-bound circuit."""
    ansatz = HardwareEfficientAnsatz(num_qubits=4, num_layers=2, num_features=2)
    qc = ansatz.build()

    rng = np.random.default_rng(0)
    x_vals = rng.normal(size=ansatz.num_features)
    w_vals = rng.normal(size=ansatz.num_weights)

    binding = dict(zip(ansatz.feature_parameters(qc), x_vals))
    binding.update(zip(ansatz.weight_parameters(qc), w_vals))

    bound = qc.assign_parameters(binding)
    assert bound.num_parameters == 0


def test_fewer_features_than_qubits() -> None:
    """Features are cycled across qubits when num_features < num_qubits."""
    ansatz = HardwareEfficientAnsatz(num_qubits=5, num_layers=1, num_features=2)
    qc = ansatz.build()
    assert len(ansatz.feature_parameters(qc)) == 2
    assert qc.num_qubits == 5


def test_invalid_config_raises() -> None:
    with pytest.raises(ValueError):
        build_ansatz(0)
    with pytest.raises(ValueError):
        build_ansatz(3, num_layers=0)
    with pytest.raises(ValueError):
        build_ansatz(3, entanglement="mesh")
    with pytest.raises(ValueError):
        build_ansatz(3, entangling_gate="iswap")


def test_cz_entangler_option() -> None:
    qc = build_ansatz(4, num_layers=1, entanglement="star", entangling_gate="cz")
    ops = qc.count_ops()
    assert ops.get("cz", 0) == 3
    assert ops.get("cx", 0) == 0
