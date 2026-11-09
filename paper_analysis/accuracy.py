"""(4) Does mitigation change the classifier's decision? And (5) does the simulator predict ODRA?

Decision = sign(<O>) (threshold 0, as in training). Two scores per method:

* acc     agreement with the true label y of the eval point;
* agree   agreement with the IDEAL circuit's decision sign(O_ideal): what mitigation can at
          best restore (the noiseless model itself is wrong on some points).

Methods: raw (mean of the target copies), CDR (untwirled, all copies), CDR + twirl, ZNE
{1,3,5} (nights A, B). The eval points are stratified by |O_ideal| (a quarter sit next to
the decision boundary), so results are also given for the points with |O_ideal| above the
median of the rung.

Simulation vs ODRA: the matched simulations (same windows, circuits, shots; device model
from that window's start calibration) are scored the same way and correlated with the
hardware per point (values, errors, decisions) and per rung-method cell (accuracy, error).

    python -m paper_analysis.accuracy
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import binomtest, pearsonr, spearmanr

from paper_analysis.common import HW, OUT, SIM, available, cdr_sets, labels, load_window, ols


def estimates(root):
    """One row per (window, rung, point, method) with the estimate of <O>."""
    rows = []
    for p in available(root):
        sets = cdr_sets(load_window(p))
        for (w, rung, arm, ei), e in sets.items():
            x = np.nanmean(e["X"], axis=1)
            a, b = ols(x, e["y"])
            t = e["target"].mean()
            base = {"window": w, "rung": rung, "eval_index": ei, "n_cz": e["n_cz"],
                    "ideal": e["ideal"]}
            if arm == "off_copies":
                rows.append({**base, "method": "raw", "est": t})
                rows.append({**base, "method": "CDR", "est": a * t + b})
            elif arm == "twirl_native":
                rows.append({**base, "method": "CDR+twirl", "est": a * t + b})
            elif arm == "dd_on":
                rows.append({**base, "method": "CDR+DD", "est": a * t + b})
        z = p / "zne.csv"
        if z.exists():
            zz = pd.read_csv(z)
            for _, r in zz[zz.variant == "genuine"].iterrows():
                rows.append({"window": p.name, "rung": r.rung, "eval_index": int(r.eval_index),
                             "n_cz": int(r.n_cz), "ideal": r.ideal, "method": "ZNE", "est": r.zne})
    d = pd.DataFrame(rows)
    y = labels()
    d["y"] = d.eval_index.map(y)
    sgn = lambda v: np.where(np.asarray(v) >= 0, 1, -1)  # noqa: E731
    d["dec"] = sgn(d.est)
    d["acc"] = (d.dec == d.y).astype(int)
    d["agree"] = (d.dec == sgn(d.ideal)).astype(int)
    d["err"] = (d.est - d.ideal).abs()
    med = d.groupby(["window", "rung"]).ideal.transform(lambda s: s.abs().median())
    d["clear"] = d.ideal.abs() > med
    return d


def mcnemar(d, m1, m2, col="agree"):
    a = d[d.method == m1].set_index(["window", "rung", "eval_index"])[col]
    b = d[d.method == m2].set_index(["window", "rung", "eval_index"])[col]
    j = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
    up, down = int(((j.b == 1) & (j.a == 0)).sum()), int(((j.b == 0) & (j.a == 1)).sum())
    p = binomtest(up, up + down).pvalue if up + down else 1.0
    return len(j), up, down, p


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    hw = estimates(HW)
    hw.to_csv(OUT / "accuracy_points_hw.csv", index=False)
    ideal_acc = (hw[hw.method == "raw"].assign(a=lambda t: (np.where(t.ideal >= 0, 1, -1) == t.y))
                 .groupby(["window", "rung"]).a.mean())
    print("=== ODRA: decision accuracy (8 points per rung) ===")
    tab = hw.pivot_table(index=["window", "rung", "n_cz"], columns="method", values="acc")
    tab["ideal"] = ideal_acc
    print(tab.round(3).to_string())
    print("\nagreement with the ideal decision:")
    print(hw.pivot_table(index=["window", "rung", "n_cz"], columns="method", values="agree").round(3)
          .to_string())
    print("\npooled over all windows and rungs:")
    for col in ("acc", "agree"):
        s = hw.groupby("method")[col].agg(["mean", "count"])
        print(f"  {col}: " + ", ".join(f"{m} {r['mean']:.3f} (n={int(r['count'])})" for m, r in s.iterrows()))
    c = hw[hw.clear]
    print("  agree, points with |O_ideal| above the rung median: " + ", ".join(
        f"{m} {v:.3f}" for m, v in c.groupby("method").agree.mean().items()))
    for m in ("CDR", "CDR+twirl", "ZNE"):
        n, up, down, p = mcnemar(hw, "raw", m)
        if n:
            print(f"  McNemar raw -> {m} (agree with ideal): n={n}, fixed {up}, broken {down}, p={p:.3f}")

    if not available(SIM):
        print("\n(no matched simulations yet)")
        return
    sim = estimates(SIM)
    sim.to_csv(OUT / "accuracy_points_sim.csv", index=False)
    k = ["window", "rung", "eval_index", "method"]
    j = hw.merge(sim[k + ["est", "err", "dec", "acc", "agree"]], on=k, suffixes=("_hw", "_sim"))
    j.to_csv(OUT / "sim_vs_hw_points.csv", index=False)
    print(f"\n=== simulation vs ODRA ({j.window.nunique()} windows, {len(j)} point-method pairs) ===")
    for m, g in j.groupby("method"):
        pr, sr = pearsonr(g.est_hw, g.est_sim), spearmanr(g.est_hw, g.est_sim)
        pe = spearmanr(g.err_hw, g.err_sim)
        print(f"  {m:<10s} <O>: Pearson r={pr.statistic:.3f}, Spearman {sr.statistic:.3f} | "
              f"error: Spearman {pe.statistic:.2f} (p={pe.pvalue:.1g}) | same decision "
              f"{np.mean(g.dec_hw == g.dec_sim):.0%} | mean err hw {g.err_hw.mean():.4f} "
              f"sim {g.err_sim.mean():.4f} (x{g.err_hw.mean() / g.err_sim.mean():.1f})")
    cell = j.groupby(["window", "rung", "method"])[["acc_hw", "acc_sim", "agree_hw", "agree_sim",
                                                    "err_hw", "err_sim"]].mean().reset_index()
    cell.to_csv(OUT / "sim_vs_hw_cells.csv", index=False)
    print(f"\nper rung-method cell ({len(cell)} cells):")
    for a, b in (("acc_hw", "acc_sim"), ("agree_hw", "agree_sim"), ("err_hw", "err_sim")):
        pr, sr = pearsonr(cell[a], cell[b]), spearmanr(cell[a], cell[b])
        print(f"  {a[:-3]:<6s}: Pearson r={pr.statistic:.2f} (p={pr.pvalue:.1g}), "
              f"Spearman {sr.statistic:.2f} (p={sr.pvalue:.1g}); mean hw {cell[a].mean():.3f} "
              f"sim {cell[b].mean():.3f}")
    with pd.option_context("display.width", 200):
        print(cell.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
