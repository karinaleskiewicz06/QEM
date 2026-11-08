"""Window w02vn: two-axis variable-noise CDR on ODRA, with the noise levels INTERLEAVED.

Why a new window: in the P5 night the noise levels of one evaluation point (base, + CZ.CZ
pairs, + matched idle) were measured in separate blocks hours apart. vnCDR regresses the
levels jointly, so drift between blocks breaks its assumption that every level sees the
same device. Here one block is one evaluation point, and every executor job contains all
three levels of that point mixed copy by copy.

Design (pre-registered in preregistration_w02_vncdr.md, analysis code = --analyse below):

* rung: the frozen star L3 classifier (12 CZ) -- the rung where simulation predicts a gain;
* 8 evaluation points: point set 0 of campaign/eval_points.json (2 per margin quartile);
* per point: the target and n_train = 20 near-Clifford training circuits (near_target
  sampler, built on the native circuit, same CZ skeleton);
* three levels of every circuit: base, + k CZ.CZ pairs (cz_pairs), + matched idle
  (idle_matched); k = 12 by default (12 -> 36 CZ, as P5 star_cz36 / star_idle36);
* M = 6 copies of every circuit at every level, S = 32768 shots (4.1 M shots per point per
  method; chosen by the power analysis in nicdr/power_vn.py).

Equal budget at analysis: plain CDR uses the 6 base copies; 2-axis vnCDR uses 2 copies of
each of the 3 levels; 1-axis vnCDR uses 3 copies of each of 2 levels. Same shots.

    python campaign/vncdr_window.py --dry-run                     # plan and budget
    python campaign/vncdr_window.py --sim-device calibrations/odra_raw_w01A_start.json \
        --window-id simvn --campaign vncdr_sim                       # dress rehearsal in Aer
    python campaign/vncdr_window.py --submit --window-id w02vn --resume   # ODRA
    python campaign/vncdr_window.py --analyse runs/odra_campaign/w02vn    # pre-registered analysis
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import pathlib
import random
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
from qiskit.quantum_info import Statevector  # noqa: E402

from campaign.eval_points import load as load_eval_points  # noqa: E402
from campaign.odra_window import (SEC_PER_CIRCUIT, SEC_PER_SHOT, Executor, Job,  # noqa: E402
                                  _seed, frozen, run_window)
from noisy_sim import readout_observable  # noqa: E402
from qem.cdr_training import build_training_set, clifford_ideal_expval  # noqa: E402
from qem.compile import compile_native, cz_skeleton  # noqa: E402
from qem.env_check import add_env_argument, require_locked_environment  # noqa: E402
from qem.identity_insertion import insert_identity, scheduled_duration  # noqa: E402
from qem.provenance import RunRecorder  # noqa: E402

LEVELS = ("base", "cz", "idle")
MODES = {"cz": "cz_pairs", "idle": "idle_matched"}
FLOOR = 1e-3
N_DRAWS = 200
DRAW_SEED = 20261104


# --------------------------------------------------------------------------- #
# Plan                                                                           #
# --------------------------------------------------------------------------- #

def select_points(point_sets):
    pts = load_eval_points(REPO / "campaign" / "eval_points.json")
    return [p for k, p in enumerate(pts) if k % 3 in point_sets]


def build_plan(args, points):
    obs = readout_observable(5, "mean")
    jobs: list[Job] = []
    info = {"rungs": {}, "blocks": []}
    for rung in args.rungs:
        cw, xp = frozen(rung)
        for p in points:
            ei = p["eval_index"]
            block = f"{rung}/p{ei:02d}"
            info["blocks"].append(block)
            lg = cw.assign_parameters(dict(zip(xp, p["x"])))
            ideal_t = float(np.real(Statevector.from_instruction(lg).expectation_value(obs)))
            nat = compile_native(lg).circuit
            train = build_training_set(nat, n_train=args.n_train, sampler="near_target",
                                       base_seed=args.seed, target_index=ei,
                                       window_id=args.window_id)
            members = [("target", None, nat, ideal_t)] + [
                ("train", i, c, float(clifford_ideal_expval(c, obs))) for i, c in enumerate(train)]
            level_circ = {}
            for role, ti, base, ideal in members:
                for lv in LEVELS:
                    c = base.copy() if lv == "base" else insert_identity(
                        base, args.pairs, MODES[lv], t_cz=args.t_cz)
                    m = c.copy()
                    m.measure_all()
                    level_circ[(role, ti, lv)] = (m, ideal, c)
            if rung not in info["rungs"]:
                info["rungs"][rung] = {lv: {"n_cz": level_circ[("target", None, lv)][2]
                                            .count_ops().get("cz", 0),
                                            "t_us": scheduled_duration(
                                                level_circ[("target", None, lv)][2],
                                                t_prx=args.t_prx, t_cz=args.t_cz) * 1e6}
                                       for lv in LEVELS}
            # interleave: copy-major, then member, then level -> every job mixes all levels
            for r in range(args.copies):
                for role, ti, _, _ in members:
                    for lv in LEVELS:
                        m, ideal, c = level_circ[(role, ti, lv)]
                        tag = "target" if role == "target" else f"train{ti:03d}"
                        cid = f"{block}/{lv}/{tag}/r{r:02d}"
                        jobs.append(Job(cid, block, m, args.shots, {
                            "rung": rung, "kind": "vncdr", "level": lv, "role": role,
                            "train_index": ti, "repeat_index": r, "eval_index": ei,
                            "ideal": ideal, "n_cz": int(c.count_ops().get("cz", 0)),
                            "insert_pairs": 0 if lv == "base" else args.pairs,
                            "insert_mode": None if lv == "base" else MODES[lv],
                            "duration_sched_s": scheduled_duration(c, t_prx=args.t_prx,
                                                                   t_cz=args.t_cz),
                            "skeleton_matches_base": None}))
    return jobs, info


def block_order(blocks, seed, window_id):
    order = list(blocks)
    random.Random(_seed(seed, window_id, "vn-block-order")).shuffle(order)
    return order


# --------------------------------------------------------------------------- #
# Pre-registered analysis                                                       #
# --------------------------------------------------------------------------- #

def _vals(counts):
    v, w = [], []
    for k, c in counts.items():
        s = k.replace(" ", "")[-5:].zfill(5)
        v.append(np.mean([1 - 2 * int(s[4 - q]) for q in range(5)]))
        w.append(c)
    return np.array(v), np.array(w, float)


def load_run(run_dir):
    data = {}
    for line in (pathlib.Path(run_dir) / "counts.jsonl").open():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("kind") != "vncdr":
            continue
        key = (r["rung"], int(r["eval_index"]), r["role"], r.get("train_index"), r["level"])
        data.setdefault(key, {"ideal": float(r["ideal"]), "reps": {}})
        data[key]["reps"][int(r["repeat_index"])] = _vals(r["counts"])
    return data


def _mean(entry, reps):
    num = sum(float(np.dot(*entry["reps"][i])) for i in reps)
    den = sum(float(entry["reps"][i][1].sum()) for i in reps)
    return num / den


def _estimate(data, rung, ei, n_train, levels, reps_per_level, intercept=True):
    X_tr, X_te = [], []
    for lv, reps in zip(levels, reps_per_level):
        X_tr.append([_mean(data[(rung, ei, "train", i, lv)], reps) for i in range(n_train)])
        X_te.append(_mean(data[(rung, ei, "target", None, lv)], reps))
    y = np.array([data[(rung, ei, "train", i, levels[0])]["ideal"] for i in range(n_train)])
    X = np.array(X_tr).T
    xt = np.array(X_te)
    if intercept:
        X = np.column_stack([X, np.ones(len(X))])
        xt = np.append(xt, 1.0)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(xt @ coef)


def _paired(a, b):
    from scipy.stats import wilcoxon
    a = np.maximum(np.asarray(a), FLOOR)
    b = np.maximum(np.asarray(b), FLOOR)
    d = np.log(a) - np.log(b)
    rng = np.random.default_rng(0)
    boots = np.exp(rng.choice(d, (10000, d.size)).mean(axis=1))
    p = float(wilcoxon(d, alternative="less").pvalue) if np.any(d != 0) else 1.0
    return {"n": int(d.size), "wins": int((d < 0).sum()), "mean_A": float(np.mean(a)),
            "mean_B": float(np.mean(b)), "geo_ratio": float(np.exp(d.mean())),
            "ci_lo": float(np.quantile(boots, 0.025)), "ci_hi": float(np.quantile(boots, 0.975)),
            "p": p}


def analyse(run_dir, copies=6):
    data = load_run(run_dir)
    keys = sorted({(r, e) for (r, e, *_rest) in data})
    n_train = 1 + max(k[3] for k in data if k[2] == "train")
    complete = []
    for rung, ei in keys:
        ok = all(len(data.get((rung, ei, role, ti, lv), {"reps": {}})["reps"]) == copies
                 for lv in LEVELS
                 for role, ti in [("target", None)] + [("train", i) for i in range(n_train)])
        (complete if ok else []).append((rung, ei))
    missing = [k for k in keys if k not in complete]
    rng = np.random.default_rng(DRAW_SEED)
    methods = {"CDR": ("base",), "vn_t": ("base", "idle"), "vn_cz": ("base", "cz"),
               "vn_2ax": ("base", "cz", "idle")}
    rows = []
    for rung, ei in complete:
        ideal = data[(rung, ei, "target", None, "base")]["ideal"]
        raw = _mean(data[(rung, ei, "target", None, "base")], range(copies))
        row = {"rung": rung, "eval_index": ei, "ideal": ideal, "err_raw": abs(raw - ideal)}
        for name, levels in methods.items():
            L = len(levels)
            per = copies // L
            if L == 1:
                row[f"err_{name}"] = abs(_estimate(data, rung, ei, n_train, levels,
                                                   [list(range(copies))]) - ideal)
                continue
            errs = [abs(_estimate(data, rung, ei, n_train, levels,
                                  [sorted(rng.choice(copies, per, replace=False).tolist())
                                   for _ in levels]) - ideal) for _ in range(N_DRAWS)]
            row[f"err_{name}"] = float(np.mean(errs))
            row[f"err_{name}_first"] = abs(_estimate(data, rung, ei, n_train, levels,
                                                     [list(range(per))] * L) - ideal)
            row[f"err_{name}_noint"] = abs(_estimate(data, rung, ei, n_train, levels,
                                                     [list(range(per))] * L, intercept=False) - ideal)
            row[f"err_{name}_fullbudget"] = abs(_estimate(data, rung, ei, n_train, levels,
                                                          [list(range(copies))] * L) - ideal)
        rows.append(row)
    out = pathlib.Path(run_dir)
    with (out / "vncdr.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = [f"complete points: {len(complete)}; incomplete (excluded, reported): {missing}"]
    prim = _paired([r["err_vn_2ax"] for r in rows], [r["err_CDR"] for r in rows])
    verdict = "SUCCESS" if (prim["p"] < 0.05 and prim["geo_ratio"] < 1) else "NOT SUPPORTED"
    lines.append("PRIMARY (H_vn): 2-axis vnCDR (2 copies/level, mean over draws) vs CDR "
                 "(6 base copies), one-sided Wilcoxon on log error:")
    lines.append(f"  n={prim['n']} wins={prim['wins']}/{prim['n']} mean {prim['mean_A']:.4f} vs "
                 f"{prim['mean_B']:.4f} geo {prim['geo_ratio']:.3f} "
                 f"[{prim['ci_lo']:.3f}, {prim['ci_hi']:.3f}] p={prim['p']:.4f} -> {verdict}")
    lines.append("secondary (no claims):")
    for col in [c for c in rows[0] if c.startswith("err_vn")] + ["err_raw"]:
        if col == "err_vn_2ax":
            continue
        s = _paired([r[col] for r in rows], [r["err_CDR"] for r in rows])
        lines.append(f"  {col[4:]:<22s} vs CDR: wins {s['wins']}/{s['n']} geo {s['geo_ratio']:.3f} "
                     f"[{s['ci_lo']:.3f}, {s['ci_hi']:.3f}] p={s['p']:.4f}")
    (out / "vncdr_summary.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"wrote {out / 'vncdr.csv'} and {out / 'vncdr_summary.txt'}")


# --------------------------------------------------------------------------- #
# CLI                                                                            #
# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="plan and budget only (default)")
    mode.add_argument("--submit", action="store_true", help="run on ODRA")
    mode.add_argument("--sim-device", metavar="CALIBRATION_JSON")
    mode.add_argument("--analyse", metavar="RUN_DIR")
    ap.add_argument("--window-id", default="w02vn")
    ap.add_argument("--campaign", default="odra_campaign")
    ap.add_argument("--root", default="runs")
    ap.add_argument("--rungs", nargs="+", default=["star"])
    ap.add_argument("--point-sets", type=int, nargs="+", default=[0])
    ap.add_argument("--max-points", type=int, default=None, help="first K points (tests)")
    ap.add_argument("--pairs", type=int, default=12)
    ap.add_argument("--n-train", type=int, default=20)
    ap.add_argument("--copies", type=int, default=6)
    ap.add_argument("--shots", type=int, default=32768)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--t-cz", type=float, default=60e-9)
    ap.add_argument("--t-prx", type=float, default=20e-9)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--chunk", type=int, default=25,
                    help="circuits per executor call; each call is saved at once (resume unit)")
    ap.add_argument("--no-qasm", action="store_true")
    ap.add_argument("--sim-theta", type=float, default=0.0)
    ap.add_argument("--sim-phi", type=float, default=0.0)
    ap.add_argument("--sim-eps", type=float, default=0.0)
    add_env_argument(ap)
    args = ap.parse_args(argv)

    if args.analyse:
        analyse(args.analyse, copies=args.copies)
        return
    require_locked_environment(allow_mismatch=args.allow_env_mismatch)

    points = select_points(args.point_sets)
    if args.max_points:
        points = points[: args.max_points]
    per_point = (args.n_train + 1) * len(LEVELS) * args.copies
    n = per_point * len(points) * len(args.rungs)
    hours = n * (SEC_PER_CIRCUIT + SEC_PER_SHOT * args.shots) / 3600
    print(f"window {args.window_id}: rungs {args.rungs}, {len(points)} points "
          f"{[p['eval_index'] for p in points]}, levels {LEVELS} (+{args.pairs} pairs), "
          f"n_train {args.n_train}, copies {args.copies}, S {args.shots}")
    print(f"  {n} circuits, {n * args.shots:,} shots, ~{hours:.1f} h at the pilot rate "
          f"(night A ran ~1.7x slower because of the queue)")
    if not (args.submit or args.sim_device):
        print("[DRY-RUN] nothing executed.")
        return
    if args.sim_device:
        from sim.device_model import load_calibration
        c = load_calibration(args.sim_device)
        args.t_prx, args.t_cz = c.t_prx, c.t_cz
    jobs, info = build_plan(args, points)
    order = block_order(info["blocks"], args.seed, args.window_id)
    print("levels:", info["rungs"])
    ex = Executor(args)
    rec = RunRecorder.open(args.campaign, window_id=args.window_id, args=vars(args),
                           seed=args.seed, device="odra", submitted=bool(args.submit),
                           root=args.root)
    rec.set_extra("plan", {"design": "vncdr-interleaved", "block_order": order,
                           "levels": info["rungs"], "n_circuits": len(jobs),
                           "eval_points": [p["eval_index"] for p in points]})
    if ex.dev is not None:
        from sim.device_model import manifest_entry
        rec.set_extra("device_model", manifest_entry(ex.dev))
    print(f"[provenance] {rec.dir}")
    run_window(args, jobs, order, rec, ex)
    rec.close()
    if rec.manifest.is_split:
        print("WARNING: calibration set changed during the window -> marked split")
    analyse(rec.dir, copies=args.copies)


if __name__ == "__main__":
    main()
