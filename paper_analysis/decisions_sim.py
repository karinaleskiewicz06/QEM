"""Classifier decisions under ODRA noise on 100 points: raw vs CDR, every rung, three datasets.

Simulation only (the matched ODRA device model agrees with the hardware r = 0.99 on <O>
and 98-100 % on decisions, see accuracy.py). Per (dataset, rung, point): raw = target at
2 x 8192 shots; CDR = OLS on 20 near-Clifford training circuits of that point (1 x 8192
shots each; on ODRA more copies do not help, frontier.py).

Questions:
* how often does noise flip the ideal decision, and where (margin |O_ideal|)?
* threshold model: raw ~ s * ideal + c. A flip needs |O_ideal| < |c| / s. Note that the CDR
  decision sign(a * raw + b) is the raw decision with the threshold moved from 0 to -b/a:
  for decisions CDR is only a threshold correction;
* does CDR restore the ideal decision (McNemar), and does it change accuracy?

    python -m paper_analysis.decisions_sim two_curves
    python -m paper_analysis.decisions_sim linear
    python -m paper_analysis.decisions_sim manifold
    python -m paper_analysis.decisions_sim --report
"""
from __future__ import annotations

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import argparse  # noqa: E402
import pathlib  # noqa: E402
import sys  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from qiskit.quantum_info import Statevector  # noqa: E402
from scipy.stats import binomtest  # noqa: E402

from noisy_sim import readout_observable  # noqa: E402
from qem.cdr_training import build_training_set, clifford_ideal_expval  # noqa: E402
from qem.compile import compile_native  # noqa: E402

OUT = REPO / "paper_analysis" / "out"
CAL = REPO / "calibrations" / "odra_raw_w01B_start.json"
SHOTS, N_TRAIN = 8192, 20
TWO_CURVES_RUNGS = ["star", "linear", "circular", "all_to_all", "star_L6", "star_L9", "star_L13",
                    "star_cz24", "star_cz36", "star_cz52", "star_idle24", "star_idle36",
                    "star_idle52"]
OTHER_RUNGS = ["star", "circular", "all_to_all"]


def models(dataset):
    """[(rung, logical circuit with free features, feature params, insertion)], X, y."""
    if dataset == "two_curves":
        from campaign.odra_window import INSERTIONS, frozen
        ref = np.load(REPO / "trained_models_hard" / "two_curves_d8_q5_deg8_star_mean_L3_reference.npz")
        out = []
        for rung in TWO_CURVES_RUNGS:
            cw, xp = frozen(rung)
            out.append((rung, cw, xp, INSERTIONS.get(rung)))
        return out, ref["X_eval"], ref["y_eval"].astype(int)
    from ansatz import HardwareEfficientAnsatz
    d = REPO / "trained_models_other" / dataset
    ref = np.load(d / "reference.npz")
    out = []
    for rung in OTHER_RUNGS:
        ans = HardwareEfficientAnsatz(5, 3, num_features=8, entanglement=rung)
        c = ans.build()
        w = np.load(d / f"{rung}_L3_weights.npy")
        out.append((rung, c.assign_parameters(dict(zip(ans.weight_parameters(c), w))),
                    ans.feature_parameters(c), None))
    return out, ref["X_eval"], ref["y_eval"].astype(int)


def expval(counts):
    tot, s = 0, 0.0
    for k, c in counts.items():
        b = k.replace(" ", "")[-5:]
        s += c * np.mean([1 - 2 * int(ch) for ch in b])
        tot += c
    return s / tot


