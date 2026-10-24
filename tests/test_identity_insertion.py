"""P5: identity insertion keeps the function and separates CZ count from duration."""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

import numpy as np
import pytest
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from noisy_sim import readout_observable
from qem.cdr_training import build_training_set, clifford_ideal_expval
from qem.compile import compile_native, cz_skeleton
from qem.folding import FOLD_VARIANTS, fold_native
from qem.identity_insertion import (insert_identity, insertion_slots,
                                    scheduled_duration)
from qem.merge1q import merge_prx
from qem.twirl import twirl_native_merged

REPO = pathlib.Path(__file__).resolve().parent.parent
CAL = REPO / "spec" / "odra_cal_example.json"


@pytest.fixture(scope="module")
def native():
    rng = np.random.default_rng(4)
    ans = HardwareEfficientAnsatz(5, 3, num_features=8, entanglement="star")
    c = ans.build()
    wp, xp = ans.weight_parameters(c), ans.feature_parameters(c)
    b = c.assign_parameters({**dict(zip(wp, rng.uniform(-np.pi, np.pi, len(wp)))),
                             **dict(zip(xp, rng.uniform(-1, 1, len(xp))))})
    return compile_native(b).circuit


def test_slots_are_spread_and_bounded():
    assert insertion_slots(12, 6) == [1, 3, 5, 7, 9, 11]
    s = insertion_slots(12, 20)
    assert len(s) == 20 and min(s) >= 0 and max(s) <= 11
    with pytest.raises(ValueError):
        insertion_slots(0, 3)


@pytest.mark.parametrize("pairs,target", [(6, 24), (12, 36), (20, 52)])
def test_counts_and_function(native, pairs, target):
    ref = Statevector.from_instruction(native)
    cz = insert_identity(native, pairs, "cz_pairs")
    idle = insert_identity(native, pairs, "idle_matched")
    assert cz.count_ops()["cz"] == target and idle.count_ops()["cz"] == 12
    assert cz.count_ops()["r"] == idle.count_ops()["r"] == native.count_ops()["r"]
    for c in (cz, idle):
        assert abs(abs(Statevector.from_instruction(c).inner(ref)) - 1) < 1e-10


@pytest.mark.parametrize("pairs", [6, 12, 20])
def test_idle_matched_has_the_duration_of_cz_pairs(native, pairs):
    d_cz = scheduled_duration(insert_identity(native, pairs, "cz_pairs"))
    d_idle = scheduled_duration(insert_identity(native, pairs, "idle_matched"))
    assert d_cz == pytest.approx(d_idle, rel=1e-12)
    assert d_cz > scheduled_duration(native)


def test_insertion_survives_the_pipeline(native):
    """Twirl, 1q merge, folding and training keep delays, skeleton and Clifford ideals."""
    obs = readout_observable(5, "mean")
    for mode in ("cz_pairs", "idle_matched"):
        c = insert_identity(native, 6, mode)
        tw = twirl_native_merged(c, np.random.default_rng(1)).circuit
        assert cz_skeleton(tw) == cz_skeleton(c)
        assert tw.count_ops().get("delay", 0) == c.count_ops().get("delay", 0)
        # Z-basis readout: probabilities must agree (merging drops trailing Z phases)
        np.testing.assert_allclose(Statevector.from_instruction(tw).probabilities(),
                                   Statevector.from_instruction(c).probabilities(), atol=1e-10)
        assert merge_prx(c).count_ops().get("delay", 0) == c.count_ops().get("delay", 0)
        for v in FOLD_VARIANTS:
            f = fold_native(c, 3, v, seed=2)
            assert f.count_ops()["cz"] == 3 * c.count_ops()["cz"]
        for t in build_training_set(c, n_train=3, target_index=0, window_id="x"):
            assert cz_skeleton(t) == cz_skeleton(c)
            assert np.isfinite(clifford_ideal_expval(t, obs))


def test_delay_reaches_the_iqm_circuit(native):
    from run_hardware import qiskit_to_iqm
    c = insert_identity(native, 2, "idle_matched", t_cz=60e-9)
    c.measure_all()
    ops = [o for o in qiskit_to_iqm(c).instructions if o.name == "delay"]
    assert len(ops) == 4 and all(o.args["duration"] == pytest.approx(120e-9) for o in ops)


def test_p5_night_plan():
    from campaign import odra_window as ow
    a = argparse.Namespace(points=list(ow.NIGHTS["P5"]), cdr_arms=list(ow.NIGHT_ARMS["P5"]),
                           n_train=20, frames=6, shots=8192, no_zne=True, seed=42,
                           window_id="p5")
    counts = ow.plan_counts(a, 8)
    assert len(counts) == 10 and all(n == 1008 for n, _ in counts.values())


def test_p5_dry_run():
    out = subprocess.run([sys.executable, "campaign/odra_window.py", "--dry-run",
                          "--window-id", "p5", "--night", "P5", "--point-set", "0"],
                         cwd=REPO, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert "star_idle52" in out.stdout and "ZNE off" in out.stdout


@pytest.mark.slow
def test_p5_night_in_simulation_and_regression(tmp_path):
    res = subprocess.run([sys.executable, "campaign/odra_window.py", "--sim-device", str(CAL),
                          "--window-id", "p5", "--root", str(tmp_path), "--night", "P5",
                          "--point-set", "0", "--eval-points", "6", "--n-train", "3",
                          "--frames", "2", "--shots", "512"],
                         cwd=REPO, capture_output=True, text=True, timeout=1800)
    assert res.returncode == 0, res.stderr[-2000:]
    w = tmp_path / "odra_campaign" / "p5"
    from analysis.depth_regression import run
    out = run([w], tmp_path / "dr.csv")
    assert {"cz10", "dur_us"} <= set(out.term)
    assert set(out["sample"]) == {"all", "l3_only"}
