"""P3 on the simulator: the W_neg null separates the folds, and the runners write it."""

from __future__ import annotations

import csv
import pathlib
import subprocess
import sys

import numpy as np
import pytest
from qiskit_aer import AerSimulator

from sim.calibrate_wneg_null import depolarizing_model, frozen_targets, run_null

REPO = pathlib.Path(__file__).resolve().parent.parent
CAL = REPO / "calibrations" / "odra_20260803.json"


@pytest.mark.slow
@pytest.mark.parametrize("pattern", ["star", "all_to_all"])
def test_wneg_separates_garbage_from_valid_folds(pattern):
    """Under depolarizing noise every valid fold sits below every garbage fold.

    A property, not a threshold: the threshold itself is fixed by
    ``sim/calibrate_wneg_null.py`` before the campaign.
    """
    targets, ideals, coeffs = frozen_targets("trained_models_hard", pattern, 4)
    sim = AerSimulator(method="density_matrix", noise_model=depolarizing_model(1e-3, 1e-2))
    rows = run_null(targets, ideals, coeffs, sim=sim, shots=8192, scales=[1, 3, 5], seed=1)
    w = {v: [r["w_neg"] for r in rows if r["variant"] == v]
         for v in ("genuine", "identity", "garbage")}
    assert max(w["genuine"] + w["identity"]) < min(w["garbage"])
    # matched cost is what makes the comparison fair
    for r in rows:
        assert r["n_cz_lam3"] == 3 * r["n_cz_lam1"] and r["n_cz_lam5"] == 5 * r["n_cz_lam1"]
    # Eq. 2 is a statement about the genuine estimate; the floor must be measured
    assert all(r["floor"] != "" for r in rows)


@pytest.mark.slow
@pytest.mark.parametrize("legacy", [False, True])
def test_twirl_runner_writes_zne_flags_and_points(tmp_path: pathlib.Path, legacy):
    out = tmp_path / "zne.csv"
    cmd = [sys.executable, "run_garnet_twirl.py", "--device", "odra",
           "--points", "optimal:star", "optimal:all_to_all", "--arms", "zne",
           "--sim", "--calibration", str(CAL), "--eval-points", "2", "--shots", "512",
           "--no-provenance", "--out", str(out)] + (["--legacy-clamp"] if legacy else [])
    res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=900,
                         env={**__import__("os").environ, "KMP_DUPLICATE_LIB_OK": "TRUE"})
    assert res.returncode == 0, res.stderr[-2000:]

    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 2
    for r in rows:
        for k in ("fallback_used", "unphysical", "mean_lam1", "mean_lam3", "mean_lam5",
                  "retention_norm", "snr_lmax", "w_neg", "retention_R"):
            assert r[k] != "", k

    pts = list(csv.DictReader((tmp_path / "zne_zne_points.csv").open()))
    assert len(pts) == 4
    for p in pts:
        assert p["legacy_clamp"] == str(legacy)
        if not legacy:
            assert p["fallback_used"] == "False"
            assert float(p["zne"]) == float(p["zne_raw"])
    # the summary row is the mean of its points
    for r in rows:
        sel = [p for p in pts if p["pattern"] == r["pattern"]]
        assert float(r["err"]) == pytest.approx(
            np.mean([float(p["err_zne"]) for p in sel]), abs=1e-4)
