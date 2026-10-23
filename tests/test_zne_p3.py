"""P3: ZNE without the silent fallback, matched-cost folding controls, W_neg and kappa."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import warnings

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from qem.compile import compile_native, cz_skeleton
from qem.folding import FOLD_VARIANTS, fold_native, identity_block, random_angle_twin
from qem.zne import (ZNEEstimate, diagnose_point, expval_se, extrapolate_flagged,
                     floor_prediction, floor_tracking, kappa_opt, kappa_uniform,
                     negativity, neyman_allocation, per_shot_variance, probabilities,
                     richardson_coefficients, uniform_allocation)
from zne_dryrun import extrapolate

REPO = pathlib.Path(__file__).resolve().parent.parent
PATTERNS = ["star", "linear", "circular", "all_to_all"]
NODE_SETS = [[1, 3], [1, 3, 5], [1, 3, 5, 7]]


def bound(pattern: str, seed: int = 1) -> QuantumCircuit:
    rng = np.random.default_rng(seed)
    ans = HardwareEfficientAnsatz(5, 3, num_features=8, entanglement=pattern)
    circ = ans.build()
    wp, xp = ans.weight_parameters(circ), ans.feature_parameters(circ)
    return circ.assign_parameters({
        **dict(zip(wp, rng.uniform(-np.pi, np.pi, len(wp)))),
        **dict(zip(xp, rng.uniform(-1, 1, len(xp))))})


def counts_from_probs(p: np.ndarray, shots: int = 10 ** 9) -> dict[str, int]:
    """Counts in Qiskit's bit order whose frequencies are ``p`` to ~1e-9."""
    n = int(np.log2(len(p)))
    return {format(i, f"0{n}b"): int(round(x * shots)) for i, x in enumerate(p) if x > 0}


# --------------------------------------------------------------------------- #
# kappa and Neyman allocation                                                    #
# --------------------------------------------------------------------------- #

def test_richardson_coefficients_135():
    np.testing.assert_allclose(richardson_coefficients([1, 3, 5]), [15 / 8, -5 / 4, 3 / 8])


@pytest.mark.parametrize("scales", NODE_SETS)
def test_richardson_coefficients_sum_to_one(scales):
    assert richardson_coefficients(scales).sum() == pytest.approx(1.0, abs=1e-12)


def test_kappa_uniform_matches_spec():
    """Spec P3 acceptance: 4.0 / 14.656 / 44.5625."""
    got = [kappa_uniform(s) for s in NODE_SETS]
    np.testing.assert_allclose(got, [4.0, 14.65625, 44.5625], atol=1e-12)


def test_kappa_opt_equal_sigma_matches_spec():
    """Spec P3 acceptance: 3.0 / 11.25 / 35.0."""
    got = [kappa_opt(s) for s in NODE_SETS]
    np.testing.assert_allclose(got, [3.0, 11.25, 35.0], atol=1e-12)


def test_runner_kappa_is_the_module_kappa():
    from zne_shot_boundary import richardson_kappa
    for s in NODE_SETS:
        k, c = richardson_kappa(s)
        assert k == kappa_uniform(s)
        np.testing.assert_allclose(c, richardson_coefficients(s))


@pytest.mark.parametrize("scales", NODE_SETS)
def test_neyman_never_worse_than_uniform(scales):
    """The Neyman variance (sum |c| sigma)^2 / S is a minimum over allocations."""
    rng = np.random.default_rng(0)
    c = richardson_coefficients(scales)
    for _ in range(200):
        sig = rng.uniform(0.2, 1.0, len(scales))
        var_uniform = len(c) * np.sum(c ** 2 * sig ** 2)            # times 1/S
        var_neyman = np.sum(np.abs(c) * sig) ** 2
        assert var_neyman <= var_uniform + 1e-12
        assert kappa_opt(scales, sig) == pytest.approx(var_neyman / sig[0] ** 2 - 1)


