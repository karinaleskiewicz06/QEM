"""(3) Can one tell, BEFORE trusting a mitigated number, whether CDR helped?

Everything a user has without the ideal value of the target comes from the training
circuits (their ideal values are known, they are Clifford). Predictors per
(window, rung, arm, point):

* loo      leave-one-out CDR error on the training circuits (refit without circuit i,
           predict its ideal value): an error bar for the target;
* train_raw  mean |noisy - ideal| on the training circuits: an estimate of the raw error;
* r2, a    fit quality and slope (a > 1 amplifies shot noise).

Rule: use CDR if loo < train_raw, else report raw. Checked against the truth (target
error with and without CDR): rank correlations, calibration of loo as an error bar, and
how often the rule picks the better of the two (vs always-CDR and the oracle).

    python -m paper_analysis.decision_rule
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from paper_analysis.common import OUT, available, cdr_sets, load_window, ols


def features(e):
    x = np.nanmean(e["X"], axis=1)
    y = e["y"]
    a, b = ols(x, y)
    pred = a * x + b
    ss = np.sum((y - y.mean()) ** 2)
    loo = []
    for i in range(len(y)):
        m = np.arange(len(y)) != i
        ai, bi = ols(x[m], y[m])
        loo.append(abs(ai * x[i] + bi - y[i]))
    t = e["target"].mean()
    return {"a": a, "r2": 1 - np.sum((y - pred) ** 2) / ss if ss > 0 else np.nan,
            "loo": float(np.mean(loo)), "loo_rms": float(np.sqrt(np.mean(np.square(loo)))),
            "train_raw": float(np.mean(np.abs(x - y))),
            "err_cdr": abs(a * t + b - e["ideal"]), "err_raw": abs(t - e["ideal"])}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sets = {}
    for p in available():
        sets.update(cdr_sets(load_window(p)))
    rows = [{"window": w, "rung": r, "arm": arm, "eval_index": ei, "n_cz": e["n_cz"],
             **features(e)} for (w, r, arm, ei), e in sets.items()]
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "decision_points.csv", index=False)
    print(f"{len(d)} (window, rung, arm, point) cells, "
          f"{d.groupby(['window', 'rung', 'arm']).ngroups} rung-arm cells\n")

    def rho(x, y):
        s = spearmanr(x, y)
        return f"rho={s.statistic:.2f} (p={s.pvalue:.1g})"

    print("per point:")
    print(f"  loo vs true CDR error:        {rho(d.loo, d.err_cdr)}")
    print(f"  train_raw vs true raw error:  {rho(d.train_raw, d.err_raw)}")
    print(f"  r2 vs true CDR error:         {rho(d.r2, d.err_cdr)}")
    print(f"  loo as error bar: true CDR error <= loo_rms in {np.mean(d.err_cdr <= d.loo_rms):.0%}, "
          f"<= 2 loo_rms in {np.mean(d.err_cdr <= 2 * d.loo_rms):.0%} "
          f"(Gaussian 1 sigma ~ 68 %, 2 sigma ~ 95 %)")

    c = (d.groupby(["window", "rung", "arm", "n_cz"])[["loo", "loo_rms", "train_raw", "r2", "a",
                                                      "err_cdr", "err_raw"]].mean().reset_index())
    c.to_csv(OUT / "decision_cells.csv", index=False)
    print("\nper rung-arm cell (mean over 8 points):")
    print(f"  loo vs true CDR error:        {rho(c.loo, c.err_cdr)}; "
          f"median ratio true/loo {np.median(c.err_cdr / c.loo):.2f}")
    print(f"  train_raw vs true raw error:  {rho(c.train_raw, c.err_raw)}; "
          f"median ratio {np.median(c.err_raw / c.train_raw):.2f}")
    print(f"  predicted gain train_raw/loo vs true gain err_raw/err_cdr: "
          f"{rho(c.train_raw / c.loo, c.err_raw / c.err_cdr)}")

    use_cdr = d.loo < d.train_raw
    better_cdr = d.err_cdr < d.err_raw
    chosen = np.where(use_cdr, d.err_cdr, d.err_raw)
    oracle = np.minimum(d.err_cdr, d.err_raw)
    print("\nrule 'CDR if loo < train_raw':")
    print(f"  picks CDR in {use_cdr.mean():.0%} of points; CDR truly better in {better_cdr.mean():.0%}")
    print(f"  rule picks the better option in {np.mean(use_cdr == better_cdr):.0%} "
          f"(always-CDR: {better_cdr.mean():.0%})")
    print(f"  mean error: rule {chosen.mean():.4f} | always CDR {d.err_cdr.mean():.4f} | "
          f"always raw {d.err_raw.mean():.4f} | oracle {oracle.mean():.4f}")
    with pd.option_context("display.width", 200):
        print("\n", c.sort_values(["arm", "n_cz"]).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
