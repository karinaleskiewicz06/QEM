"""Window w04m: raw decisions of every CZ rung on the full 100-point eval set (ODRA).

Question: noise shrinks <O> toward 0 and shifts it a little (readout asymmetry), so the
classifier's decision sign(<O>) should flip only where |O_ideal| is below that shift. On
the 8-point sets this was seen as "raw already agrees with the ideal decision in 92 %".
Here: all 100 eval points of the frozen reference set, every CZ option of the campaign,
raw only (cheap), plus readout-reference circuits (all |0>, all |1>) to measure the shift.

* rungs: star / linear / circular / all_to_all L3 (12 / 30 / 39 / 57 CZ), star L6 / L9 /
  L13 (24 / 36 / 52 CZ), and the P5 insertions on star L3: + CZ pairs (24 / 36 / 52 CZ)
  and + matched idle (12 CZ, same durations) -- 13 rungs;
* M = 2 copies, S = 8192 shots; one block per copy; inside a block points are shuffled and
  every job mixes all rungs, so drift hits all rungs alike;
* readout references: |00000> and |11111>, 4 copies each, spread over the blocks.

The file name contains ``odra_window.py`` on purpose: ``run_dd.sh`` waits while any
process matching it runs, so starting this script now (it waits for night B itself)
queues it between night B and the DD window.

    python campaign/margin_odra_window.py --dry-run
    python campaign/margin_odra_window.py --sim-device calibrations/odra_raw_w01A_start.json \
        --window-id simm --campaign margin_sim
    python campaign/margin_odra_window.py --submit --window-id w04m --wait-for run_night_b.sh
    python campaign/margin_odra_window.py --analyse runs/odra_campaign/w04m
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import random
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
from qiskit import QuantumCircuit  # noqa: E402
from qiskit.quantum_info import Statevector  # noqa: E402

from campaign.odra_window import (INSERTIONS, N_QUBITS, SEC_PER_CIRCUIT, SEC_PER_SHOT,  # noqa: E402
                                  Executor, Job, _seed, frozen, run_window)
from noisy_sim import readout_observable  # noqa: E402
from qem.compile import compile_native  # noqa: E402
from qem.env_check import add_env_argument, require_locked_environment  # noqa: E402
from qem.identity_insertion import insert_identity  # noqa: E402
from qem.provenance import RunRecorder  # noqa: E402

RUNGS = ["star", "linear", "circular", "all_to_all", "star_L6", "star_L9", "star_L13",
         "star_cz24", "star_cz36", "star_cz52", "star_idle24", "star_idle36", "star_idle52"]
REF = REPO / "trained_models_hard" / "two_curves_d8_q5_deg8_star_mean_L3_reference.npz"
RO_COPIES = 4


def reference_set():
    z = np.load(REF)
    return z["X_eval"], z["y_eval"].astype(int)


def build_plan(args):
    X, y = reference_set()
    if args.max_points:
        X, y = X[: args.max_points], y[: args.max_points]
    obs = readout_observable(N_QUBITS, "mean")
    per_rung = {}
    info = {}
    for rung in args.rungs:
        cw, xp = frozen(rung)
        circs = []
        for k, x in enumerate(X):
            lg = cw.assign_parameters(dict(zip(xp, x)))
            ideal = float(np.real(Statevector.from_instruction(lg).expectation_value(obs)))
            nat = compile_native(lg).circuit
            if rung in INSERTIONS:
                pairs, mode = INSERTIONS[rung]
                nat = insert_identity(nat, pairs, mode, t_cz=args.t_cz)
            m = nat.copy()
            m.measure_all()
            circs.append((k, m, ideal, int(nat.count_ops().get("cz", 0))))
        per_rung[rung] = circs
        info[rung] = circs[0][3]
    ro = []
    for state in (0, 1):
        qc = QuantumCircuit(N_QUBITS)
        if state:
            qc.x(range(N_QUBITS))
        m = compile_native(qc).circuit.copy()
        m.measure_all()
        ro.append((state, m))
    jobs: list[Job] = []
    blocks = []
    for r in range(args.copies):
        block = f"r{r:02d}"
        blocks.append(block)
        rng = random.Random(_seed(args.seed, args.window_id, "margin", r))
        order = list(range(len(X)))
        rng.shuffle(order)
        items = []
        for k in order:
            rungs = list(args.rungs)
            rng.shuffle(rungs)
            for rung in rungs:
                kk, m, ideal, ncz = per_rung[rung][k]
                items.append(Job(f"{block}/{rung}/x{kk:03d}", block, m, args.shots, {
                    "rung": rung, "kind": "margin", "point": kk, "label": int(y[kk]),
                    "ideal": ideal, "repeat_index": r, "n_cz": ncz}))
        # readout references spread through the block
        n_ro = RO_COPIES * 2 // args.copies or 2
        for i in range(n_ro):
            state, m = ro[i % 2]
            pos = (i + 1) * len(items) // (n_ro + 1)
            items.insert(pos, Job(f"{block}/readout/s{state}/c{i:02d}", block, m, args.shots, {
                "kind": "readout", "state": state, "repeat_index": r}))
        jobs += items
    return jobs, blocks, info


# --------------------------------------------------------------------------- #
# Analysis                                                                       #
# --------------------------------------------------------------------------- #

def analyse(run_dir):
    run_dir = pathlib.Path(run_dir)
    agg: dict = {}
    ro = {0: [], 1: []}
    for line in (run_dir / "counts.jsonl").open():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("kind") == "readout":
            ro[int(r["state"])].append(float(r["expval"]))
            continue
        if r.get("kind") != "margin":
            continue
        e = agg.setdefault((r["rung"], int(r["point"])), {"ideal": r["ideal"], "label": r["label"],
                                                          "n_cz": r["n_cz"], "v": []})
        e["v"].append(float(r["expval"]))
    rows = []
    for (rung, k), e in sorted(agg.items()):
        raw = float(np.mean(e["v"]))
        rows.append({"rung": rung, "n_cz": e["n_cz"], "point": k, "label": e["label"],
                     "ideal": e["ideal"], "raw": raw, "n_copies": len(e["v"]),
                     "dec_ideal": 1 if e["ideal"] >= 0 else -1, "dec_raw": 1 if raw >= 0 else -1})
    with (run_dir / "margin.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = []
    if ro[0] and ro[1]:
        m0, m1 = np.mean(ro[0]), np.mean(ro[1])
        lines.append(f"readout references: <Z>|00000> = {m0:.4f}, <Z>|11111> = {m1:.4f}; "
                     f"offset (m0 + m1)/2 = {(m0 + m1) / 2:+.4f}, contraction (m0 - m1)/2 = "
                     f"{(m0 - m1) / 2:.4f}")
    lines.append(f"{'rung':<12s} {'CZ':>3s} {'acc ideal':>9s} {'acc raw':>8s} {'agree':>6s} "
                 f"{'flips':>5s} {'slope':>6s} {'offset':>7s} {'max |ideal| flipped':>20s}")
    for rung in [r for r in RUNGS if any(x["rung"] == r for x in rows)]:
        s = [x for x in rows if x["rung"] == rung]
        ideal = np.array([x["ideal"] for x in s])
        raw = np.array([x["raw"] for x in s])
        lab = np.array([x["label"] for x in s])
        di, dr = np.where(ideal >= 0, 1, -1), np.where(raw >= 0, 1, -1)
        slope, off = np.polyfit(ideal, raw, 1)
        flipped = np.abs(ideal[di != dr])
        lines.append(f"{rung:<12s} {s[0]['n_cz']:>3d} {np.mean(di == lab):9.3f} {np.mean(dr == lab):8.3f} "
                     f"{np.mean(di == dr):6.3f} {int(np.sum(di != dr)):5d} {slope:6.3f} {off:+7.4f} "
                     f"{(flipped.max() if flipped.size else 0):20.4f}")
    (run_dir / "margin_summary.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"wrote {run_dir / 'margin.csv'}")


# --------------------------------------------------------------------------- #
# Hardware helpers: wait for the previous window, calibration, ODRA outages      #
# --------------------------------------------------------------------------- #

def _log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def _others_running(pattern):
    """True if a process other than this one (or its caffeinate parent) matches."""
    out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout.split()
    return any(int(p) not in (os.getpid(), os.getppid()) for p in out)


def _wait_for(pattern):
    said = False
    while _others_running(pattern):
        if not said:
            _log(f"waiting for '{pattern}' to finish")
            said = True
        time.sleep(30)


def _calibration(window_id, tag):
    raw = REPO / "calibrations" / f"odra_raw_{window_id}_{tag}.json"
    if raw.exists() and '"observations"' in raw.read_text():
        _log(f"calibration {tag} already taken")
        return True
    r = subprocess.run([sys.executable, str(REPO / "collect_odra_calibration.py"), "--out",
                        str(REPO / "calibrations" / f"odra_{window_id}_{tag}.json"),
                        "--raw-out", str(raw)], capture_output=True, text=True)
    ok = r.returncode == 0 and raw.exists() and '"observations"' in raw.read_text()
    _log(f"calibration {tag} {'saved' if ok else 'FAILED'}")
    return ok


# --------------------------------------------------------------------------- #
# CLI                                                                            #
# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--submit", action="store_true")
    mode.add_argument("--sim-device", metavar="CALIBRATION_JSON")
    mode.add_argument("--analyse", metavar="RUN_DIR")
    ap.add_argument("--window-id", default="w04m")
    ap.add_argument("--campaign", default="odra_campaign")
    ap.add_argument("--root", default="runs")
    ap.add_argument("--rungs", nargs="+", default=RUNGS)
    ap.add_argument("--max-points", type=int, default=None)
    ap.add_argument("--copies", type=int, default=2)
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--t-cz", type=float, default=60e-9)
    ap.add_argument("--t-prx", type=float, default=20e-9)
    ap.add_argument("--chunk", type=int, default=100)
    ap.add_argument("--no-qasm", action="store_true")
    ap.add_argument("--wait-for", default=None, help="pgrep pattern to wait for before starting")
    ap.add_argument("--attempts", type=int, default=8)
    ap.add_argument("--sim-theta", type=float, default=0.0)
    ap.add_argument("--sim-phi", type=float, default=0.0)
    ap.add_argument("--sim-eps", type=float, default=0.0)
    add_env_argument(ap)
    args = ap.parse_args(argv)
    if args.analyse:
        analyse(args.analyse)
        return
    require_locked_environment(allow_mismatch=args.allow_env_mismatch)
    n_pts = args.max_points or 100
    n = (len(args.rungs) * n_pts + 2 * RO_COPIES) * args.copies
    hours = n * (SEC_PER_CIRCUIT + SEC_PER_SHOT * args.shots) / 3600
    print(f"window {args.window_id}: {len(args.rungs)} rungs x {n_pts} points x {args.copies} "
          f"copies (+ readout refs), S {args.shots}: ~{n} circuits, ~{hours:.1f} h at the pilot rate")
    if not (args.submit or args.sim_device):
        print("[DRY-RUN] nothing executed.")
        return
    if args.sim_device:
        from sim.device_model import load_calibration
        c = load_calibration(args.sim_device)
        args.t_prx, args.t_cz = c.t_prx, c.t_cz
    if args.wait_for:
        _wait_for(args.wait_for)
    jobs, blocks, info = build_plan(args)
    print("CZ per rung:", info)
    args.resume = True
    if args.submit:
        if not (os.environ.get("IQM_SERVER_URL") and os.environ.get("IQM_TOKEN")):
            raise SystemExit("set IQM_SERVER_URL and IQM_TOKEN")
        while not _calibration(args.window_id, "start"):
            time.sleep(600)
    for attempt in range(1, args.attempts + 1):
        try:
            ex = Executor(args)
            rec = RunRecorder.open(args.campaign, window_id=args.window_id, args=vars(args),
                                   seed=args.seed, device="odra", submitted=bool(args.submit),
                                   root=args.root)
            rec.set_extra("plan", {"design": "margin-raw-all-rungs", "rungs": info,
                                   "n_circuits": len(jobs), "blocks": blocks})
            print(f"[provenance] {rec.dir}")
            run_window(args, jobs, blocks, rec, ex)
            rec.close()
            _log(f"DONE {args.window_id}")
            break
        except Exception as e:                        # ODRA outage: wait, then resume
            _log(f"FAIL attempt {attempt}: {type(e).__name__}: {e}; retry in 10 min")
            if attempt == args.attempts or not args.submit:
                raise
            time.sleep(600)
    if args.submit:
        _calibration(args.window_id, "end")
    analyse(rec.dir)


if __name__ == "__main__":
    main()
