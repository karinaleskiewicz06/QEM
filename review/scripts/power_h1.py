"""Zad. 7: moc H1 po nocy B (32 pary, jednostronny Wilcoxon, Holm w rodzinie 5 testów).

Dane nocy A (16 par) są ustalone. Noc B (linear, all_to_all; 16 par) jest losowana:
  scenariusz "12CZ": różnice log-błędów jak na star (8 obserwowanych punktów),
  scenariusz "39CZ": jak na circular.
Losowanie łączne po punktach (wektor d_H1, d_H3, d_H6 z tego samego punktu), żeby
zachować korelację testów w Holmie. H7a/H7b ustalone na wartościach z P5
(p = 0.660 i ~5e-13, one-sided jak w prereg_w01.py).
Warianty: bootstrap z powtórzeniami (B1) oraz wygładzony bootstrap (B2: punkt + szum
N(0, h^2) z h = 0.5 * sd, by uniknąć sztucznych remisów przy 8 wartościach).
Kryterium H1: p_holm < 0.05 i średnia geometryczna ratio < 1.
"""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

T = pathlib.Path(__file__).resolve().parent / "tmp"
FLOOR = 1e-4
cdr = pd.read_csv(T / "w01A_cdr_recomputed.csv")


def le(s):
    return np.log(np.maximum(s, FLOOR))


def diffs(a, ta, b, tb):
    A = cdr[(cdr.arm == a) & (cdr.train_set == ta)].set_index(["rung", "eval_index"]).err
    B = cdr[(cdr.arm == b) & (cdr.train_set == tb)].set_index(["rung", "eval_index"]).err
    return (le(A) - le(B)).sort_index()


D = pd.DataFrame({"H1": diffs("twirl_native", "near_target", "off_copies", "near_target"),
                  "H3": diffs("twirl_native", "shared_random", "twirl_logical", "shared_random"),
                  "H6": diffs("spread", "near_target", "twirl_native", "near_target")})
print(D.groupby(level=0).agg(["mean", "std"]).round(3))
A = D.values
P7 = {"H7a": 0.6604, "H7b": 5e-13}


def holm(ps: dict) -> dict:
    keys = sorted(ps, key=ps.get)
    m, run, out = len(keys), 0.0, {}
    for k, key in enumerate(keys):
        run = max(run, min(1.0, (m - k) * ps[key]))
        out[key] = run
    return out


def sim(src: np.ndarray, n_rep: int, smooth: bool, rng) -> dict:
    sd = src.std(axis=0, ddof=1)
    hits = {"H1": 0, "H1_raw_p<0.05": 0, "H1_p<0.0125": 0}
    p_list = []
    for _ in range(n_rep):
        b = src[rng.integers(0, len(src), 16)]
        if smooth:
            b = b + rng.normal(0, 0.5 * sd, b.shape)
        allp = np.vstack([A, b])
        ps = {h: float(wilcoxon(allp[:, i], alternative="less").pvalue)
              for i, h in enumerate(("H1", "H3", "H6"))}
        ps.update(P7)
        ph = holm(ps)
        ok = ph["H1"] < 0.05 and allp[:, 0].mean() < 0
        hits["H1"] += ok
        hits["H1_raw_p<0.05"] += ps["H1"] < 0.05
        hits["H1_p<0.0125"] += ps["H1"] < 0.0125
        p_list.append(ps["H1"])
    r = {k: v / n_rep for k, v in hits.items()}
    r["median_p_H1"] = float(np.median(p_list))
    return r


rng = np.random.default_rng(20261025)
rows = []
for scen, rung in (("noc B jak 12 CZ (star)", "star"), ("noc B jak 39 CZ (circular)", "circular"),
                   ("noc B jak cała noc A (mieszanka)", None)):
    src = D.loc[rung].values if rung else A
    for smooth in (False, True):
        r = sim(src, 4000, smooth, rng)
        rows.append({"scenariusz": scen, "bootstrap": "wygładzony" if smooth else "zwykły", **r})
res = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(res.round(3).to_string(index=False))
res.to_csv(T / "power_h1.csv", index=False)
