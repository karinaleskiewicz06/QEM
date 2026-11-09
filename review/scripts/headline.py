"""Liczby nagłówkowe z przeliczonych CSV (review/scripts/tmp) + testy."""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import wilcoxon

T = pathlib.Path(__file__).resolve().parent / "tmp"
FLOOR = 1e-4
cdr = pd.read_csv(T / "w01A_cdr_recomputed.csv")
zne = pd.read_csv(T / "w01A_zne_recomputed.csv")

print("CDR mean err (OLS) per rung x arm:")
print(cdr.pivot_table(index="rung", columns=["arm", "train_set"], values="err").round(4).T)
raw = cdr[(cdr.arm == "off_copies")].groupby("rung").err_raw.mean()
print("raw (off_copies target):", raw.round(4).to_dict())
print("raw per arm:", cdr.pivot_table(index="rung", columns="arm", values="err_raw").round(4).to_dict())
print("\nZNE mean err:")
print(zne.pivot_table(index="rung", columns="variant", values="err_zne").round(4))
print(zne.pivot_table(index="rung", columns="variant", values=["ev_lam3", "ev_lam5"]).round(3))
print("mean ideal:", zne[zne.variant == "genuine"].groupby("rung").ideal.mean().round(3).to_dict())


def lerr(s):
    return np.log(np.maximum(s.values, FLOOR))


def pair(a, b, ts_a="near_target", ts_b="near_target"):
    A = cdr[(cdr.arm == a) & (cdr.train_set == ts_a)].set_index(["rung", "eval_index"])
    B = cdr[(cdr.arm == b) & (cdr.train_set == ts_b)].set_index(["rung", "eval_index"])
    return A.join(B, lsuffix="_a", rsuffix="_b", how="inner")


j = pair("twirl_native", "off_copies")
for rung, g in j.groupby(level="rung"):
    d = lerr(g.err_a) - lerr(g.err_b)
    print(f"twirl vs off {rung}: wins {int((d < 0).sum())}/8 geo-ratio {np.exp(d.mean()):.3f} "
          f"p1s={wilcoxon(d, alternative='less').pvalue:.3f}")
d = lerr(j.err_a) - lerr(j.err_b)
print(f"pooled 16: p={wilcoxon(d, alternative='less').pvalue:.4f} ratio {np.exp(d.mean()):.3f}")
np.save(T / "h1_logdiff_A.npy", d)
np.save(T / "h1_logdiff_rung.npy", np.array([r for r, _ in j.index]))
for nm, (a, ta, b, tb) in {"H3": ("twirl_native", "shared_random", "twirl_logical", "shared_random"),
                           "H6": ("spread", "near_target", "twirl_native", "near_target")}.items():
    jj = pair(a, b, ta, tb)
    dd = lerr(jj.err_a) - lerr(jj.err_b)
    print(f"{nm} pooled: p={wilcoxon(dd, alternative='less').pvalue:.4f} ratio {np.exp(dd.mean()):.3f}"
          f" per rung {[round(float(np.exp(dd[jj.index.get_level_values(0) == r].mean())), 3) for r in ('star', 'circular')]}")

print("\nH4:")
for rung, g in zne.groupby("rung"):
    gen = g[g.variant == "genuine"].set_index("eval_index")
    gar = g[g.variant == "garbage"].set_index("eval_index")
    p_raw = wilcoxon(lerr(gen.err_zne), lerr(gen.err_raw), alternative="less").pvalue
    p_gar = wilcoxon(lerr(gen.err_zne), lerr(gar.err_zne.loc[gen.index]), alternative="less").pvalue
    p_raw_lin = wilcoxon(gen.err_zne, gen.err_raw, alternative="less").pvalue
    p_gar_lin = wilcoxon(gen.err_zne, gar.err_zne.loc[gen.index], alternative="less").pvalue
    print(f"  {rung}: ZNE<raw p={p_raw:.4f} (lin {p_raw_lin:.4f}); ZNE<garbage p={p_gar:.4f} "
          f"(lin {p_gar_lin:.4f}); median W_neg {gen.w_neg.median():.4f}, median SNR {gen.snr_lmax.median():.2f}")

# P5
p5 = pd.read_csv(T / "w01P5_cdr_recomputed.csv")
p5 = p5[(p5.arm == "off_copies") & (p5.train_set == "near_target")].copy()
orig = pd.read_csv("runs/odra_campaign/w01P5/cdr.csv")
orig = orig[orig.fit == "ols"][["rung", "eval_index", "duration_sched_s", "n_prx"]]
p5 = p5.merge(orig, on=["rung", "eval_index"])
p5["cz10"] = p5.n_cz / 10
p5["dur_us"] = p5.duration_sched_s * 1e6
p5["ler"] = np.log(np.maximum(p5.err_raw, FLOOR))
p5["lec"] = np.log(np.maximum(p5.err, FLOOR))
print("\nP5 rungs:", p5.groupby("rung")[["n_cz", "n_prx", "dur_us", "err_raw", "err"]].mean().round(4))
l3 = p5[~p5.rung.str.match(r"star_L\d+")]
for lab, sub in (("l3_only", l3), ("l3 bez star_cz52", l3[l3.rung != "star_cz52"])):
    for y in ("ler", "lec"):
        m = smf.ols(f"{y} ~ cz10 + dur_us + C(eval_index)", data=sub).fit(
            cov_type="cluster", cov_kwds={"groups": sub.eval_index})
        print(f"  {lab} {y}: cz10 factor {np.exp(m.params.cz10):.3f} p={m.pvalues.cz10:.2g}; "
              f"dur factor {np.exp(m.params.dur_us):.3f} p={m.pvalues.dur_us:.2g}; n={int(m.nobs)}")
    # korelacja cz10 i dur
    print(f"  {lab}: corr(cz10,dur)={np.corrcoef(sub.cz10, sub.dur_us)[0,1]:.3f}")