@pytest.mark.parametrize("total", [3, 7, 128, 1000, 4096, 8191])
def test_neyman_allocation_spends_exactly_the_budget(total):
    alloc = neyman_allocation(total, [1, 3, 5], [0.45, 0.4, 0.3])
    assert sum(alloc) == total
    assert min(alloc) >= 1


def test_neyman_allocation_is_proportional():
    sig = np.array([0.45, 0.40, 0.30])
    alloc = np.array(neyman_allocation(10 ** 6, [1, 3, 5], sig))
    w = np.abs(richardson_coefficients([1, 3, 5])) * sig
    np.testing.assert_allclose(alloc / alloc.sum(), w / w.sum(), atol=1e-5)


def test_neyman_allocation_rejects_too_small_budget():
    with pytest.raises(ValueError):
        neyman_allocation(2, [1, 3, 5])


def test_uniform_allocation_is_the_archived_split():
    assert uniform_allocation(1000, [1, 3, 5]) == [333, 333, 333]


# --------------------------------------------------------------------------- #
# Extrapolation flags                                                            #
# --------------------------------------------------------------------------- #

def test_overshoot_is_reported_not_replaced():
    vals = [0.9, 0.3, 0.05]                       # Richardson gives 1.33
    est = extrapolate_flagged([1, 3, 5], vals)
    assert est.unphysical and not est.fallback_used
    assert est.value == est.raw_value
    assert est.value == pytest.approx(np.polyval(np.polyfit([1, 3, 5], vals, 2), 0.0))


def test_legacy_clamp_still_falls_back_and_says_so():
    est = extrapolate_flagged([1, 3, 5], [0.9, 0.3, 0.05], legacy_clamp=True)
    assert est.fallback_used and est.unphysical
    assert est.value == extrapolate([1, 3, 5], [0.9, 0.3, 0.05], "richardson")


def test_physical_estimate_carries_no_flag():
    est = extrapolate_flagged([1, 3, 5], [0.5, 0.4, 0.3])
    assert not est.unphysical and not est.fallback_used


@pytest.mark.parametrize("kind", ["linear", "richardson", "exponential"])
def test_legacy_clamp_is_bit_identical_to_the_old_function(kind):
    rng = np.random.default_rng(3)
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")          # curve_fit on random data
        for _ in range(300):
            y = rng.uniform(-1, 1, 3)
            assert extrapolate_flagged([1, 3, 5], y, kind, legacy_clamp=True).value \
                == extrapolate([1, 3, 5], y, kind)


def test_old_function_flag_mode():
    est = extrapolate([1, 3, 5], [0.9, 0.3, 0.05], "richardson", on_unphysical="flag")
    assert isinstance(est, ZNEEstimate) and est.unphysical
    assert isinstance(extrapolate([1, 3, 5], [0.5, 0.4, 0.3], "richardson"), float)
    with pytest.raises(ValueError):
        extrapolate([1, 3, 5], [0.5, 0.4, 0.3], "richardson", on_unphysical="ignore")


# --------------------------------------------------------------------------- #
# Folding controls                                                               #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def natives():
    return {p: compile_native(bound(p)).circuit for p in PATTERNS}


@pytest.mark.parametrize("pattern", PATTERNS)
@pytest.mark.parametrize("scale", [1, 3, 5, 7])
def test_variants_have_identical_cost(natives, pattern, scale):
    """Same CZ skeleton, CZ count and PRX count -- per qubit -- at every scale."""
    folded = [fold_native(natives[pattern], scale, v, seed=5) for v in FOLD_VARIANTS]
    skeletons = {cz_skeleton(f) for f in folded}
    assert len(skeletons) == 1
    assert len(next(iter(skeletons))) == scale * natives[pattern].count_ops()["cz"]

    def prx_per_qubit(c):
        out = [0] * c.num_qubits
        for inst in c.data:
            if inst.operation.name == "r":
                out[c.find_bit(inst.qubits[0]).index] += 1
        return out

    assert len({tuple(prx_per_qubit(f)) for f in folded}) == 1
    assert len({f.count_ops().get("barrier", 0) for f in folded}) == 1


