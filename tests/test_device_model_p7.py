"""P7: a device model pinned to the calibration, with coherent error inside the budget."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

import numpy as np
import pytest
from qiskit import QuantumCircuit

from sim import device_model as dm
from sim.fit_coherence import abc, hardware_targets, ladder_statistics

REPO = pathlib.Path(__file__).resolve().parent.parent
RAW = REPO / "calibrations" / "odra_raw_20260803.json"
MAPPED = REPO / "calibrations" / "odra_20260803.json"


@pytest.fixture(scope="module")
def cal():
    return dm.load_calibration(RAW)


def _applied(dev, gate, qubits) -> tuple[float, np.ndarray]:
    """Average fidelity of the channel Aer *actually applies*, and that channel.

    Measured, not rebuilt: one gate in a 5-qubit circuit, ``save_superop``, process
    fidelity against the ideal gate. That is the point -- Aer silently drops an
    all-qubit error for a gate that already has qubit-specific ones, so "I added it" is
    not evidence that it is applied. The idle neighbours are untouched (no schedule), so
    the 5-qubit process fidelity equals the gate's own; ``d`` is the gate's dimension.
    """
    from qiskit.quantum_info import Operator, SuperOp, process_fidelity
    from qiskit_aer import AerSimulator
    qc = QuantumCircuit(5)
    if gate == "cz":
        qc.cz(*qubits)
    else:
        qc.r(0.7, 0.2, qubits[0])
    ideal = Operator(qc)
    qc.save_superop()
    so = AerSimulator(method="superop", noise_model=dev.noise_model).run(qc).result() \
        .data(0)["superop"]
    d = 2 ** len(qubits)
    fp = process_fidelity(SuperOp(so), target=ideal)
    return (d * fp + 1) / (d + 1), np.asarray(so)


# --------------------------------------------------------------------------- #
# Calibration                                                                    #
# --------------------------------------------------------------------------- #

def test_phys_matches_the_hardware_runner():
    src = (REPO / "run_hardware.py").read_text()
    m = re.search(r"^PHYS = (\[.*\])", src, re.M)
    assert tuple(json.loads(m.group(1).replace("'", '"'))) == dm.ODRA_PHYS


def test_raw_calibration_is_mapped_through_phys(cal):
    raw = json.loads(RAW.read_text())["raw"]
    for logical, phys in enumerate(dm.ODRA_PHYS):
        assert cal.t1[logical] == raw["t1"][phys]
        assert cal.t2[logical] == raw["t2"][phys]
        assert cal.e01[logical] == raw["readout"][phys]["error_0_to_1"]
        assert cal.e10[logical] == raw["readout"][phys]["error_1_to_0"]
    assert cal.per_gate


def test_per_gate_fidelities_are_irb_and_prx_rb(cal):
    obs = json.loads(RAW.read_text())["raw"]["observations"]
    for (a, b), f in cal.f_cz.items():
        pa, pb = dm.ODRA_PHYS[a], dm.ODRA_PHYS[b]
        keys = [k for k in obs if k.startswith("metrics.irb.cz.")
                and {pa, pb} == set(k.split(".")[4].split("__"))]
        assert len(keys) == 1 and obs[keys[0]]["value"] == f
    # IRB of the CZ is better than the 2q Clifford RB the mapped file carries
    mapped = json.loads(MAPPED.read_text())
    assert min(cal.f_cz.values()) > 1 - mapped["p_2q"]


def test_readout_is_asymmetric(cal):
    assert np.all(cal.e10 > cal.e01)


def test_mapped_calibration_warns():
    with pytest.warns(UserWarning, match="per-Clifford"):
        c = dm.load_calibration(MAPPED)
    assert not c.per_gate


# --------------------------------------------------------------------------- #
# Error budget                                                                   #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("theta,phi", [(0.0, 0.0), (0.02, 0.0), (0.05, 0.03)])
def test_applied_cz_fidelity_equals_irb_for_every_theta(cal, theta, phi):
    dev = dm.build_noise_model(cal, theta, phi)
    assert not any(b["exceeded"] for b in dev.budget)
    for (a, b), target in cal.f_cz.items():
        for qs in ((a, b), (b, a)):
            f, _ = _applied(dev, "cz", qs)
            assert f == pytest.approx(target, abs=1e-8), (qs, theta)


def test_coherent_term_is_applied_on_every_pair(cal):
    """The coherent part must reach the simulator, on every pair and direction."""
    base = dm.build_noise_model(cal, 0.0)
    coh = dm.build_noise_model(cal, 0.03)
    for (a, b) in dm.STAR_EDGES:
        for qs in ((a, b), (b, a)):
            assert not np.allclose(_applied(base, "cz", qs)[1], _applied(coh, "cz", qs)[1])


def test_applied_prx_fidelity_equals_rb(cal):
    dev = dm.build_noise_model(cal)
    for q in range(5):
        assert _applied(dev, "r", (q,))[0] == pytest.approx(cal.f_prx[q], abs=1e-8)


def test_ramsey_t2_inside_gates_overruns_two_prx(cal):
    """Why echo T2 is the default: with T2* the thermal part alone is over budget."""
    with pytest.warns(UserWarning, match=r"r\[0\] \(thermal"):
        dev = dm.build_noise_model(cal, gate_t2="ramsey")
    over = [b for b in dev.budget if b["exceeded"]]
    assert {b["qubits"] for b in over} == {(0,), (3,)}
    assert all(b["cause"] == "thermal" for b in over)
    assert all(f < t for f, t in ((_applied(dev, "r", b["qubits"])[0], b["f_target"])
                                  for b in over))


def test_budget_exceeded_is_flagged_not_hidden(cal):
    with pytest.warns(UserWarning, match=r"cz\[0, 1\] \(coherent"):
        dev = dm.build_noise_model(cal, 0.25)
    cz = [b for b in dev.budget if b["gate"] == "cz"]
    assert all(b["exceeded"] and b["cause"] == "coherent" for b in cz)


def test_no_warning_at_theta_zero(cal):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dm.build_noise_model(cal)


def test_match_depolarizing_is_linear_in_p():
    from qiskit_aer.noise import thermal_relaxation_error
    base = thermal_relaxation_error(20e-6, 10e-6, 60e-9).tensor(
        thermal_relaxation_error(15e-6, 8e-6, 60e-9))
    p, f0, ex = dm.match_depolarizing(base, 0.99, 2)
    assert not ex and 0 < p < 1
    assert (1 - p) * f0 + p / 4 == pytest.approx(0.99, abs=1e-12)


# --------------------------------------------------------------------------- #
# Circuit preparation                                                            #
# --------------------------------------------------------------------------- #

def _native() -> QuantumCircuit:
    qc = QuantumCircuit(5)
    qc.r(0.7, 0.2, 0)
    qc.cz(0, 1)
    qc.r(-1.1, 0.4, 1)
    qc.id(2)
    qc.cz(0, 3)
    qc.measure_all()
    return qc


def test_over_rotation_is_relative(cal):
    dev = dm.build_noise_model(cal, eps_prx=0.01, with_idle=False)
    got = [tuple(i.operation.params) for i in dev.prepare(_native()).data
           if i.operation.name == "r"]
    assert got[0] == pytest.approx((0.7 * 1.01, 0.2))
    assert got[1] == pytest.approx((-1.1 * 1.01, 0.4))


def test_prepare_drops_id_and_schedules_idle(cal):
    with_idle = dm.build_noise_model(cal).prepare(_native())
    without = dm.build_noise_model(cal, with_idle=False).prepare(_native())
    assert "id" not in with_idle.count_ops() and "id" not in without.count_ops()
    assert with_idle.count_ops().get("delay", 0) > 0
    assert with_idle.count_ops().get("quantum_channel", 0) == with_idle.count_ops()["delay"]
    assert "delay" not in without.count_ops()
    # nothing was transpiled: the gate sequence is the input's
    strip = lambda c: [(i.operation.name, [c.find_bit(q).index for q in i.qubits])
                       for i in c.data if i.operation.name in ("r", "cz")]
    assert strip(with_idle) == strip(_native())


def test_dd_dephases_idle_qubits_at_echo_t2(cal):
    """DD changes only the idle channel: same gates, same delays, slower dephasing."""
    from qiskit.quantum_info import Operator, SuperOp
    qc = QuantumCircuit(5)
    qc.r(np.pi / 2, 0.0, 1)
    qc.barrier()            # otherwise ALAP moves the first pulse next to the second
    for _ in range(10):
        qc.cz(0, 2)
    qc.r(np.pi / 2, 0.0, 1)
    off = dm.build_noise_model(cal, dd=False)
    on = dm.build_noise_model(cal, dd=True)
    assert off.prepare(qc).count_ops()["delay"] == on.prepare(qc).count_ops()["delay"]
    qc.measure_all()
    p_off = off.run([qc], 40000, seed=1)[0]
    p_on = on.run([qc], 40000, seed=1)[0]
    # qubit 1 runs a Ramsey sequence across the idle window; dephasing pulls P(1)
    # from ~1 towards 0.5, less so when it dephases at the slower echo T2
    one = lambda c: sum(v for k, v in c.items() if k[-2] == "1") / sum(c.values())
    assert one(p_on) > one(p_off) + 0.005
    assert np.all(cal.t2_echo >= cal.t2)


def test_schedule_options(cal):
    for sched in ("alap", "asap"):
        out = dm.build_noise_model(cal, schedule=sched).prepare(_native())
        assert out.count_ops().get("delay", 0) > 0
    with pytest.raises(ValueError):
        dm.build_noise_model(cal, schedule="later")
    tags = {dm.build_noise_model(cal, schedule=s).tag for s in ("alap", "asap")}
    assert len(tags) == 2


def test_prepare_rejects_non_native(cal):
    qc = QuantumCircuit(5)
    qc.cx(0, 1)
    with pytest.raises(ValueError):
        dm.build_noise_model(cal).prepare(qc)


def test_theta_changes_the_outcome(cal):
    """Guard against the silent-drop trap end to end: same seed, different theta."""
    qc = QuantumCircuit(5)
    qc.r(np.pi / 2, np.pi / 2, range(5))
    for _ in range(6):
        for q in range(1, 5):
            qc.cz(0, q)
    qc.r(np.pi / 2, 0.0, range(5))
    qc.measure_all()
    a = dm.build_noise_model(cal, 0.0).run([qc], 20000, seed=3)[0]
    with pytest.warns(UserWarning):
        b = dm.build_noise_model(cal, 0.3).run([qc], 20000, seed=3)[0]
    keys = set(a) | set(b)
    tv = 0.5 * sum(abs(a.get(k, 0) - b.get(k, 0)) for k in keys) / 20000
    assert tv > 0.05


# --------------------------------------------------------------------------- #
# CLI                                                                            #
# --------------------------------------------------------------------------- #

def _args(**kw):
    ns = argparse.Namespace(sim_device=str(RAW), sim_theta=0.0, sim_phi=0.0, sim_eps=0.0,
                            sim_no_idle=False, submit=False, sim_gate_t2="echo",
                            sim_schedule="alap")
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def test_from_args_refuses_hardware_and_other_devices():
    with pytest.raises(SystemExit):
        dm.from_args(_args(submit=True))
    with pytest.raises(SystemExit):
        dm.from_args(_args(), "garnet")
    assert dm.from_args(_args(sim_device=None)) is None
    assert isinstance(dm.from_args(_args()), dm.DeviceModel)


RUNNERS = ["run_garnet_twirl.py", "run_odra_cdr.py", "zne_shot_boundary.py",
           "random_mirror_benchmark.py", "run_hardware.py"]


@pytest.mark.parametrize("runner", RUNNERS)
def test_runners_offer_sim_device_and_one_compile_path(runner):
    out = subprocess.run([sys.executable, runner, "--help"], cwd=REPO,
                         capture_output=True, text=True, timeout=120).stdout
    for flag in ("--sim-device", "--sim-theta", "--sim-phi", "--sim-eps", "--sim-schedule",
                 "--legacy-transpile", "--allow-archive-write"):
        assert flag in out, (runner, flag)
    src = (REPO / runner).read_text()
    assert "compile_native" in src and "guard_archive(args.out" in src


@pytest.mark.parametrize("runner", ["run_garnet_twirl.py", "zne_shot_boundary.py"])
def test_default_out_no_longer_overwrites_the_archive(runner):
    """Every default --out is an archived CSV; a run without --out must refuse."""
    res = subprocess.run([sys.executable, runner, "--device", "odra", "--no-provenance"],
                         cwd=REPO, capture_output=True, text=True, timeout=120)
    assert res.returncode != 0 and "archived result" in (res.stdout + res.stderr)


def test_guard_archive_allows_campaign_dirs(tmp_path):
    from qem.provenance import guard_archive
    assert guard_archive("results_sim/x.csv") == "results_sim/x.csv"
    assert guard_archive("runs/a/b.csv") == "runs/a/b.csv"
    assert guard_archive(str(tmp_path / "y.csv")) == str(tmp_path / "y.csv")
    assert guard_archive("odra_twirl_o1.csv", allow=True) == "odra_twirl_o1.csv"
    with pytest.raises(SystemExit):
        guard_archive("odra_twirl_o1.csv")


def test_manifest_entry_is_json(cal):
    json.dumps(dm.manifest_entry(dm.build_noise_model(cal)))


# --------------------------------------------------------------------------- #
# fit_coherence plumbing                                                         #
# --------------------------------------------------------------------------- #

def test_hardware_statistics():
    hw, s_r2, s_lr = hardware_targets(["odra_twirl_o1.csv", "odra_twirl_o2.csv"])
    assert sorted(hw.index) == ["all_to_all", "circular", "linear", "star"]
    assert hw["r2_off"].between(0, 1).all()
    assert (hw["log_ratio"] < 0).all()          # twirling helped at every point
    assert s_r2 > 0 and s_lr > 0


def test_ladder_statistics_pairs_on_and_off():
    import pandas as pd
    st = ladder_statistics(pd.read_csv(REPO / "odra_twirl_o1.csv"))
    row = st[st.pattern == "star"].iloc[0]
    assert row.log_ratio == pytest.approx(np.log(0.0232 / 0.0584))
    assert row.r2_off == pytest.approx(0.9711)


def test_distance_counts_simulation_noise():
    import pandas as pd
    from sim.fit_coherence import distances
    hw = pd.DataFrame({"r2_off": [0.7], "log_ratio": [-1.0]}, index=["star"])
    one = pd.DataFrame({"pattern": ["star"], "r2_off": [0.8], "log_ratio": [-1.0]})
    noisy = pd.DataFrame({"pattern": ["star"] * 2, "r2_off": [0.7, 0.9],
                          "log_ratio": [-1.0, -1.0]})
    # same mean, but the two noisy draws widen the denominator
    assert distances(noisy, hw, 0.1, 0.5, ["star"]) < distances(one, hw, 0.1, 0.5, ["star"])
    assert distances(one, hw, 0.1, 0.5, ["star"]) == pytest.approx(1.0)


def test_benchmark_uses_disjoint_reference_points():
    from sim.bench_cdr_variants import reference_points
    ref = reference_points()
    assert ref.shape == (100, 8)
    # repetition r takes points r*8 .. r*8+7: twelve repetitions never share a target
    blocks = [tuple(map(tuple, ref[r * 8:(r + 1) * 8])) for r in range(12)]
    assert len({p for b in blocks for p in b}) == 96


def test_abc_weights():
    import pandas as pd
    t = pd.DataFrame({"d2": [4.0, 0.0, 2.0]})
    w = abc(t)
    assert w.sum() == pytest.approx(1.0) and w.idxmax() == 1
    assert w[0] / w[1] == pytest.approx(np.exp(-2.0))
