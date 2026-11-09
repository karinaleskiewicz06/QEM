"""Niezależne przeliczenie CDR/ZNE z counts.jsonl (bez importu kodu projektu).

Uruchomienie: python review/scripts/recompute_w01A.py runs/odra_campaign/w01A
Zapisuje do review/scripts/tmp/<okno>_{cdr,zne}_recomputed.csv. Nic nie zapisuje w runs/.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

import numpy as np
import pandas as pd

N = 5
OUT = pathlib.Path(__file__).resolve().parent / "tmp"


def meanz(counts, order="qiskit"):
    """<(1/n) sum Z_q>; dla mean-Z kolejność bitów nie ma znaczenia (sprawdzamy to)."""
    tot, acc = 0, 0.0
    zq = np.zeros(N)
    for k, c in counts.items():
        s = k.replace(" ", "")
        s = s[-N:] if order == "qiskit" else s[:N]
        bits = [int(ch) for ch in s]
        zq += c * (1 - 2 * np.array(bits))
        tot += c
    return float(zq.mean() / tot), zq / tot


def probs(counts):
    p = np.zeros(2 ** N)
    tot = 0
    for k, c in counts.items():
        s = k.replace(" ", "")[-N:]
        p[int(s, 2)] += c
        tot += c
    return p / tot


def ols(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    xm, ym = x.mean(), y.mean()
    a = np.sum((x - xm) * (y - ym)) / np.sum((x - xm) ** 2)
    b = ym - a * xm
    r2 = 1 - np.sum((y - a * x - b) ** 2) / np.sum((y - ym) ** 2)
    return a, b, r2


C135 = np.array([15 / 8, -5 / 4, 3 / 8])


def main(run_dir):
    run_dir = pathlib.Path(run_dir)
    recs = [json.loads(l) for l in (run_dir / "counts.jsonl").open() if l.strip()]
    # 1. expval z counts
    d_ev, d_order = 0.0, 0.0
    for r in recs:
        q, zq = meanz(r["counts"], "qiskit")
        i, _ = meanz(r["counts"], "iqm")
        d_ev = max(d_ev, abs(q - r["expval"]))
        d_order = max(d_order, abs(q - i))
        r["_ev"] = q
        assert sum(r["counts"].values()) == r["shots"], r["circuit_id"]
    print(f"max|expval(counts)-expval(rec)| = {d_ev:.3g}; max|qiskit-iqm order| = {d_order:.3g}")

    # 3. budżet
    shots = collections.defaultdict(int)
    for r in recs:
        if r["kind"] == "cdr":
            shots[(r["rung"], r["arm"], r["train_set"], r["eval_index"])] += r["shots"]
    print("budżet CDR na punkt:", collections.Counter(shots.values()))
    zsh = collections.defaultdict(int)
    for r in recs:
        if r["kind"] == "zne" and r["variant"] == "genuine":
            zsh[(r["rung"], r["eval_index"])] += r["shots"]
    print("budżet ZNE genuine na punkt:", collections.Counter(zsh.values()))

    # CDR
    g = collections.defaultdict(list)
    for r in recs:
        if r["kind"] == "cdr":
            g[(r["rung"], r["arm"], r["train_set"], r["eval_index"])].append(r)
    rows = []
    for key, rs in sorted(g.items()):
        tgt = [r for r in rs if r["role"] == "target"]
        tr = collections.defaultdict(list)
        for r in rs:
            if r["role"] == "train":
                tr[r["train_index"]].append(r)
        ideals_t = {r["ideal"] for r in tgt}
        assert len(ideals_t) == 1
        x = [np.mean([r["_ev"] for r in tr[i]]) for i in sorted(tr)]
        y = [tr[i][0]["ideal"] for i in sorted(tr)]
        assert all(len({r["ideal"] for r in tr[i]}) == 1 for i in tr)
        a, b, r2 = ols(x, y)
        raw = float(np.mean([r["_ev"] for r in tgt]))
        ideal = tgt[0]["ideal"]
        mit = a * raw + b
        rows.append(dict(rung=key[0], arm=key[1], train_set=key[2], eval_index=key[3],
                         n_cz=tgt[0]["n_cz"], ideal=ideal, raw=raw, mitigated=mit,
                         err_raw=abs(raw - ideal), err=abs(mit - ideal), a=a, b=b, r2=r2,
                         n_train_points=len(x), n_target=len(tgt),
                         shots_total=sum(r["shots"] for r in rs)))
    cdr = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    cdr.to_csv(OUT / f"{run_dir.name}_cdr_recomputed.csv", index=False)

    # ZNE
    z = collections.defaultdict(dict)
    for r in recs:
        if r["kind"] == "zne":
            z[(r["rung"], r["eval_index"])][(r["variant"], r["scale"])] = r
    zrows = []
    for (rung, eix), d in sorted(z.items()):
        base = d[("genuine", 1)]
        for v in ("genuine", "identity", "garbage"):
            sel = [base, d[(v, 3)], d[(v, 5)]]
            ev = np.array([s["_ev"] for s in sel])
            est = float(C135 @ ev)
            ph = sum(c * probs(s["counts"]) for c, s in zip(C135, sel))
            wneg = float(-ph[ph < 0].sum())
            # SE na lambda=5: wariancja per-shot obserwabli mean-Z
            p5 = probs(sel[-1]["counts"])
            idx = np.arange(32)
            val = np.array([np.mean(1 - 2 * ((i >> np.arange(N)) & 1)) for i in idx])
            var = p5 @ (val - p5 @ val) ** 2
            se = np.sqrt(var / sel[-1]["shots"])
            zrows.append(dict(rung=rung, eval_index=eix, variant=v, ideal=base["ideal"],
                              ev_lam1=ev[0], ev_lam3=ev[1], ev_lam5=ev[2], zne=est,
                              err_raw=abs(ev[0] - base["ideal"]),
                              err_zne=abs(est - base["ideal"]), w_neg=wneg,
                              snr_lmax=abs(ev[2]) / se))
    zne = pd.DataFrame(zrows)
    zne.to_csv(OUT / f"{run_dir.name}_zne_recomputed.csv", index=False)

    # porównanie z CSV projektu
    for name, mine, keys, cols in (
            ("cdr.csv", cdr, ["rung", "arm", "train_set", "eval_index"],
             ["ideal", "raw", "mitigated", "err_raw", "err", "a", "b", "r2", "shots_total",
              "n_train_points"]),
            ("zne.csv", zne, ["rung", "variant", "eval_index"],
             ["ev_lam1", "ev_lam3", "ev_lam5", "zne", "err_raw", "err_zne", "w_neg",
              "snr_lmax"])):
        p = run_dir / name
        if not p.exists():
            continue
        theirs = pd.read_csv(p)
        if "fit" in theirs:
            theirs = theirs[theirs.fit == "ols"]
        m = mine.merge(theirs, on=keys, suffixes=("", "_csv"), how="outer", indicator=True)
        print(f"\n{name}: wiersze {len(mine)} (moje) vs {len(theirs)} (CSV); "
              f"niesparowane: {(m._merge != 'both').sum()}")
        for c in cols:
            dd = np.abs(m[c].astype(float) - m[c + "_csv"].astype(float))
            print(f"  max |Δ {c}| = {dd.max():.3g}")
    return cdr, zne


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "runs/odra_campaign/w01A")
