"""P1: one deterministic compilation path, and single-qubit fusion that is exact."""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import SparsePauliOp, Statevector

from ansatz import HardwareEfficientAnsatz
from qem.compile import PHYS_IDENTITY, compile_native, cz_skeleton
from qem.merge1q import max_prx_run, merge_prx, prx_upper_bound
from topology import star_coupling_map
from zne_dryrun import IQM_BASIS_GATES, native_transpile

PATTERNS = ["star", "linear", "circular", "all_to_all"]
SNAPSHOT = pathlib.Path(__file__).parent / "data" / "compile_snapshot_qiskit241.json"
#: Above this the fusion is suspiciously weak; it is a smell, not a contract, because
#: the ratio depends on how redundant the transpiler's output happened to be.
MERGE_RATIO_WARN = 0.75


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


@pytest.mark.parametrize("pattern", PATTERNS)
def test_merge_preserves_the_observable(pattern: str):
    """<Z_i> must be untouched: fusion is an identity on the circuit's action."""
    off = compile_native(bound(pattern), merge_1q=False).circuit
    assert np.abs(zexp(merge_prx(off)) - zexp(off)).max() < 1e-10


@pytest.mark.parametrize("pattern", PATTERNS)
def test_merge_preserves_the_cz_skeleton(pattern: str):
    off = compile_native(bound(pattern), merge_1q=False).circuit
    assert cz_skeleton(merge_prx(off)) == cz_skeleton(off)


@pytest.mark.parametrize("pattern", PATTERNS)
def test_no_two_prx_survive_without_a_cz_between_them(pattern: str):
    """The structural guarantee. Exact, unlike a gate-count ratio."""
    off = compile_native(bound(pattern), merge_1q=False).circuit
    assert max_prx_run(merge_prx(off)) <= 1


@pytest.mark.parametrize("pattern", PATTERNS)
def test_prx_count_respects_the_structural_bound(pattern: str):
    merged = compile_native(bound(pattern), merge_1q=True)
    assert merged.n_prx <= prx_upper_bound(merged.n_cz, 5)


@pytest.mark.parametrize("pattern", PATTERNS)
def test_merge_ratio_is_reported_and_not_alarming(pattern: str):
    off = compile_native(bound(pattern), merge_1q=False)
    on = compile_native(bound(pattern), merge_1q=True)
    ratio = on.n_prx / off.n_prx
    assert ratio <= MERGE_RATIO_WARN, (
        f"{pattern}: fusion left {ratio:.3f} of the single-qubit gates, above the "
        f"{MERGE_RATIO_WARN} smell threshold -- check that RZ is still being commuted "
        f"through CZ")


def test_merge_rejects_a_non_native_gate():
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    with pytest.raises(ValueError, match="native circuit"):
        merge_prx(qc)


# -- the single compilation path -------------------------------------------- #

@pytest.mark.parametrize("pattern", PATTERNS)
def test_compilation_is_deterministic(pattern: str):
    """Five compilations of one circuit must give one skeleton.

    The unseeded path does not: that is the defect this module exists to remove.
    """
    circ = bound(pattern)
    skeletons = {compile_native(circ).cz_skeleton for _ in range(5)}
    assert len(skeletons) == 1


@pytest.mark.parametrize("pattern", ["linear", "circular", "all_to_all"])
def test_legacy_path_is_nondeterministic_regression(pattern: str):
    """Documented regression: the old path is unstable for every routed pattern.

    Kept as a test so the claim in DATA_NOTES.md stays checkable rather than becoming
    folklore. star is excluded because it needs no routing and is stable there.
    """
    circ = bound(pattern)
    skeletons = {cz_skeleton(native_transpile(circ, 5)) for _ in range(5)}
    assert len(skeletons) > 1


def test_compile_reports_layout_and_counts():
    out = compile_native(bound("linear"))
    assert out.layout == tuple(PHYS_IDENTITY)
    assert out.n_cz == len(out.cz_skeleton)
    assert out.merged is True
    assert out.n_prx > 0 and out.depth > 0


def test_same_skeleton_as_is_symmetric_and_strict():
    a = compile_native(bound("star"))
    b = compile_native(bound("star"))
    c = compile_native(bound("all_to_all"))
    assert a.same_skeleton_as(b) and b.same_skeleton_as(a)
    assert not a.same_skeleton_as(c)


def test_snapshot_matches_this_environment():
    """The recorded reference values, re-measured.

    A mismatch is not automatically a failure of the code -- it means the environment
    moved, and every comparison with the archived campaigns needs re-checking. Failing
    loudly here is the point.
    """
    snap = json.loads(SNAPSHOT.read_text())
    for pattern, rec in snap["patterns"].items():
        fixed = rec["fixed_layout_seed42"]
        off = compile_native(bound(pattern), merge_1q=False)
        on = compile_native(bound(pattern), merge_1q=True)
        assert off.n_cz == fixed["n_cz"], f"{pattern}: CZ ladder moved"
        assert off.n_prx == fixed["n_prx_before_merge"], f"{pattern}: PRX before merge moved"
        assert on.n_prx == fixed["n_prx_after_merge"], f"{pattern}: PRX after merge moved"