@pytest.mark.parametrize("pattern", PATTERNS)
@pytest.mark.parametrize("scale", [3, 5])
def test_genuine_and_identity_preserve_the_state(natives, pattern, scale):
    u = natives[pattern]
    ref = Statevector.from_instruction(u)
    for v in ("genuine", "identity"):
        got = Statevector.from_instruction(fold_native(u, scale, v))
        assert abs(abs(got.inner(ref)) - 1.0) < 1e-10, v


@pytest.mark.parametrize("pattern", PATTERNS)
def test_garbage_changes_the_state_above_scale_one(natives, pattern):
    u = natives[pattern]
    ref = Statevector.from_instruction(u)
    assert abs(abs(Statevector.from_instruction(
        fold_native(u, 1, "garbage", seed=5)).inner(ref)) - 1) < 1e-10
    for scale in (3, 5):
        got = Statevector.from_instruction(fold_native(u, scale, "garbage", seed=5))
        assert abs(got.inner(ref)) < 1 - 1e-3


def test_folding_never_transpiles(natives):
    """Only native gates and barriers come out; nothing was re-routed or merged."""
    for u in natives.values():
        for v in FOLD_VARIANTS:
            f = fold_native(u, 5, v, seed=1, measure=True)
            assert set(f.count_ops()) <= {"r", "cz", "barrier", "measure"}


def test_garbage_is_reproducible_from_its_seed(natives):
    u = natives["linear"]
    a, b = (fold_native(u, 5, "garbage", seed=9) for _ in range(2))
    assert a == b
    assert fold_native(u, 5, "garbage", seed=10) != a


def test_twin_and_identity_block_shapes(natives):
    u = natives["circular"]
    v = random_angle_twin(u, np.random.default_rng(0))
    assert cz_skeleton(v) == cz_skeleton(u)
    assert v.count_ops()["r"] == u.count_ops()["r"]
    blk = identity_block(u)
    assert abs(abs(Statevector.from_instruction(blk).inner(
        Statevector.from_label("0" * 5))) - 1) < 1e-10


def test_fold_rejects_bad_input(natives):
    u = natives["star"]
    with pytest.raises(ValueError):
        fold_native(u, 2)
    with pytest.raises(ValueError):
        fold_native(u, 3, "nonsense")
    m = u.copy()
    m.measure_all()
    with pytest.raises(ValueError):
        fold_native(m, 3)


# --------------------------------------------------------------------------- #
# W_neg, floor, retention                                                        #
# --------------------------------------------------------------------------- #

def _random_simplex(rng, n=32):
    p = rng.uniform(0.1, 1.0, n)
    return p / p.sum()


def test_exact_polynomial_decay_gives_no_negativity():
    """If P_s(lambda) is quadratic in lambda, Richardson on {1,3,5} recovers P_s(0)."""
    rng = np.random.default_rng(1)
    p0, uniform = _random_simplex(rng), np.full(32, 1 / 32)
    # depolarizing-like mixing towards uniform, quadratic in lambda and valid for lambda<=5
    w = lambda lam: 0.06 * lam + 0.01 * lam ** 2
    per_scale = [counts_from_probs((1 - w(l)) * p0 + w(l) * uniform) for l in (1, 3, 5)]
    rep = negativity([1, 3, 5], per_scale, 5)
    assert rep.w_neg == 0.0 and rep.frac_negative == 0.0
    np.testing.assert_allclose(rep.p_hat, p0, atol=1e-6)