def run(dataset):
    from qem.identity_insertion import insert_identity
    from sim.device_model import build_noise_model
    dev = build_noise_model(str(CAL), 0.0, 0.0, 0.0)
    t_cz = dev.calibration.t_cz
    obs = readout_observable(5, "mean")
    mods, X, y = models(dataset)
    rows = []
    for rung, cw, xp, ins in mods:
        circs, meta = [], []
        for k, x in enumerate(X):
            lg = cw.assign_parameters(dict(zip(xp, x)))
            ideal = float(np.real(Statevector.from_instruction(lg).expectation_value(obs)))
            nat = compile_native(lg).circuit
            train = build_training_set(nat, n_train=N_TRAIN, sampler="near_target", base_seed=42,
                                       target_index=k, window_id=f"dec_{dataset}")
            members = [("target", nat, ideal)] + [("train", c, float(clifford_ideal_expval(c, obs)))
                                                 for c in train]
            for role, c, idl in members:
                if ins:
                    c = insert_identity(c, ins[0], ins[1], t_cz=t_cz)
                m = c.copy()
                m.measure_all()
                circs.append(m)
                meta.append((k, role, idl))
        vals = []
        for i in range(0, len(circs), 400):
            vals += [expval(c) for c in dev.run(circs[i:i + 400], SHOTS, seed=17 + i)]
        tgt2 = [expval(c) for c in dev.run([c for c, m in zip(circs, meta) if m[1] == "target"],
                                           SHOTS, seed=99)]
        by = {}
        for (k, role, idl), v in zip(meta, vals):
            by.setdefault(k, {"x": [], "y": []})
            if role == "target":
                by[k]["ideal"], by[k]["raw1"] = idl, v
            else:
                by[k]["x"].append(v)
                by[k]["y"].append(idl)
        for k, e in by.items():
            raw = 0.5 * (e["raw1"] + tgt2[k])
            a, b = np.polyfit(e["x"], e["y"], 1)
            rows.append({"dataset": dataset, "rung": rung, "point": k, "label": int(y[k]), "ideal": e["ideal"],
                         "raw": raw, "cdr": a * raw + b, "a": a, "b": b})
        print(f"{dataset} {rung}: done", flush=True)
    d = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT / f"decisions_sim_{dataset}.csv", index=False)


def report():
    frames = [pd.read_csv(f) for f in sorted(OUT.glob("decisions_sim_*.csv"))]
    d = pd.concat(frames)
    sg = lambda v: np.where(np.asarray(v) >= 0, 1, -1)  # noqa: E731
    d["di"], d["dr"], d["dc"] = sg(d.ideal), sg(d.raw), sg(d.cdr)
    lines = [f"{'dataset':<10s} {'rung':<12s} {'acc id':>6s} {'acc raw':>7s} {'acc CDR':>7s} "
             f"{'agr raw':>7s} {'agr CDR':>7s} {'fixed':>5s} {'broken':>6s} {'p':>6s} "
             f"{'s':>5s} {'c':>7s} {'|c|/s':>6s} {'flip pred':>9s}"]
    tot = {"fixed": 0, "broken": 0}
    for (ds, rung), g in d.groupby(["dataset", "rung"], sort=False):
        s, c = np.polyfit(g.ideal, g.raw, 1)
        thr = abs(c) / s
        flips = g.di != g.dr
        pred = sg(s * g.ideal + c) != g.di          # flip predicted by the threshold model
        fixed = int(((g.dr != g.di) & (g.dc == g.di)).sum())
        broken = int(((g.dr == g.di) & (g.dc != g.di)).sum())
        tot["fixed"] += fixed
        tot["broken"] += broken
        p = binomtest(fixed, fixed + broken).pvalue if fixed + broken else 1.0
        hit = (f"{int((pred & flips).sum())}/{int(flips.sum())}" if flips.any() else "0/0")
        lines.append(f"{ds:<10s} {rung:<12s} {np.mean(g.di == g.label):6.3f} {np.mean(g.dr == g.label):7.3f} "
                     f"{np.mean(g.dc == g.label):7.3f} {np.mean(g.dr == g.di):7.3f} "
                     f"{np.mean(g.dc == g.di):7.3f} {fixed:5d} {broken:6d} {p:6.3f} {s:5.2f} "
                     f"{c:+7.4f} {thr:6.3f} {hit:>9s}")
    p = binomtest(tot["fixed"], tot["fixed"] + tot["broken"]).pvalue
    lines.append(f"\nall cells: CDR fixed {tot['fixed']}, broke {tot['broken']} decisions "
                 f"(McNemar p = {p:.2g})")
    fl = d[d.di != d.dr]
    lines.append(f"flipped raw decisions: {len(fl)} of {len(d)}; |O_ideal| of flipped points: "
                 f"median {fl.ideal.abs().median():.3f}, max {fl.ideal.abs().max():.3f} "
                 f"(all points median {d.ideal.abs().median():.3f})")
    txt = "\n".join(lines)
    (OUT / "decisions_sim.txt").write_text(txt + "\n")
    print(txt)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", nargs="?")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        report()
    else:
        run(a.dataset)
