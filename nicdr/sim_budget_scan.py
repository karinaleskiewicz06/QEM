"""Does noise-informed CDR win in principle, and at what shot budget? -- Aer, offline.

Device model: sim/device_model.py built from the w01A start calibration (thermal relaxation
in gates and in idle gaps, depolarizing matched to RB/IRB, asymmetric readout), optionally
with a coherent ZZ error on every CZ. The circuits are the campaign's own: the frozen star
and circular classifiers at the 8 evaluation points of point set 0, their near-Clifford
training sets (near_target, n_train = 20), and two noise-scaled copies of every target
and training circuit: + k CZ.CZ pairs (CZ axis) and + matched idle (time axis).

Each circuit is simulated once with 2^20 shots, which is treated as its exact outcome
distribution; every shot budget is then drawn from it many times. At budget B (shots per
evaluation point) each method spends exactly B:

* CDR      21 circuits at the base level, B/21 shots each;
* MI-CDR   same data as CDR, noise model M_2 fitted on all points of the rung;
* vn_t / vn_cz   21 circuits x 2 levels, B/42 shots each;
* vn_2ax   21 circuits x 3 levels, B/63 shots each.

    python -m nicdr.sim_budget_scan [--theta 0 0.05] [--draws 40]
"""
from __future__ import annotations

import argparse
import csv
import json
import time

import numpy as np
from qiskit.quantum_info import Statevector

from nicdr.common import OUT_SIM, REPO, fit_noise, multi_reg, ols_line

CAL = REPO / "calibrations" / "odra_raw_w01A_start.json"
RUNG_PAIRS = {"star": 12, "circular": 12}      # +24 CZ on both rungs
BUDGETS = [24_576, 103_219, 258_048, 516_096, 1_032_192, 2_064_384, 4_128_768]
N_TRAIN = 20
EXACT_SHOTS = 2 ** 20


def build_circuits(t_cz, t_prx):
    from campaign.odra_window import frozen
    from qem.cdr_training import build_training_set, clifford_ideal_expval
    from qem.compile import compile_native
    from qem.identity_insertion import insert_identity, scheduled_duration
    from noisy_sim import readout_observable

    obs = readout_observable(5, "mean")
    pts = json.load(open(REPO / "campaign" / "eval_points.json"))["points"]
    pts = [p for p in pts if p["eval_index"] in (0, 3, 6, 9, 12, 15, 18, 21)]
    specs = []          # dicts with circuit + metadata
    for rung, k in RUNG_PAIRS.items():
        cw, xp = frozen(rung)
        for p in pts:
            ei = p["eval_index"]
            lg = cw.assign_parameters(dict(zip(xp, p["x"])))
            ideal_t = float(np.real(Statevector.from_instruction(lg).expectation_value(obs)))
            nat = compile_native(lg).circuit
            train = build_training_set(nat, n_train=N_TRAIN, sampler="near_target",
                                       base_seed=42, target_index=ei, window_id="simNI")
            members = [("target", None, nat, ideal_t)] + [
                ("train", i, c, float(clifford_ideal_expval(c, obs))) for i, c in enumerate(train)]
            for role, ti, base, ideal in members:
                for level in ("base", "cz", "idle"):
                    if level == "base":
                        c = base.copy()
                    elif level == "cz":
                        c = insert_identity(base, k, "cz_pairs", t_cz=t_cz)
                    else:
                        c = insert_identity(base, k, "idle_matched", t_cz=t_cz)
                    ops = c.count_ops()
                    t_us = scheduled_duration(c, t_prx=t_prx, t_cz=t_cz) * 1e6
                    m = c.copy()
                    m.measure_all()
                    specs.append({"rung": rung, "eval_index": ei, "role": role, "train_index": ti,
                                  "level": level, "ideal": ideal, "n_cz": int(ops.get("cz", 0)),
                                  "n_prx": int(ops.get("r", 0)), "t_us": t_us, "circ": m})
    return specs


def outcome_dist(counts):
    vals, p = [], []
    tot = sum(counts.values())
    for key, c in counts.items():
        s = key.replace(" ", "")[-5:].zfill(5)
        vals.append(np.mean([1 - 2 * int(s[4 - q]) for q in range(5)]))
        p.append(c / tot)
    return np.array(vals), np.array(p)


def sample_mean(dist, n, rng):
    vals, p = dist
    if n <= 0:
        return float("nan")
    c = rng.multinomial(n, p)
    return float(np.dot(vals, c) / n)


