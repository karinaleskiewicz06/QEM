"""P7 on the simulator: the CDR-variant regression, the ABC fit, and a runner end to end."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import warnings

import pandas as pd
import pytest

from sim.bench_cdr_variants import paired_test, run_rep, wins
from sim.device_model import build_noise_model

REPO = pathlib.Path(__file__).resolve().parent.parent
RAW = REPO / "calibrations" / "odra_raw_20260803.json"
ENV = {**os.environ, "KMP_DUPLICATE_LIB_OK": "TRUE"}


@pytest.mark.slow
def test_spread_near_target_beats_twirl_native_shared_under_coherent_error():
    """Spec P7 regression, as a property tested per target.

    Coherent model theta = 0.05, phi = 0.03 at the deepest rung (all_to_all; 57 CZ on
    the fixed-layout path, the spec's "54"), on the classifier's reference points. The
    spec asked for ">= 6/8 repetitions"; that criterion sits on the noise because the
    reference arm has a heavy tail. Agreed instead: one-sided paired Wilcoxon over the
    64 (rep, target) pairs at p < 0.05, and a lower mean. The spec's absolute values
    (0.0190 vs 0.0357) came from a weaker, uncalibrated model and are not asserted; see
    results_sim/bench_cdr/README.md.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")          # theta=0.05 exceeds one CZ budget
        dev = build_noise_model(RAW, 0.05, 0.03)
    combos = [("spread", "near_target"), ("twirl_native", "shared_random")]
    rows = []
    for rep in range(8):
        rows += run_rep(dev, "all_to_all", rep, combos=combos)
    df = pd.DataFrame(rows)
    assert set(df.cz) == {57}
    t = paired_test(df, combos[0], combos[1])
    w, _, _ = wins(df, combos[0], combos[1])
    msg = (f"per target {t['n_better']}/{t['n']}, p = {t['p_wilcoxon']:.3g}; "
           f"reps {int(w.sum())}/8; means {t['mean_a']:.4f} vs {t['mean_b']:.4f}")
    assert t["n"] == 64, msg
    assert t["p_wilcoxon"] < 0.05, msg
    assert t["mean_a"] < t["mean_b"], msg


@pytest.mark.slow
def test_fit_coherence_quick(tmp_path):
    res = subprocess.run([sys.executable, "-m", "sim.fit_coherence", "--quick",
                          "--out-dir", str(tmp_path)], cwd=REPO, env=ENV,
                         capture_output=True, text=True, timeout=1200)
    assert res.returncode == 0, res.stderr[-2000:]
    grid = pd.read_csv(tmp_path / "grid.csv")
    assert len(grid) == 2 and grid.weight.sum() == pytest.approx(1.0)
    pred = pd.read_csv(tmp_path / "predictive_check.csv")
    assert set(pred.statistic) == {"r2_off", "log_ratio"}


@pytest.mark.slow
def test_twirl_runner_on_device_model_rebuilds_exactly(tmp_path):
    """--sim-device goes through the runner's own path and archives like hardware."""
    from analysis.rebuild_from_counts import rebuild
    res = subprocess.run(
        [sys.executable, str(REPO / "run_garnet_twirl.py"), "--device", "odra",
         "--sim-device", str(RAW), "--sim-theta", "0.02",
         "--models-dir", str(REPO / "trained_models_hard"),
         "--points", "optimal:star", "--arms", "cdr", "zne", "--eval-points", "2",
         "--shots", "512", "--n-train", "3", "--n-twirl", "2",
         "--campaign", "p7", "--window-id", "w", "--out", "t.csv"],
        cwd=tmp_path, env=ENV, capture_output=True, text=True, timeout=900)
    assert res.returncode == 0, res.stderr[-2000:]
    run_dir = tmp_path / "runs" / "p7" / "w"
    assert rebuild(run_dir)["mismatches"] == []
    assert '"theta_zz": 0.02' in (run_dir / "manifest.json").read_text()
