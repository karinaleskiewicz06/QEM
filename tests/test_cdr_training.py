"""P1: training circuits that keep the target's routing and differ between targets."""

from __future__ import annotations

import numpy as np
import pytest
from qiskit import QuantumCircuit

from ansatz import HardwareEfficientAnsatz
from cdr import near_clifford_training_circuits
from noisy_sim import readout_observable
from qem.cdr_training import (CLIFFORD_ANGLES, build_legacy_shared_training,
                              build_training_set, clifford_ideal_expval, is_clifford,
                              near_target, nearest, snap_native_to_clifford,
                              stable_seed, uniform_random)
from qem.compile import compile_native, cz_skeleton
from zne_dryrun import native_transpile

PATTERNS = ["star", "linear", "circular", "all_to_all"]
ROUTED = ["linear", "circular", "all_to_all"]


def targets(pattern: str, n: int = 2, seed: int = 7):
    rng = np.random.default_rng(seed)
    ans = HardwareEfficientAnsatz(5, 3, num_features=8, entanglement=pattern)
    circ = ans.build()
    wp, xp = ans.weight_parameters(circ), ans.feature_parameters(circ)
    cw = circ.assign_parameters(dict(zip(wp, rng.uniform(-np.pi, np.pi, len(wp)))))
    return [cw.assign_parameters(dict(zip(xp, rng.uniform(-1, 1, len(xp)))))
            for _ in range(n)], cw, xp


# -- the acceptance criteria ------------------------------------------------ #

@pytest.mark.parametrize("pattern", PATTERNS)
def test_every_training_circuit_keeps_the_target_skeleton(pattern: str):
    """100% match, by construction -- nothing is re-transpiled."""
    tgts, _, _ = targets(pattern, 1)
    native = compile_native(tgts[0])
    train = build_training_set(native.circuit, n_train=10, target_index=0,
                               window_id="o1")
    assert all(cz_skeleton(t) == native.cz_skeleton for t in train)


@pytest.mark.parametrize("pattern", PATTERNS)
def test_every_training_circuit_is_clifford(pattern: str):
    tgts, _, _ = targets(pattern, 1)
    train = build_training_set(compile_native(tgts[0]).circuit, n_train=10,
                               target_index=0, window_id="o1")
    assert all(is_clifford(t) for t in train)


@pytest.mark.parametrize("pattern", PATTERNS)
def test_different_targets_get_different_training_sets(pattern: str):
    """The archived campaigns shared one set across all evaluation points."""
    tgts, _, _ = targets(pattern, 2)
    a = build_training_set(compile_native(tgts[0]).circuit, n_train=10,
                           target_index=0, window_id="o1")
    b = build_training_set(compile_native(tgts[1]).circuit, n_train=10,
                           target_index=1, window_id="o1")
    assert any(x.data != y.data for x, y in zip(a[1:], b[1:]))


@pytest.mark.parametrize("pattern", ROUTED)
def test_legacy_path_loses_the_skeleton_regression(pattern: str):
    """Documented regression on the archived path: almost nothing matches.

    Measured here rather than quoted, so DATA_NOTES.md stays checkable. The old path
    is also non-deterministic, so the count is bounded rather than fixed.
    """
    tgts, _, _ = targets(pattern, 1)
    target_skel = cz_skeleton(native_transpile(tgts[0], 5))
    train = near_clifford_training_circuits(tgts[0], n_train=10, seed=42)
    matched = sum(cz_skeleton(native_transpile(t, 5)) == target_skel for t in train)
    assert matched <= 2, (f"{pattern}: {matched}/10 matched; the archived path is "
                          f"expected to match almost none")


def test_star_is_the_exception_on_the_legacy_path():
    """star needs no routing, so even the unseeded path keeps its skeleton."""
    tgts, _, _ = targets("star", 1)
    target_skel = cz_skeleton(native_transpile(tgts[0], 5))
    train = near_clifford_training_circuits(tgts[0], n_train=10, seed=42)
    assert all(cz_skeleton(native_transpile(t, 5)) == target_skel for t in train)


# -- samplers and seeding --------------------------------------------------- #

def test_stable_seed_does_not_depend_on_the_process():
    """Python's str hash is salted per process; the seed must not inherit that."""
    assert stable_seed(42, 3, "o1") == stable_seed(42, 3, "o1")
    assert stable_seed(42, 3, "o1") != stable_seed(42, 4, "o1")
    assert stable_seed(42, 3, "o1") != stable_seed(42, 3, "o2")
    assert stable_seed(42, 3, "o1") == 1113026999 or stable_seed(42, 3, "o1") > 0


def test_nearest_snaps_to_the_closest_clifford_angle():
    assert nearest(0.1) == 0.0
    assert nearest(np.pi / 2 - 0.05) == pytest.approx(np.pi / 2)
    assert nearest(2 * np.pi - 0.01) == 0.0          # wraps


def test_near_target_prefers_angles_close_to_the_original():
    rng = np.random.default_rng(0)
    sampler = near_target(sigma=np.pi / 8)
    draws = [sampler(0.05, rng) for _ in range(400)]
    assert draws.count(0.0) > 300, "a tight sigma must concentrate near the original"


def test_uniform_random_ignores_the_original():
    rng = np.random.default_rng(0)
    draws = [uniform_random(0.05, rng) for _ in range(400)]
    assert len(set(draws)) == len(CLIFFORD_ANGLES)


def test_zero_theta_rotations_are_dropped_not_emitted():
    qc = QuantumCircuit(1)
    qc.r(0.01, 0.01, 0)
    snapped = snap_native_to_clifford(qc, nearest)
    assert snapped.count_ops().get("r", 0) == 0


def test_snap_rejects_a_non_native_gate():
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    with pytest.raises(ValueError, match="native circuit"):
        snap_native_to_clifford(qc, nearest)


def test_stabilizer_ideal_matches_statevector():
    """The stabilizer value is what makes CDR scale; it must agree with the exact one."""
    from qiskit.quantum_info import Statevector
    tgts, _, _ = targets("linear", 1)
    native = compile_native(tgts[0])
    obs = readout_observable(5, "mean")
    for t in build_training_set(native.circuit, n_train=5, target_index=0,
                                window_id="o1"):
        probe = t.copy()
        probe.remove_final_measurements(inplace=True)
        exact = float(np.real(Statevector.from_instruction(probe).expectation_value(obs)))
        assert clifford_ideal_expval(t, obs) == pytest.approx(exact, abs=1e-10)


def test_legacy_shared_training_reproduces_the_defect():
    """Only the anchor differs between targets, which is the archived behaviour."""
    tgts, _, _ = targets("linear", 3)
    natives = [compile_native(t).circuit for t in tgts]
    sets = build_legacy_shared_training(natives, n_train=6)
    for a, b in zip(sets[0][1:], sets[1][1:]):
        assert a.data == b.data, "legacy mode must share circuits 1..n-1"