def run_theta(theta, draws, log):
    from sim.device_model import build_noise_model
    dev = build_noise_model(str(CAL), theta, 0.0, 0.0)
    cal = dev.calibration
    t0 = time.time()
    specs = build_circuits(cal.t_cz, cal.t_prx)
    log(f"theta={theta}: built {len(specs)} circuits in {time.time() - t0:.0f}s; simulating "
        f"({EXACT_SHOTS} shots each)")
    t0 = time.time()
    chunk = 120
    for i in range(0, len(specs), chunk):
        part = specs[i:i + chunk]
        counts = dev.run([s["circ"] for s in part], EXACT_SHOTS, seed=1000 + i)
        for s, cn in zip(part, counts):
            s["dist"] = outcome_dist(cn)
            s["exact"] = float(np.dot(*s["dist"]))
            s.pop("circ")
    log(f"  simulated in {time.time() - t0:.0f}s")

    idx = {}
    for s in specs:
        idx[(s["rung"], s["eval_index"], s["role"], s["train_index"], s["level"])] = s
    pts = sorted({(s["rung"], s["eval_index"]) for s in specs})

    def values(rung, ei, level, n, rng):
        tgt = idx[(rung, ei, "target", None, level)]
        tr = [idx[(rung, ei, "train", i, level)] for i in range(N_TRAIN)]
        if rng is None:
            return tgt["exact"], np.array([t["exact"] for t in tr]), tgt, tr
        return (sample_mean(tgt["dist"], n, rng),
                np.array([sample_mean(t["dist"], n, rng) for t in tr]), tgt, tr)

    methods = {"CDR": ["base"], "vn_t": ["base", "idle"], "vn_cz": ["base", "cz"],
               "vn_2ax": ["base", "cz", "idle"]}
    rows = []
    for B in [None] + BUDGETS:
        reps = 1 if B is None else draws
        rng = None if B is None else np.random.default_rng(int(1e6 * (theta + 1)) + (B or 0))
        err = {m: {p: [] for p in pts} for m in list(methods) + ["MI"]}
        for _ in range(reps):
            cache = {}
            for name, levels in methods.items():
                n = None if B is None else B // (len(levels) * (N_TRAIN + 1))
                for (rung, ei) in pts:
                    Xtr, Xte = [], []
                    for lv in levels:
                        if (rung, ei, lv, n) not in cache:
                            cache[(rung, ei, lv, n)] = values(rung, ei, lv, n, rng)
                        e_t, e_tr, tgt, tr = cache[(rung, ei, lv, n)]
                        Xtr.append(e_tr)
                        Xte.append(e_t)
                    y = np.array([t["ideal"] for t in tr])
                    if len(levels) == 1:
                        a, b = ols_line(Xtr[0], y)
                        est = a * Xte[0] + b
                    else:
                        est = float(multi_reg(np.array(Xtr).T, y, np.array(Xte)[None, :])[0][0])
                    err[name][(rung, ei)].append(abs(est - tgt["ideal"]))
            # MI-CDR on the CDR (base) data, model pooled over the 8 points of each rung
            n = None if B is None else B // (N_TRAIN + 1)
            for rung in RUNG_PAIRS:
                E, I, C, T, P = [], [], [], [], []
                for (r, ei) in pts:
                    if r != rung:
                        continue
                    _, e_tr, _, tr = cache[(r, ei, "base", n)]
                    E += list(e_tr)
                    I += [t["ideal"] for t in tr]
                    C += [t["n_cz"] for t in tr]
                    T += [t["t_us"] for t in tr]
                    P += [t["n_prx"] for t in tr]
                model = fit_noise("M_2", E, I, C, T, P)
                for (r, ei) in pts:
                    if r != rung:
                        continue
                    e_t, _, tgt, _ = cache[(r, ei, "base", n)]
                    est = float(model.invert(e_t, tgt["n_cz"], tgt["t_us"], tgt["n_prx"]))
                    err["MI"][(r, ei)].append(abs(est - tgt["ideal"]))
        for rung in RUNG_PAIRS:
            base = np.array([np.mean(err["CDR"][p]) for p in pts if p[0] == rung])
            for m in err:
                e = np.array([np.mean(err[m][p]) for p in pts if p[0] == rung])
                rows.append({"theta": theta, "budget": "exact" if B is None else B, "rung": rung,
                             "method": m, "mean_err": float(e.mean()),
                             "wins_vs_CDR": int((e < base - 1e-12).sum()) if m != "CDR" else "",
                             "ratio_vs_CDR": float(e.mean() / base.mean())})
        lab = "exact" if B is None else f"{B:>9d}"
        log("  B=" + lab + "  " + "  ".join(
            f"{r['rung'][:4]}:{r['method']}={r['mean_err']:.4f}" for r in rows[-2 * len(err):]))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theta", type=float, nargs="+", default=[0.0, 0.05])
    ap.add_argument("--draws", type=int, default=40)
    args = ap.parse_args()
    OUT_SIM.mkdir(parents=True, exist_ok=True)
    lines = []

    def log(s):
        print(s, flush=True)
        lines.append(s)

    log(f"calibration: {CAL.name}; insertions {RUNG_PAIRS}; budgets {BUDGETS}; draws {args.draws}")
    rows = []
    for th in args.theta:
        rows += run_theta(th, args.draws, log)
    with (OUT_SIM / "budget_scan.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (OUT_SIM / "budget_scan.log").write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT_SIM}/budget_scan.csv and budget_scan.log")


if __name__ == "__main__":
    main()
