"""(1) Where mitigation pays: error vs shot budget and CZ count, every hardware window.

For each (window, rung, arm, point) the CDR estimate is recomputed on random subsets of the
measured copies and training circuits, so one window gives a whole error-vs-budget curve:
budget = (n_train + 1) * m * S shots per point. Raw at the same budget is the mean of the
target copies (it saturates at the raw bias). ZNE (night A only, Richardson {1,3,5}, one
copy) sits at 3 * S. Outputs:

* out/frontier_curves.csv   one row per (window, rung, arm, n_train, m): mean error over points
* out/frontier_rungs.csv    per rung: raw bias, ZNE, CDR at the night-A budget, gain factor
* out/frontier.png          error vs CZ (left) and vs budget (right)

    python -m paper_analysis.frontier
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from paper_analysis.common import HW, OUT, available, cdr_sets, load_window, logratio, ols

N_TRAINS = (5, 10, 20)
DRAWS = 60


def subsample(entry, n_train, m, rng):
    X, y, t = entry["X"], entry["y"], entry["target"]
    reps = X.shape[1]
    errs = []
    for _ in range(DRAWS):
        cols = rng.choice(reps, m, replace=False)
        rows = rng.choice(len(y), n_train, replace=False)
        x = np.nanmean(X[np.ix_(rows, cols)], axis=1)
        a, b = ols(x, y[rows])
        errs.append(abs(a * t[cols].mean() + b - entry["ideal"]))
    return float(np.mean(errs))


def raw_at(entry, m, rng):
    t = entry["target"]
    return float(np.mean([abs(t[rng.choice(len(t), m, replace=False)].mean() - entry["ideal"])
                          for _ in range(DRAWS)]))


def zne_rows():
    rows = []
    for w in ("w01A", "w01B"):
        f = HW / w / "zne.csv"
        if f.exists():
            z = pd.read_csv(f)
            z["window"] = w
            rows.append(z)
    return pd.concat(rows) if rows else pd.DataFrame()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261109)
    sets = {}
    for p in available():
        sets.update(cdr_sets(load_window(p)))
    curves = []
    for (w, rung, arm, ei), e in sets.items():
        reps = e["X"].shape[1]
        for n_train in N_TRAINS:
            if n_train > len(e["y"]):
                continue
            for m in range(1, reps + 1):
                curves.append({"window": w, "rung": rung, "arm": arm, "eval_index": ei,
                               "n_cz": e["n_cz"], "shots": e["shots"], "n_train": n_train, "m": m,
                               "budget": (n_train + 1) * m * e["shots"],
                               "err_cdr": subsample(e, n_train, m, rng),
                               "err_raw_same_budget": raw_at(e, min(reps, m), rng),
                               "raw_bias": abs(e["target"].mean() - e["ideal"])})
    c = pd.DataFrame(curves)
    agg = (c.groupby(["window", "rung", "arm", "n_cz", "n_train", "m", "budget"])
           [["err_cdr", "raw_bias"]].mean().reset_index())
    agg.to_csv(OUT / "frontier_curves.csv", index=False)

    # per rung at the night-A budget (n_train 20, all 6 copies)
    full = c[(c.n_train == 20) & (c.m == c.groupby(["window", "rung", "arm", "eval_index"]).m
                                     .transform("max"))]
    z = zne_rows()
    rows = []
    for (w, rung, arm), g in full.groupby(["window", "rung", "arm"]):
        d = logratio(g.err_cdr, g.raw_bias)
        row = {"window": w, "rung": rung, "arm": arm, "n_cz": int(g.n_cz.iloc[0]),
               "budget": int(g.budget.iloc[0]), "n_points": len(g),
               "raw_bias": g.raw_bias.mean(), "cdr": g.err_cdr.mean(),
               "gain_geo": float(np.exp(-d.mean())), "cdr_wins": int((d < 0).sum())}
        if len(z) and arm == "off_copies":
            zz = z[(z.window == w) & (z.rung == rung) & (z.variant == "genuine")]
            zg = z[(z.window == w) & (z.rung == rung) & (z.variant == "garbage")]
            if len(zz):
                row.update({"zne": zz.err_zne.mean(), "zne_garbage": zg.err_zne.mean(),
                            "zne_budget": 3 * int(g.shots.iloc[0])})
        # cheapest budget at which CDR beats raw bias on average
        cur = agg[(agg.window == w) & (agg.rung == rung) & (agg.arm == arm)].sort_values("budget")
        win = cur[cur.err_cdr < cur.raw_bias]
        row["breakeven_budget"] = int(win.budget.min()) if len(win) else None
        rows.append(row)
    r = pd.DataFrame(rows).sort_values(["arm", "n_cz", "window"])
    r.to_csv(OUT / "frontier_rungs.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(r.round(4).to_string(index=False))

    # gain vs CZ count (untwirled, all windows): is the CDR gain shrinking with depth?
    u = r[r.arm == "off_copies"]
    if len(u) > 2:
        k = np.polyfit(u.n_cz, np.log(u.gain_geo), 1)[0]
        print(f"\nCDR gain vs CZ (untwirled, {len(u)} rungs): x{np.exp(10 * k):.2f} per +10 CZ")
        print(f"raw bias vs CZ: x{np.exp(10 * np.polyfit(u.n_cz, np.log(u.raw_bias), 1)[0]):.2f} per +10 CZ;"
              f" CDR error vs CZ: x{np.exp(10 * np.polyfit(u.n_cz, np.log(u.cdr), 1)[0]):.2f} per +10 CZ")
    plot(r, agg)


def plot(r, agg):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    u = r[r.arm == "off_copies"].sort_values("n_cz")
    t = r[r.arm == "twirl_native"].sort_values("n_cz")
    ax[0].scatter(u.n_cz, u.raw_bias, c="#888888", label="raw")
    ax[0].scatter(u.n_cz, u.cdr, c="#1f5fbf", label="CDR (1 M shots)")
    if len(t):
        ax[0].scatter(t.n_cz, t.cdr, c="#e07b00", marker="s", label="CDR + twirl")
    if "zne" in u:
        zz = u.dropna(subset=["zne"])
        ax[0].scatter(zz.n_cz, zz.zne, c="#2a9d4b", marker="^", label="ZNE {1,3,5}")
        ax[0].scatter(zz.n_cz, zz.zne_garbage, c="#2a9d4b", marker="x", label="ZNE garbage")
    ax[0].set_yscale("log")
    ax[0].set_xlabel("CZ gates")
    ax[0].set_ylabel("mean |O - O_ideal|")
    ax[0].legend(fontsize=8)
    for (w, rung), g in agg[(agg.arm == "off_copies") & (agg.n_train == 20)].groupby(["window", "rung"]):
        if rung in ("star", "circular", "linear", "all_to_all"):
            ax[1].plot(g.budget, g.err_cdr, marker="o", ms=3, label=f"{rung} ({w})")
            ax[1].axhline(g.raw_bias.iloc[0], ls=":", lw=0.8, color=ax[1].lines[-1].get_color())
    ax[1].set_xscale("log")
    ax[1].set_yscale("log")
    ax[1].set_xlabel("shots per point")
    ax[1].set_ylabel("CDR error (dotted: raw bias)")
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "frontier.png", dpi=150)
    print("wrote", OUT / "frontier.png")


if __name__ == "__main__":
    main()
