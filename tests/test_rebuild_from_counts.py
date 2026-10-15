"""P0 acceptance: a result CSV must be re-derivable from counts.jsonl alone."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import numpy as np
import pytest

from analysis.rebuild_from_counts import expval_from_record, perqubit_z, rebuild
from qem.provenance import RunRecorder


def test_perqubit_z_uses_little_endian_bit_order():
    """Qubit q is character -1-q of the bitstring, matching noisy_sim."""
    z = perqubit_z({"00001": 100}, 5)           # only qubit 0 is excited
    assert z[0] == -1.0
    assert list(z[1:]) == [1.0, 1.0, 1.0, 1.0]


def test_rebuild_is_bit_exact_on_a_handcrafted_record(tmp_path: pathlib.Path):
    coeffs = [0.2] * 5
    counts = {"00000": 601, "00001": 423, "10010": 7}
    expected = float(np.dot(coeffs, perqubit_z(counts, 5)))
    rec = RunRecorder.open("t", window_id="w", root=tmp_path)
    rec.record_circuit("p0/a/off", counts, arm="cdr", coeffs=coeffs,
                       expval=expected, spec_index=0, copy_index=0)
    rec.close()
    res = rebuild(rec.dir)
    assert res["mismatches"] == []
    assert res["records"][0]["expval_rebuilt"] == expected


def test_a_corrupted_value_is_detected(tmp_path: pathlib.Path):
    """The check must be exact, not approximate: a last-bit change has to fail."""
    coeffs = [0.2] * 5
    counts = {"00000": 10, "00001": 6}
    true_val = float(np.dot(coeffs, perqubit_z(counts, 5)))
    rec = RunRecorder.open("t", window_id="w", root=tmp_path)
    rec.record_circuit("p0/a/off", counts, arm="cdr", coeffs=coeffs,
                       expval=np.nextafter(true_val, np.inf), spec_index=0, copy_index=0)
    rec.close()
    assert len(rebuild(rec.dir)["mismatches"]) == 1


def test_records_without_coefficients_are_skipped_not_failed(tmp_path: pathlib.Path):
    rec = RunRecorder.open("t", window_id="w", root=tmp_path)
    rec.record_circuit("p0/a/off", {"00000": 4}, arm="raw")
    rec.close()
    res = rebuild(rec.dir)
    assert res["mismatches"] == []
    assert res["records"][0]["expval_rebuilt"] is None


def test_copies_are_averaged_into_one_group(tmp_path: pathlib.Path):
    coeffs = [1.0]
    rec = RunRecorder.open("t", window_id="w", root=tmp_path)
    for i, counts in enumerate(({"0": 10}, {"1": 10})):        # <Z> = +1 and -1
        rec.record_circuit(f"p0/x/c{i}", counts, arm="cdr", coeffs=coeffs,
                           spec_index=0, copy_index=i)
    rec.close()
    groups = rebuild(rec.dir)["groups"]
    assert len(groups) == 1
    assert groups[0]["n_copies"] == 2 and groups[0]["expval_mean"] == 0.0


def test_missing_counts_file_is_reported_clearly(tmp_path: pathlib.Path):
    with pytest.raises(FileNotFoundError, match="no counts.jsonl"):
        rebuild(tmp_path)


@pytest.mark.slow
def test_simulated_window_rebuilds_exactly(tmp_path: pathlib.Path):
    """End-to-end: run a small --sim window, then re-derive every value from counts.

    This is the P0 acceptance criterion. It runs the real runner, so it is slow and
    it fails if the runner's readout convention and the analysis ever diverge.
    """
    repo = pathlib.Path(__file__).resolve().parent.parent
    out_csv = tmp_path / "res.csv"
    cmd = [sys.executable, "run_garnet_twirl.py", "--sim", "--device", "odra",
           "--calibration", "calibrations/odra_20260803.json",
           "--arms", "cdr", "--twirl-arms", "cdr", "--points", "optimal:star",
           "--eval-points", "2", "--shots", "256", "--n-train", "3", "--n-twirl", "2",
           "--window-id", "acc", "--campaign", "p0acceptance",
           "--out", str(out_csv)]
    env = {**__import__("os").environ, "KMP_DUPLICATE_LIB_OK": "TRUE",
           "OMP_NUM_THREADS": "1"}
    proc = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, env=env,
                          timeout=900)
    assert proc.returncode == 0, proc.stderr[-2000:]

    run_dir = repo / "runs" / "p0acceptance" / "acc"
    try:
        res = rebuild(run_dir)
        assert res["records"], "the window recorded no circuits"
        checked = [r for r in res["records"] if r["expval_rebuilt"] is not None]
        assert checked, "no record carried observable coefficients"
        assert res["mismatches"] == [], (
            f"{len(res['mismatches'])} of {len(checked)} values did not reproduce "
            f"bit-for-bit: {res['mismatches'][:3]}")

        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["campaign"] == "p0acceptance"
        assert manifest["environment"]["packages"]["qiskit"]
        assert manifest["finished_utc"]
    finally:
        __import__("shutil").rmtree(run_dir.parent, ignore_errors=True)
