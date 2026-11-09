"""Window w03dd: CDR with and without dynamical decoupling (DD) on ODRA, interleaved.

Why: the P5 night showed that raw error grows with circuit DURATION, i.e. with idle time,
which is what DD is meant to suppress. Month 1 (banknote study) saw IQM's default DD make
raw error 30-40 % worse, with run order as a possible confound. This window tests DD inside
CDR at an equal budget, with DD on / off alternated job by job so drift hits both arms alike.

Design (pre-registered in preregistration_w03_dd.md; the analysis is --analyse below):

* rungs: frozen star L3 (12 CZ) and circular L3 (39 CZ), the two rungs of night A;
* 8 evaluation points: point set 0 of campaign/eval_points.json;
* per point: the target and n_train = 20 near-Clifford training circuits (near_target, built
  on the native circuit);
* two arms on the SAME circuits: DD off and DD on (IQM server-side DD, the standard
  strategy; a compile option of the job, so circuits are identical);
* M = 6 copies, S = 8192 shots: 1,032,192 shots per point per arm, as in night A;
* one block = one (rung, point); inside it every job holds one copy of all 21 circuits
  for ONE arm, and the arms alternate (off, on / on, off ...) copy by copy.

    python campaign/dd_window.py --dry-run
    python campaign/dd_window.py --sim-device calibrations/odra_raw_w01A_start.json \
        --window-id simdd --campaign dd_sim         # pipeline rehearsal (the sim has no DD)
    python campaign/dd_window.py --submit --window-id w03dd --resume
    python campaign/dd_window.py --analyse runs/odra_campaign/w03dd
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import random
import sys
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
from qiskit.quantum_info import Statevector  # noqa: E402

from campaign.eval_points import load as load_eval_points  # noqa: E402
from campaign.odra_window import (COEFFS, N_QUBITS, SEC_PER_CIRCUIT, SEC_PER_SHOT,  # noqa: E402
                                  Executor, Job, _seed, frozen, recorded_ids)
from noisy_sim import perqubit_z_from_counts, readout_observable  # noqa: E402
from qem.cdr_training import build_training_set, clifford_ideal_expval  # noqa: E402
from qem.compile import compile_native  # noqa: E402
from qem.env_check import add_env_argument, require_locked_environment  # noqa: E402
from qem.provenance import RunRecorder  # noqa: E402

ARMS = ("off", "dd")
FLOOR = 1e-3


# --------------------------------------------------------------------------- #
# Plan                                                                           #
# --------------------------------------------------------------------------- #

def select_points(point_sets):
    pts = load_eval_points(REPO / "campaign" / "eval_points.json")
    return [p for k, p in enumerate(pts) if k % 3 in point_sets]


def build_plan(args, points):
    obs = readout_observable(N_QUBITS, "mean")
    jobs: list[Job] = []
    blocks = []
    for rung in args.rungs:
        cw, xp = frozen(rung)
        for p in points:
            ei = p["eval_index"]
            block = f"{rung}/p{ei:02d}"
            blocks.append(block)
            lg = cw.assign_parameters(dict(zip(xp, p["x"])))
            ideal_t = float(np.real(Statevector.from_instruction(lg).expectation_value(obs)))
            nat = compile_native(lg).circuit
            train = build_training_set(nat, n_train=args.n_train, sampler="near_target",
                                       base_seed=args.seed, target_index=ei,
                                       window_id=args.window_id)
            members = [("target", None, nat, ideal_t)] + [
                ("train", i, c, float(clifford_ideal_expval(c, obs))) for i, c in enumerate(train)]
            measured = []
            for role, ti, c, ideal in members:
                m = c.copy()
                m.measure_all()
                measured.append((role, ti, m, ideal, int(c.count_ops().get("cz", 0))))
            for r in range(args.copies):
                arms = ARMS if r % 2 == 0 else ARMS[::-1]
                for arm in arms:
                    for role, ti, m, ideal, ncz in measured:
                        tag = "target" if role == "target" else f"train{ti:03d}"
                        jobs.append(Job(f"{block}/{arm}/{tag}/r{r:02d}", block, m, args.shots, {
                            "rung": rung, "kind": "dd_cdr", "arm": arm, "dd": arm == "dd",
                            "role": role, "train_index": ti, "repeat_index": r,
                            "eval_index": ei, "ideal": ideal, "n_cz": ncz}))
    return jobs, blocks


# --------------------------------------------------------------------------- #
# Execution: one executor call per (copy, arm) group, DD set per call            #
# --------------------------------------------------------------------------- #

class DDExecutor(Executor):
    def run(self, circs, shots, on_job=None, dd=False):
        if self.dev is not None:                        # the device model has no DD
            return super().run(circs, shots, on_job=on_job)
        from odra_backend import run_circuits
        return run_circuits(self.backend, circs, shots, dd=dd, on_job=on_job)


def _groups(pending):
    out, cur = [], []
    for j in pending:
        if cur and (j.meta["arm"], j.meta["repeat_index"]) != (cur[0].meta["arm"],
                                                              cur[0].meta["repeat_index"]):
            out.append(cur)
            cur = []
        cur.append(j)
    if cur:
        out.append(cur)
    return out


def run(args, jobs, order, rec, ex):
    done = recorded_ids(rec.counts_path) if args.resume else set()
    if done:
        print(f"[resume] {len(done)} circuits already recorded")
    blocks_log = rec.manifest.extra.setdefault("blocks", [])
    for k, blk in enumerate(order):
        pending = [j for j in jobs if j.block == blk and j.cid not in done]
        if not pending:
            print(f"  [{k + 1}/{len(order)}] {blk}: complete, skipped")
            continue
        cal0 = ex.calibration_set_id()
        if rec.manifest.calibration_set_id["start"] is None:
            rec.set_calibration_set_id("start", cal0)
        t0 = time.time()
        print(f"  [{k + 1}/{len(order)}] {blk}: {len(pending)} circuits", flush=True)
        for g in _groups(pending):
            dd = bool(g[0].meta["dd"])
            counts = ex.run([j.circuit for j in g], args.shots, on_job=rec.add_job, dd=dd)
            for j, cnt in zip(g, counts):
                val = float(np.dot(COEFFS, perqubit_z_from_counts(cnt, N_QUBITS)))
                rec.record_circuit(j.cid, cnt, native=j.circuit, t_1q=ex.t_1q, t_2q=ex.t_2q,
                                   with_qasm=not args.no_qasm, block=j.block, expval=val,
                                   coeffs=list(map(float, COEFFS)), reduction="dot_perqubit",
                                   calibration_set_id=cal0, **j.meta)
        cal1 = ex.calibration_set_id()
        blocks_log.append({"block": blk, "order": k, "n": len(pending), "cal_before": cal0,
                           "cal_after": cal1, "seconds": round(time.time() - t0, 1)})
        rec.set_calibration_set_id("end", cal1)
        if cal0 != cal1:
            rec.note(f"calibration set changed during block {blk}: {cal0} -> {cal1}")
        rec.manifest.save(rec.manifest_path)


# --------------------------------------------------------------------------- #
# Pre-registered analysis                                                       #
# --------------------------------------------------------------------------- #

def _ols(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    a, b = np.polyfit(x, y, 1)
    pred = a * x + b
    r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)
    return float(a), float(b), float(r2)


def _paired(a, b, alternative="two-sided"):
    from scipy.stats import wilcoxon
    a = np.maximum(np.asarray(a, float), FLOOR)
    b = np.maximum(np.asarray(b, float), FLOOR)
    d = np.log(a) - np.log(b)
    rng = np.random.default_rng(0)
    boots = np.exp(rng.choice(d, (10000, d.size)).mean(axis=1))
    p = float(wilcoxon(d, alternative=alternative).pvalue) if np.any(d != 0) else 1.0
    return {"n": int(d.size), "wins": int((d < 0).sum()), "mean_A": float(a.mean()),
            "mean_B": float(b.mean()), "geo": float(np.exp(d.mean())),
            "lo": float(np.quantile(boots, 0.025)), "hi": float(np.quantile(boots, 0.975)), "p": p}


def analyse(run_dir, copies=6):
    run_dir = pathlib.Path(run_dir)
    vals: dict = {}
    for line in (run_dir / "counts.jsonl").open():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("kind") != "dd_cdr":
            continue
        key = (r["rung"], int(r["eval_index"]), r["arm"], r["role"], r.get("train_index"))
        e = vals.setdefault(key, {"ideal": float(r["ideal"]), "num": 0.0, "den": 0, "reps": set()})
        n = sum(r["counts"].values())
        e["num"] += float(r["expval"]) * n
        e["den"] += n
        e["reps"].add(int(r["repeat_index"]))
    pts = sorted({(k[0], k[1]) for k in vals})
    n_train = 1 + max(k[4] for k in vals if k[3] == "train")
    rows, missing = [], []
    for rung, ei in pts:
        need = [(rung, ei, arm, "target", None) for arm in ARMS] + [
            (rung, ei, arm, "train", i) for arm in ARMS for i in range(n_train)]
        if not all(k in vals and len(vals[k]["reps"]) == copies for k in need):
            missing.append((rung, ei))
            continue
        row = {"rung": rung, "eval_index": ei}
        for arm in ARMS:
            t = vals[(rung, ei, arm, "target", None)]
            x = [vals[(rung, ei, arm, "train", i)]["num"] / vals[(rung, ei, arm, "train", i)]["den"]
                 for i in range(n_train)]
            y = [vals[(rung, ei, arm, "train", i)]["ideal"] for i in range(n_train)]
            a, b, r2 = _ols(x, y)
            raw = t["num"] / t["den"]
            row.update({"ideal": t["ideal"], f"raw_{arm}": raw, f"err_raw_{arm}": abs(raw - t["ideal"]),
                        f"err_cdr_{arm}": abs(a * raw + b - t["ideal"]), f"a_{arm}": a,
                        f"r2_{arm}": r2})
        rows.append(row)
    with (run_dir / "dd_cdr.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = [f"complete points: {len(rows)}; incomplete (excluded, reported): {missing}"]
    prim = _paired([r["err_cdr_dd"] for r in rows], [r["err_cdr_off"] for r in rows])
    if prim["p"] < 0.05:
        verdict = "DD HELPS CDR" if prim["geo"] < 1 else "DD HURTS CDR"
    else:
        verdict = "NO DIFFERENCE DETECTED"
    lines.append("PRIMARY (H_dd): CDR with DD vs CDR without DD, both rungs pooled, two-sided "
                 "Wilcoxon on log error:")
    lines.append(f"  n={prim['n']} DD better in {prim['wins']}/{prim['n']}  mean {prim['mean_A']:.4f}"
                 f" (DD) vs {prim['mean_B']:.4f} (off)  geo {prim['geo']:.3f} [{prim['lo']:.3f}, "
                 f"{prim['hi']:.3f}] p={prim['p']:.4f} -> {verdict}")
    lines.append("secondary (no claims):")
    for rung in sorted({r["rung"] for r in rows}):
        sub = [r for r in rows if r["rung"] == rung]
        s = _paired([r["err_cdr_dd"] for r in sub], [r["err_cdr_off"] for r in sub])
        q = _paired([r["err_raw_dd"] for r in sub], [r["err_raw_off"] for r in sub])
        lines.append(f"  {rung}: CDR dd vs off: {s['wins']}/{s['n']} geo {s['geo']:.3f} p={s['p']:.4f}"
                     f" | raw dd vs off: {q['wins']}/{q['n']} geo {q['geo']:.3f} p={q['p']:.4f}"
                     f" | slope a off {np.mean([r['a_off'] for r in sub]):.2f} dd "
                     f"{np.mean([r['a_dd'] for r in sub]):.2f} | r2 off "
                     f"{np.mean([r['r2_off'] for r in sub]):.3f} dd {np.mean([r['r2_dd'] for r in sub]):.3f}")
        lines.append(f"    mean err: raw off {np.mean([r['err_raw_off'] for r in sub]):.4f} dd "
                     f"{np.mean([r['err_raw_dd'] for r in sub]):.4f} | CDR off "
                     f"{np.mean([r['err_cdr_off'] for r in sub]):.4f} dd "
                     f"{np.mean([r['err_cdr_dd'] for r in sub]):.4f}")
    (run_dir / "dd_cdr_summary.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"wrote {run_dir / 'dd_cdr.csv'} and {run_dir / 'dd_cdr_summary.txt'}")


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
    ap.add_argument("--window-id", default="w03dd")
    ap.add_argument("--campaign", default="odra_campaign")
    ap.add_argument("--root", default="runs")
    ap.add_argument("--rungs", nargs="+", default=["star", "circular"])
    ap.add_argument("--point-sets", type=int, nargs="+", default=[0])
    ap.add_argument("--max-points", type=int, default=None, help="first K points (tests)")
    ap.add_argument("--n-train", type=int, default=20)
    ap.add_argument("--copies", type=int, default=6)
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--resume", action="store_true")
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
    n = (args.n_train + 1) * args.copies * len(ARMS) * len(points) * len(args.rungs)
    hours = n * (SEC_PER_CIRCUIT + SEC_PER_SHOT * args.shots) / 3600
    print(f"window {args.window_id}: rungs {args.rungs}, {len(points)} points "
          f"{[p['eval_index'] for p in points]}, arms {ARMS}, n_train {args.n_train}, "
          f"copies {args.copies}, S {args.shots}")
    print(f"  {n} circuits, {n * args.shots:,} shots, ~{hours:.1f} h at the pilot rate")
    if not (args.submit or args.sim_device):
        print("[DRY-RUN] nothing executed.")
        return
    jobs, blocks = build_plan(args, points)
    order = list(blocks)
    random.Random(_seed(args.seed, args.window_id, "dd-block-order")).shuffle(order)
    ex = DDExecutor(args)
    rec = RunRecorder.open(args.campaign, window_id=args.window_id, args=vars(args),
                           seed=args.seed, device="odra", submitted=bool(args.submit),
                           root=args.root)
    rec.set_extra("plan", {"design": "dd-cdr-interleaved", "block_order": order,
                           "n_circuits": len(jobs), "dd_strategy": "IQM STANDARD_DD_STRATEGY",
                           "eval_points": [p["eval_index"] for p in points]})
    if ex.dev is not None:
        from sim.device_model import manifest_entry
        rec.set_extra("device_model", manifest_entry(ex.dev))
        rec.note("simulation: the device model has no DD, both arms are the same channel")
    print(f"[provenance] {rec.dir}")
    run(args, jobs, order, rec, ex)
    rec.close()
    if rec.manifest.is_split:
        print("WARNING: calibration set changed during the window -> marked split")
    analyse(rec.dir, copies=args.copies)


if __name__ == "__main__":
    main()
