"""P2: equal budgets, a reconstructible frame, and a fit that is not diluted."""

from __future__ import annotations

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp, Statevector

from ansatz import HardwareEfficientAnsatz
from qem.arms import ARMS, CircuitSpec, budget, plan_all, plan_arm
from qem.cdr_fit import (MAX_DEATTENUATION, block_variance, fit_both, fit_cdr_eiv,
                         fit_ols, shot_variance_mean_z, spread_x_variance)
from qem.compile import compile_native, cz_skeleton
from qem.merge1q import max_prx_run
from qem.twirl import draw_frame, rebuild_from_frame, twirl_native_merged, twirl_logical

PATTERNS = ["star", "linear", "circular", "all_to_all"]
#: The merged native wrap may cost this much more than the untwirled arm.
OVERHEAD_LIMIT = 1.4


def bound(pattern: str, seed: int = 1) -> QuantumCircuit:
    rng = np.random.default_rng(seed)
    ans = HardwareEfficientAnsatz(5, 3, num_features=8, entanglement=pattern)
    circ = ans.build()
    wp, xp = ans.weight_parameters(circ), ans.feature_parameters(circ)
    return circ.assign_parameters({
        **dict(zip(wp, rng.uniform(-np.pi, np.pi, len(wp)))),
        **dict(zip(xp, rng.uniform(-1, 1, len(xp))))})


def zexp(circ: QuantumCircuit) -> np.ndarray:
    probe = circ.copy()
    probe.remove_final_measurements(inplace=True)
    sv = Statevector.from_instruction(probe)
    n = probe.num_qubits
    return np.array([np.real(sv.expectation_value(
        SparsePauliOp("I" * (n - 1 - i) + "Z" + "I" * i))) for i in range(n)])


# -- budget ----------------------------------------------------------------- #

@pytest.mark.parametrize("n_train,n_frames,shots", [(10, 6, 8192), (20, 6, 8192),
                                                    (3, 2, 256), (1, 1, 1)])
def test_every_arm_spends_the_same_budget(n_train, n_frames, shots):
    """The whole point of the design: no arm may buy extra averaging."""
    expected = budget(n_train, n_frames, shots)
    plans = plan_all(n_train=n_train, n_frames=n_frames, shots=shots)
    for arm, plan in plans.items():
        assert plan.total_shots == expected, f"{arm} spends {plan.total_shots}"
        assert plan.n_circuits == (n_train + 1) * n_frames


@pytest.mark.parametrize("n_train,n_frames", [(10, 6), (20, 6)])
def test_spread_measures_n_train_times_m_distinct_circuits(n_train, n_frames):
    """Spread's size is a parameter, not the 60 from the simulation benchmark."""
    spread = plan_arm("spread", n_train=n_train, n_frames=n_frames, shots=8192)
    plain = plan_arm("off_copies", n_train=n_train, n_frames=n_frames, shots=8192)
    assert spread.n_distinct_training_circuits == n_train * n_frames
    assert plain.n_distinct_training_circuits == n_train
    assert spread.total_shots == plain.total_shots


def test_every_arm_measures_the_target_the_same_way():
    plans = plan_all(n_train=10, n_frames=6, shots=8192)
    for plan in plans.values():
        targets = [s for s in plan.specs if s.role == "target"]
        assert len(targets) == 6


def test_unknown_arm_and_bad_parameters_are_rejected():
    with pytest.raises(ValueError, match="unknown arm"):
        plan_arm("nonsense", n_train=1, n_frames=1, shots=1)
    with pytest.raises(ValueError, match="must all be positive"):
        plan_arm("spread", n_train=0, n_frames=1, shots=1)


def test_circuit_ids_are_unique_within_an_arm():
    for arm in ARMS:
        plan = plan_arm(arm, n_train=4, n_frames=3, shots=16)
        ids = [s.circuit_id for s in plan.specs]
        assert len(ids) == len(set(ids)), f"{arm} produced duplicate circuit ids"


# -- twirling ---------------------------------------------------------------- #

@pytest.mark.parametrize("pattern", PATTERNS)
def test_twirl_preserves_the_observable_and_the_skeleton(pattern: str):
    off = compile_native(bound(pattern))
    base = zexp(off.circuit)
    for seed in range(6):
        tw = twirl_native_merged(off.circuit, np.random.default_rng(seed))
        assert np.abs(zexp(tw.circuit) - base).max() < 1e-10
        assert cz_skeleton(tw.circuit) == off.cz_skeleton


@pytest.mark.parametrize("pattern", PATTERNS)
def test_merged_twirl_overhead_stays_near_the_untwirled_arm(pattern: str):
    """Unmerged wrappers cost 2-3x and made the first native run come back negative."""
    off = compile_native(bound(pattern))
    merged = [twirl_native_merged(off.circuit, np.random.default_rng(s)).circuit
              for s in range(6)]
    mean_prx = float(np.mean([c.count_ops().get("r", 0) for c in merged]))
    assert mean_prx <= OVERHEAD_LIMIT * off.n_prx, (
        f"{pattern}: {mean_prx:.1f} PRX against {off.n_prx} untwirled "
        f"({mean_prx / off.n_prx:.2f}x)")
    assert all(max_prx_run(c) <= 1 for c in merged)