def test_destroyed_signal_gives_negativity():
    rng = np.random.default_rng(2)
    p1, p3, p5 = (_random_simplex(rng) for _ in range(3))
    rep = negativity([1, 3, 5], [counts_from_probs(p) for p in (p1, p3, p5)], 5)
    assert rep.w_neg > 0 and rep.frac_negative > 0 and rep.min_p < 0
    assert rep.p_hat.sum() == pytest.approx(1.0, abs=1e-6)


def test_bit_order_iqm_is_the_reverse_of_qiskit():
    rng = np.random.default_rng(4)
    q = {format(i, "05b"): int(c) for i, c in enumerate(rng.integers(1, 50, 32))}
    iqm = {k[::-1]: v for k, v in q.items()}
    np.testing.assert_array_equal(probabilities(q, 5), probabilities(iqm, 5, "iqm"))
    hub = [1.0, 0, 0, 0, 0]
    assert per_shot_variance(q, hub) == per_shot_variance(iqm, hub, "iqm")
    assert expval_se(q, hub) == expval_se(iqm, hub, "iqm")


def test_per_shot_variance_matches_the_runner():
    from zne_shot_boundary import per_shot_variance_from_counts
    rng = np.random.default_rng(5)
    counts = {format(i, "05b"): int(c) for i, c in enumerate(rng.integers(0, 80, 32))}
    for coeffs in ([0.2] * 5, [1, 0, 0, 0, 0], [0.5, 0.1, 0.1, 0.2, 0.1]):
        assert per_shot_variance(counts, coeffs) == pytest.approx(
            per_shot_variance_from_counts(counts, np.array(coeffs), 5), abs=1e-12)


def test_frames_are_pooled():
    a, b = {"00000": 30, "11111": 10}, {"00000": 10, "11111": 30}
    np.testing.assert_allclose(probabilities([a, b], 5)[[0, 31]], [0.5, 0.5])


def test_floor_tracking_is_zero_on_the_floor():
    """Eq. 2: E(3) = E(5) = f makes E_hat exactly c1*E1 + (1-c1)*f."""
    for f in (0.0, 0.12, -0.05):
        vals = [0.4, f, f]
        e_hat = extrapolate_flagged([1, 3, 5], vals).value
        assert e_hat == pytest.approx(floor_prediction([1, 3, 5], 0.4, f))
        assert floor_tracking([1, 3, 5], e_hat, 0.4, f) == pytest.approx(0, abs=1e-12)


def test_diagnose_point_row():
    q = {"00000": 600, "00001": 300, "11111": 100}
    row = diagnose_point([1, 3, 5], [0.5, 0.35, 0.25], ideal=0.6,
                         counts_per_scale=[q, q, q], coeffs=[0.2] * 5, floor=0.0)
    for k in ("ev_lam1", "ev_lam3", "ev_lam5", "zne", "zne_raw", "fallback_used",
              "unphysical", "retention_norm", "retention_R", "snr_lmax", "w_neg",
              "w_neg_marg", "floor_tracking", "rho"):
        assert k in row
    assert row["retention_norm"] == pytest.approx(0.5 / 0.6)
    assert row["w_neg"] == 0.0          # identical distributions extrapolate to themselves


# --------------------------------------------------------------------------- #
# Runner wiring                                                                  #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("runner", ["run_garnet_twirl.py", "run_odra_cdr.py",
                                    "zne_shot_boundary.py"])
def test_runners_offer_legacy_clamp(runner):
    out = subprocess.run([sys.executable, runner, "--help"], cwd=REPO,
                         capture_output=True, text=True, timeout=120).stdout
    assert "--legacy-clamp" in out


def test_shot_boundary_dry_run_neyman_45_reps(tmp_path):
    out = subprocess.run([sys.executable, "zne_shot_boundary.py", "--allocation", "neyman",
                          "--reps", "45", "--no-provenance",
                          "--out", str(tmp_path / "k.csv")], cwd=REPO,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert "kappa_opt = 11.250" in out.stdout
    assert "reps 45" in out.stdout
