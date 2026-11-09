"""Add-on to nicdr_sim.py: budget scan (bias/variance crossover of vnCDR vs CDR) and the
model-informed estimator refit on *shot-noisy* training data. Twirled-ZZ truth by default.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
from scipy.optimize import least_squares

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nicdr_sim as m  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent
twirl = "--coherent" not in sys.argv
truth = dict(T1=40e-6, T2=25e-6, p1=1e-3, p2=0.012, eps=0.10, twirl=twirl, pro=0.02)
rng = np.random.default_rng(11)
n_targets, n_train = 6, 20
rows = []
for t in range(n_targets):
    tgt = m.star_target(rng)
    tr = [m.snap(tgt, rng, "matched", nearest=True)] + [m.snap(tgt, rng, "matched")
                                                        for _ in range(n_train - 1)]
    rows.append(dict(
        ideal=m.ideal(tgt), y=np.array([m.ideal(c) for c in tr]),
        tgt=np.array([m.simulate(m.fold(tgt, l), truth) for l in (1, 3, 5)]),
        X=np.array([[m.simulate(m.fold(c, l), truth) for l in (1, 3, 5)] for c in tr]),
        circ=tgt, tr=tr))
    print("built", t, flush=True)

mrng = np.random.default_rng(5)


def noisy(v, S):
    v = np.asarray(v, float)
    return v + mrng.normal(0, 1, v.shape) * np.sqrt(np.clip(1 - v ** 2, 1e-6, None) / (m.N * S))


lam = np.array([1, 3, 5.0])
scan = {}
for B in (42_000, 168_000, 672_000, 2_688_000):
    S21, S63, S3 = B // 21, B // 63, B // 3
    e = {k: [] for k in ("cdr", "vncdr", "vncdr_int", "vncdr_13", "zne_lin")}
    for r in rows:
        for _ in range(400):
            e["cdr"].append(abs(m.predict(m.ols(noisy(r["X"][:, 0], S21), r["y"]),
                                          noisy(r["tgt"][0], S21)) - r["ideal"]))
            Xn, tn = noisy(r["X"], S63), noisy(r["tgt"], S63)
            e["vncdr"].append(abs(m.predict(m.ols(Xn, r["y"], False), tn, False) - r["ideal"]))
            e["vncdr_int"].append(abs(m.predict(m.ols(Xn, r["y"]), tn) - r["ideal"]))
            S42 = B // 42
            X2, t2 = noisy(r["X"][:, :2], S42), noisy(r["tgt"][:2], S42)
            e["vncdr_13"].append(abs(m.predict(m.ols(X2, r["y"], False), t2, False) - r["ideal"]))
            e["zne_lin"].append(abs(float(np.polyfit(lam, noisy(r["tgt"], S3), 1)[1]) - r["ideal"]))
    scan[B] = {k: float(np.mean(v)) for k, v in e.items()}
    print(B, scan[B], flush=True)


def model(p):
    p2, k, rr = p
    return dict(T1=40e-6 / k, T2=25e-6 / k, p1=1e-3, p2=p2, eps=0, twirl=False, pro=(1 - rr) / 2)


ms_err = []
for r in rows[:4]:
    for rep in range(3):
        xs = noisy(r["X"][:, 0], 2000)
        fit = least_squares(lambda p: np.array([m.simulate(c, model(p)) for c in r["tr"]]) - xs,
                            x0=[0.01, 1.0, 0.96], bounds=([0, 0.05, 0.5], [0.2, 20, 1.0]),
                            diff_step=1e-3, max_nfev=30).x
        bias = m.simulate(r["circ"], model(fit)) - r["ideal"]
        ms_err.append(abs(noisy(r["tgt"][0], 2000) - bias - r["ideal"]))
    print("model_sub noisy-fit so far", np.mean(ms_err), flush=True)

res = dict(truth=str(truth), budget_scan=scan, model_sub_noisy_fit_mae=float(np.mean(ms_err)),
           model_sub_n=len(ms_err))
(OUT / f"nicdr_addon{'_twirl' if twirl else '_coherent'}.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