@pytest.mark.parametrize("pattern", PATTERNS)
def test_frame_reconstructs_the_executed_circuit(pattern: str):
    """An archived record must stand alone: native circuit + frame == what ran."""
    off = compile_native(bound(pattern))
    for seed in range(4):
        tw = twirl_native_merged(off.circuit, np.random.default_rng(seed))
        assert rebuild_from_frame(off.circuit, tw.frame_str).data == tw.circuit.data


def test_frame_has_one_pauli_per_cz_and_round_trips_as_text():
    off = compile_native(bound("linear"))
    tw = twirl_native_merged(off.circuit, np.random.default_rng(0))
    assert len(tw.frame) == off.n_cz
    assert all(len(p) == 2 and set(p) <= set("IXYZ") for p in tw.frame)
    assert tuple(tw.frame_str.split(".")) == tw.frame


def test_wrong_length_frame_is_rejected():
    off = compile_native(bound("star"))
    with pytest.raises(ValueError, match="frame has"):
        twirl_native_merged(off.circuit, frame=("XX",))


def test_logical_twirl_leaves_swap_derived_gates_bare():
    """Why the logical arm is only a lower bound on randomized compiling."""
    logical = bound("linear")
    n_logical_2q = sum(1 for i in logical.data
                       if i.operation.name in ("cz", "cx"))
    tw = twirl_logical(logical, np.random.default_rng(0))
    routed = compile_native(logical)
    assert len(tw.frame) == n_logical_2q
    assert routed.n_cz > n_logical_2q, "routing must add gates for this to be a real gap"


# -- the fit ----------------------------------------------------------------- #

def test_ols_matches_the_existing_implementation():
    from cdr import fit_cdr
    x = [0.30, 0.50, 0.70, 0.11]
    y = [0.40, 0.68, 0.92, 0.18]
    a, b, r2 = fit_cdr(x, y)
    out = fit_ols(x, y)
    assert out.a == pytest.approx(a) and out.b == pytest.approx(b)
    assert out.r2 == pytest.approx(r2)


def test_eiv_recovers_a_slope_that_ols_dilutes():
    """Noise in x biases OLS toward zero; subtracting its variance undoes that."""
    rng = np.random.default_rng(0)
    a_true, b_true, sigma = 1.4, 0.05, 0.20
    x_true = rng.uniform(-0.6, 0.6, 60)
    y = a_true * x_true + b_true
    x = x_true + rng.normal(0, sigma, x_true.size)
    ols, eiv = fit_ols(x, y), fit_cdr_eiv(x, y, sigma ** 2)
    assert abs(ols.a - a_true) > 0.15, "the setup must actually dilute"
    assert abs(eiv.a - a_true) < abs(ols.a - a_true) / 3


def test_eiv_equals_ols_when_x_is_noiseless():
    x = np.linspace(-0.5, 0.5, 20)
    y = 1.3 * x + 0.02
    assert fit_cdr_eiv(x, y, 0.0).a == pytest.approx(fit_ols(x, y).a)


def test_deattenuation_is_capped_when_the_spread_collapses():
    """Without the cap a barely-spread training set gives an exploding slope."""
    x = np.array([0.10, 0.11, 0.09, 0.10])
    y = np.array([0.20, 0.23, 0.18, 0.21])
    out = fit_cdr_eiv(x, y, 10.0)          # variance far larger than the spread
    assert out.capped
    assert abs(out.a) <= MAX_DEATTENUATION * abs(fit_ols(x, y).a) + 1e-9


def test_block_variance_uses_the_variance_of_the_mean():
    vals = [0.41, 0.43, 0.39, 0.42, 0.40, 0.44]
    assert block_variance(vals) == pytest.approx(np.var(vals, ddof=1) / len(vals))
    assert block_variance([0.5]) == 0.0


def test_spread_variance_adds_the_frame_term():
    shot_only = shot_variance_mean_z(0.3, 5, 8192)
    with_frames = spread_x_variance(0.3, 5, 8192, [0.30, 0.34, 0.28, 0.33])
    assert with_frames > shot_only
    assert spread_x_variance(0.3, 5, 8192, [0.3]) == pytest.approx(shot_only)


def test_fit_both_reports_both():
    x = [0.1, 0.3, 0.5, 0.7]
    y = [0.2, 0.45, 0.72, 0.95]
    out = fit_both(x, y, 1e-4)
    assert set(out) == {"ols", "eiv"}
    assert out["ols"].method == "ols" and out["eiv"].method == "eiv"
