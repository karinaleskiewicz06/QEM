"""P0: the per-window manifest and the per-circuit raw record."""

from __future__ import annotations

import json
import pathlib

import pytest
from qiskit import QuantumCircuit, transpile

from qem.provenance import (RunManifest, RunRecorder, circuit_stats,
                            estimate_duration_s, save_counts)
from topology import star_coupling_map
from zne_dryrun import IQM_BASIS_GATES


def _native(n_cz_per_leaf: int = 1) -> QuantumCircuit:
    qc = QuantumCircuit(5, 5)
    for _ in range(n_cz_per_leaf):
        for q in range(1, 5):
            qc.h(q)
            qc.cz(0, q)
    qc.measure(range(5), range(5))
    return transpile(qc, basis_gates=IQM_BASIS_GATES, coupling_map=star_coupling_map(5),
                     initial_layout=[0, 1, 2, 3, 4], optimization_level=1,
                     seed_transpiler=42)


def test_save_counts_appends_one_json_object_per_line(tmp_path: pathlib.Path):
    p = tmp_path / "counts.jsonl"
    save_counts(p, "a", {"00000": 10}, {"arm": "raw"})
    save_counts(p, "b", {"00001": 20}, {"arm": "cdr"})
    lines = p.read_text().strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["circuit_id"] == "a" and first["shots"] == 10 and first["arm"] == "raw"


def test_record_carries_gate_counts_skeleton_and_duration(tmp_path: pathlib.Path):
    native = _native()
    rec = RunRecorder.open("t", window_id="w", root=tmp_path)
    rec.record_circuit("p0/target/off", {"00000": 8}, native=native,
                       t_1q=20e-9, t_2q=60e-9, arm="cdr")
    rec.close()
    r = json.loads(rec.counts_path.read_text().strip())
    stats = circuit_stats(native)
    assert r["n_cz"] == stats["n_cz"] and r["n_prx"] == stats["n_prx"]
    assert r["cz_skeleton"] == stats["cz_skeleton"]
    assert r["duration_s"] == estimate_duration_s(stats["n_prx"], stats["n_cz"],
                                                  t_1q=20e-9, t_2q=60e-9)
    assert r["qasm3"], "the native circuit must be serialised with its counts"


def test_cz_skeleton_is_ordered_and_matches_the_circuit():
    """The skeleton is what makes a CDR training circuit comparable with its target."""
    native = _native()
    skeleton = circuit_stats(native)["cz_skeleton"]
    assert skeleton == [[0, 1], [0, 2], [0, 3], [0, 4]]


def test_manifest_records_environment_and_git_state(tmp_path: pathlib.Path):
    rec = RunRecorder.open("t", window_id="w", args={"shots": 512}, seed=7,
                           device="odra", root=tmp_path)
    rec.close()
    m = json.loads(rec.manifest_path.read_text())
    assert m["seed"] == 7 and m["device"] == "odra" and m["cli_args"]["shots"] == 512
    assert m["environment"]["packages"]["qiskit"]
    assert "git_commit" in m["environment"] and "git_dirty" in m["environment"]
    assert m["started_utc"] and m["finished_utc"]


def test_job_ids_are_recorded_once(tmp_path: pathlib.Path):
    rec = RunRecorder.open("t", window_id="w", root=tmp_path)
    rec.add_job("019fb481-3e61-7573-b807-2ceae730df02")
    rec.add_job("019fb481-3e61-7573-b807-2ceae730df02")
    rec.add_job("019fb483-a859-7361-84c9-3ab463ea2e10")
    rec.close()
    assert len(json.loads(rec.manifest_path.read_text())["job_ids"]) == 2


@pytest.mark.parametrize("start,end,expected", [
    ("cal-A", "cal-A", False),
    ("cal-A", "cal-B", True),
    (None, "cal-B", False),      # unknown start: cannot claim a split
])
def test_split_window_detection(tmp_path: pathlib.Path, start, end, expected):
    """A recalibration mid-window means the points are not one condition."""
    rec = RunRecorder.open("t", window_id="w", root=tmp_path)
    rec.set_calibration_set_id("start", start)
    rec.set_calibration_set_id("end", end)
    rec.close()
    assert json.loads(rec.manifest_path.read_text())["split_window"] is expected


def test_manifest_survives_a_crashed_window(tmp_path: pathlib.Path):
    """close() may never run; what was written before must still be readable."""
    rec = RunRecorder.open("t", window_id="w", root=tmp_path)
    rec.record_circuit("p0/a/off", {"00000": 4}, arm="raw")
    m = json.loads(rec.manifest_path.read_text())
    assert m["finished_utc"] is None
    assert len(rec.counts_path.read_text().strip().splitlines()) == 1
