"""P2 acceptance: the whole arm pipeline on two ladder points, on the simulator."""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest
from qiskit_aer import AerSimulator

from analysis.rebuild_from_counts import rebuild
from ansatz import HardwareEfficientAnsatz
from noisy_sim import (IQM_BASIS_GATES, build_noise_model, load_iqm_calibration,
                       observable_coeffs, perqubit_z_from_counts, readout_observable)
from qem.arms import plan_arm
from qem.cdr_fit import block_variance, fit_both, shot_variance_mean_z
from qem.cdr_training import build_training_set, clifford_ideal_expval
from qem.compile import compile_native, cz_skeleton
from qem.provenance import RunRecorder
from qem.twirl import rebuild_from_frame, twirl_native_merged

CAL = pathlib.Path("calibrations/odra_20260803.json")
#: two ladder points: no routing, and heavy routing
LADDER = [("star", 12), ("circular", 39)]


def _bound(pattern: str, seed: int):
    rng = np.random.default_rng(seed)
    ans = HardwareEfficientAnsatz(5, 3, num_features=8, entanglement=pattern)
    circ = ans.build()
    wp, xp = ans.weight_parameters(circ), ans.feature_parameters(circ)
    cw = circ.assign_parameters(dict(zip(wp, rng.uniform(-np.pi, np.pi, len(wp)))))
    return cw.assign_parameters(dict(zip(xp, rng.uniform(-1, 1, len(xp)))))


@pytest.mark.slow
@pytest.mark.parametrize("arm", ["off_copies", "spread"])
@pytest.mark.parametrize("pattern,expected_cz", LADDER)
def test_arm_runs_end_to_end_and_rebuilds(tmp_path: pathlib.Path, arm, pattern,
                                          expected_cz):
    """plan -> compile -> twirl -> execute -> record -> rebuild -> fit.

    Small on purpose (n_train=3, M=2, 256 shots): this checks that the pieces fit
    together and that the archive is complete, not that the physics comes out a
    particular way.
    """
    cal = load_iqm_calibration(CAL)
    sim = AerSimulator(noise_model=build_noise_model(cal, idle_t2=cal.t2),
                       coupling_map=cal.coupling_map, basis_gates=IQM_BASIS_GATES)
    obs = readout_observable(5, "mean")
    coeffs = observable_coeffs(obs, 5)

    n_train, n_frames, shots = 3, 2, 256
    plan = plan_arm(arm, n_train=n_train, n_frames=n_frames, shots=shots)

    target = compile_native(_bound(pattern, seed=11))
    assert target.n_cz == expected_cz, "the ladder moved; check DATA_NOTES"

    n_distinct = plan.n_distinct_training_circuits
    train = build_training_set(target.circuit, n_train=n_distinct, target_index=0,
                               window_id="smoke")
    assert all(cz_skeleton(t) == target.cz_skeleton for t in train)

    rec = RunRecorder.open("p2smoke", window_id=f"{arm}_{pattern}", root=tmp_path,
                           args={"arm": arm}, seed=11)
    rng = np.random.default_rng(5)
    measured: dict[int | None, list[float]] = {}

    for spec in plan.specs:
        circ = target.circuit if spec.role == "target" else train[spec.train_index]
        frame_str = ""
        if spec.twirl:
            tw = twirl_native_merged(circ, rng)
            circ, frame_str = tw.circuit, tw.frame_str
        run_circ = circ.copy()
        run_circ.measure_all()
        counts = sim.run(run_circ, shots=spec.shots).result().get_counts()
        value = float(np.dot(coeffs, perqubit_z_from_counts(counts, 5)))
        measured.setdefault(spec.train_index, []).append(value)
        rec.record_circuit(f"{pattern}/{spec.circuit_id}", counts, native=run_circ,
                           with_qasm=False, arm=arm, twirl=spec.twirl,
                           twirl_kind=spec.twirl_kind, frame=frame_str,
                           train_index=spec.train_index, expval=value,
                           coeffs=list(map(float, coeffs)), reduction="dot_perqubit")
    rec.close()

    # the archive must reproduce every value it stored
    res = rebuild(rec.dir)
    assert res["mismatches"] == [], res["mismatches"][:3]
    assert len(res["records"]) == plan.n_circuits
    assert sum(r["shots"] for r in res["records"]) == plan.total_shots

    # every recorded frame must reconstruct the circuit that ran
    checked_frames = 0
    for line in rec.counts_path.read_text().splitlines():
        r = json.loads(line)
        if not r.get("frame"):
            continue
        base = target.circuit if r["train_index"] is None else train[r["train_index"]]
        again = rebuild_from_frame(base, r["frame"])
        assert len(r["frame"].split(".")) == target.n_cz
        # the record stores the measured circuit's counts, so compare against those
        assert again.count_ops().get("cz", 0) == r["n_cz"]
        assert again.count_ops().get("r", 0) == r["n_prx"]
        assert cz_skeleton(again) == target.cz_skeleton
        checked_frames += 1
    if plan.specs[0].twirl:
        assert checked_frames == plan.n_circuits, "every twirled circuit needs a frame"
    else:
        assert checked_frames == 0

    # and the fit must run on what was measured
    xs, ys, vxs = [], [], []
    for idx, vals in measured.items():
        if idx is None:
            continue
        xs.append(float(np.mean(vals)))
        ys.append(clifford_ideal_expval(train[idx], obs))
        vxs.append(block_variance(vals) if len(vals) > 1
                   else shot_variance_mean_z(xs[-1], 5, shots))
    fits = fit_both(xs, ys, vxs)
    for fit in fits.values():
        assert np.isfinite(fit.a) and np.isfinite(fit.b)
        assert -1.5 <= fit.apply(float(np.mean(measured[None]))) <= 1.5
