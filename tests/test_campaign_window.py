"""P8: the ODRA window -- plan, budget, block order, resume, analysis."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

import pytest

from campaign import eval_points
from campaign import odra_window as ow

REPO = pathlib.Path(__file__).resolve().parent.parent
CAL = REPO / "spec" / "odra_cal_example.json"


def _args(**kw):
    base = dict(points=["star", "all_to_all"], cdr_arms=list(ow.DEFAULT_ARMS), n_train=3,
                frames=2, shots=256, no_zne=False, seed=42, window_id="t1")
    base.update(kw)
    return argparse.Namespace(**base)


def test_eval_points_file_is_reproducible_and_stratified():
    committed = json.loads((REPO / "campaign" / "eval_points.json").read_text())
    rebuilt = eval_points.build()
    assert [p["reference_index"] for p in committed["points"]] == \
           [p["reference_index"] for p in rebuilt["points"]]
    strata = [p["stratum"] for p in committed["points"]]
    assert len(strata) == 24 and all(strata.count(s) == 6 for s in range(4))
    assert len({p["reference_index"] for p in committed["points"]}) == 24


def test_analytic_budget_matches_the_built_plan():
    args = _args()
    pts = eval_points.load(REPO / "campaign" / "eval_points.json")[:2]
    jobs, _ = ow.build_plan(args, pts)
    built = {}
    for j in jobs:
        built[j.block] = built.get(j.block, 0) + 1
    assert built == {b: n for b, (n, _) in ow.plan_counts(args, 2).items()}


def test_every_cdr_arm_spends_the_same_budget_per_point():
    args = _args()
    pts = eval_points.load(REPO / "campaign" / "eval_points.json")[:2]
    jobs, _ = ow.build_plan(args, pts)
    spent = {}
    for j in jobs:
        if j.meta["kind"] == "cdr":
            key = (j.block, j.meta["eval_index"])
            spent[key] = spent.get(key, 0) + j.shots
    assert len(set(spent.values())) == 1
    assert next(iter(spent.values())) == (args.n_train + 1) * args.frames * args.shots


def test_ids_unique_and_training_skeletons_match():
    jobs, _ = ow.build_plan(_args(), eval_points.load(REPO / "campaign" / "eval_points.json")[:2])
    assert len({j.cid for j in jobs}) == len(jobs)
    near = [j for j in jobs if j.meta.get("train_set") == "near_target"]
    assert near and all(j.meta["skeleton_matches_target"] for j in near)


def test_plan_is_deterministic_per_window():
    pts = eval_points.load(REPO / "campaign" / "eval_points.json")[:1]
    a, _ = ow.build_plan(_args(points=["star"]), pts)
    b, _ = ow.build_plan(_args(points=["star"]), pts)
    c, _ = ow.build_plan(_args(points=["star"], window_id="t2"), pts)
    assert [j.circuit for j in a] == [j.circuit for j in b]
    assert [j.circuit for j in a] != [j.circuit for j in c]   # frames/training differ


def test_block_order_is_seeded_and_differs_between_windows():
    blocks = list(ow.plan_counts(_args(), 2))
    o1 = ow.block_order(blocks, 42, "w01")
    assert o1 == ow.block_order(blocks, 42, "w01")
    assert sorted(o1) == sorted(blocks)
    assert o1 != ow.block_order(blocks, 42, "w02")


def test_logical_twirl_requires_logical_training():
    with pytest.raises(SystemExit):
        ow.parse_arms(["twirl_logical:near_target"])
    assert ow.parse_arms(["spread"]) == [("spread", "near_target")]


def test_points_accept_placement_prefixes():
    assert ow.parse_points(["optimal:star", "adverse:all_to_all", "star_L9"]) == \
           ["star", "all_to_all", "star_L9"]
    with pytest.raises(SystemExit):
        ow.parse_points(["optimal:ring"])


def test_dry_run_prints_budget_and_nights():
    out = subprocess.run([sys.executable, "campaign/odra_window.py", "--dry-run",
                          "--window-id", "test"], cwd=REPO, capture_output=True, text=True,
                         timeout=120)
    assert out.returncode == 0, out.stderr
    assert "TOTAL" in out.stdout and "night 1" in out.stdout


def test_dd_ablation_is_deferred_to_p6():
    out = subprocess.run([sys.executable, "campaign/odra_window.py", "--dd-ablation"],
                         cwd=REPO, capture_output=True, text=True, timeout=120)
    assert out.returncode != 0 and "P6" in (out.stdout + out.stderr)


@pytest.mark.slow
def test_window_end_to_end_with_resume(tmp_path):
    """Simulated window, then a resume after losing records: measures only what is missing."""
    from analysis.rebuild_from_counts import rebuild
    cmd = [sys.executable, "campaign/odra_window.py", "--sim-device", str(CAL),
           "--window-id", "e2e", "--root", str(tmp_path), "--points", "optimal:star",
           "adverse:all_to_all", "--eval-points", "2", "--n-train", "3", "--frames", "2",
           "--shots", "256"]
    res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=1800)
    assert res.returncode == 0, res.stderr[-2000:]
    w = tmp_path / "odra_campaign" / "e2e"
    m = json.loads((w / "manifest.json").read_text())
    assert m["calibration_set_id"]["start"] and not m["split_window"]
    assert len(m["extra"]["blocks"]) == len(m["extra"]["plan"]["block_order"])
    assert rebuild(w)["mismatches"] == []
    first = (w / "cdr.csv").read_text()

    lines = (w / "counts.jsonl").read_text().splitlines()
    (w / "counts.jsonl").write_text("\n".join(lines[:-15]) + "\n")
    res = subprocess.run(cmd + ["--resume"], cwd=REPO, capture_output=True, text=True,
                         timeout=1800)
    assert res.returncode == 0, res.stderr[-2000:]
    after = (w / "counts.jsonl").read_text().splitlines()
    ids = [json.loads(l)["circuit_id"] for l in after]
    assert len(after) == len(lines) and len(set(ids)) == len(ids)
    assert "[resume]" in res.stdout
    # the analysis is a pure function of the records
    assert (w / "cdr.csv").read_text().splitlines()[0] == first.splitlines()[0]
