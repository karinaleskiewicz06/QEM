"""P5 regression with small-cluster inference, for the paper (read-only on the data).

    KMP_DUPLICATE_LIB_OK=TRUE python paper_draft/figs/p5_robust_paper.py

log err ~ cz10 + dur_us + point fixed effects, L=3 rungs of night P5 (off_copies, OLS CDR).
For each sample (all L3 rungs; without star_cz52; without star_cz24 and star_cz52) and each
outcome (raw, after CDR) it reports the factor exp(beta), the cluster-robust CI and p with
the t(G-1) reference (G = 8 points), and an exact wild-cluster-bootstrap p (Rademacher,
restricted under H0, all 2^8 sign vectors enumerated). Writes p5_robust_numbers.txt.
"""
from __future__ import annotations

import itertools
import pathlib
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

warnings.filterwarnings("ignore")
HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
FLOOR = 1e-4

p5 = pd.read_csv(REPO / "runs/odra_campaign/w01P5/cdr.csv")
p5 = p5[(p5.fit == "ols") & (p5.arm == "off_copies") & (p5.train_set == "near_target")].copy()
p5["cz10"], p5["dur_us"] = p5.n_cz / 10, p5.duration_sched_s * 1e6
p5["ler"] = np.log(np.maximum(p5.err_raw, FLOOR))
p5["lec"] = np.log(np.maximum(p5.err, FLOOR))
l3 = p5[~p5.rung.str.match(r"star_L\d+")].reset_index(drop=True)

lines = []
for lab, drop in (("all L3", []), ("drop cz52", ["star_cz52"]),
                  ("drop cz24+cz52", ["star_cz24", "star_cz52"])):
    s = l3[~l3.rung.isin(drop)].reset_index(drop=True)
    cl = s.eval_index.values
    ucl = np.unique(cl)
    signs = np.array(list(itertools.product([-1, 1], repeat=len(ucl))))
    for y in ("ler", "lec"):
        f = f"{y} ~ cz10 + dur_us + C(eval_index)"
        m = smf.ols(f, data=s).fit(cov_type="cluster", cov_kwds={"groups": cl}, use_t=True)
        mz = smf.ols(f, data=s).fit(cov_type="cluster", cov_kwds={"groups": cl})
        ci = m.conf_int()
        for term in ("cz10", "dur_us"):
            fr = f.replace(f" {term} +", "").replace(f"+ {term} ", "")
            r0 = smf.ols(fr, data=s).fit()
            tobs = abs(m.tvalues[term])
            idx = np.searchsorted(ucl, cl)
            cnt = 0
            for sg in signs:
                ystar = r0.fittedvalues.values + r0.resid.values * sg[idx]
                mb = smf.ols(f, data=s.assign(**{y: ystar})).fit(
                    cov_type="cluster", cov_kwds={"groups": cl})
                cnt += abs(mb.tvalues[term]) >= tobs - 1e-12
            p_wb = cnt / len(signs)
            lines.append(
                f"{lab:15s} {'raw' if y == 'ler' else 'cdr':3s} {term:6s} n={int(m.nobs):2d} "
                f"factor {np.exp(m.params[term]):.3f} CI_t7 [{np.exp(ci.loc[term, 0]):.2f}, "
                f"{np.exp(ci.loc[term, 1]):.2f}] p_normal {mz.pvalues[term]:.2g} "
                f"p_t7 {m.pvalues[term]:.2g} p_wildboot {p_wb:.3f}")
# sensitivity: drop the two points with |ideal| < 0.1 (error there is an offset, not a contraction)
s = l3[l3.ideal.abs() >= 0.1]
m = smf.ols("ler ~ cz10 + dur_us + C(eval_index)", data=s).fit(
    cov_type="cluster", cov_kwds={"groups": s.eval_index}, use_t=True)
for term in ("cz10", "dur_us"):
    lines.append(f"|ideal|>=0.1    raw {term:6s} n={int(m.nobs):2d} G={s.eval_index.nunique()} "
                 f"factor {np.exp(m.params[term]):.3f} p_t(G-1) {m.pvalues[term]:.2g}")
out = "\n".join(lines)
(HERE / "p5_robust_numbers.txt").write_text(out + "\n")
print(out)
