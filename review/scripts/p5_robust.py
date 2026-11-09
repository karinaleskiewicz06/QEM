"""P5: szkielety, oraz odporność wnioskowania z 8 klastrami (t(G-1), wild cluster bootstrap)."""
from __future__ import annotations

import collections
import json
import pathlib

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

T = pathlib.Path(__file__).resolve().parent / "tmp"
REPO = pathlib.Path(__file__).resolve().parents[2]
recs = [json.loads(l) for l in open(REPO / "runs/odra_campaign/w01P5/counts.jsonl")]
tg = {}
for r in recs:
    if r["role"] == "target":
        tg.setdefault((r["rung"], r["eval_index"]), set()).add(tuple(map(tuple, r["cz_skeleton"])))
c = collections.Counter()
for r in recs:
    me = tuple(map(tuple, r["cz_skeleton"])) in tg[(r["rung"], r["eval_index"])]
    c[(r["role"], r["skeleton_matches_target"], me)] += 1
print("P5 szkielety (rola, pole, przeliczone):", dict(c))
print("P5 kalibracje:", collections.Counter(r["calibration_set_id"] for r in recs))

p5 = pd.read_csv(REPO / "runs/odra_campaign/w01P5/cdr.csv")
p5 = p5[(p5.fit == "ols") & (p5.arm == "off_copies")].copy()
p5["cz10"], p5["dur_us"] = p5.n_cz / 10, p5.duration_sched_s * 1e6
p5["ler"], p5["lec"] = np.log(np.maximum(p5.err_raw, 1e-4)), np.log(np.maximum(p5.err, 1e-4))
l3 = p5[~p5.rung.str.match(r"star_L\d+")].reset_index(drop=True)
rng = np.random.default_rng(7)
for y in ("ler", "lec"):
    f = f"{y} ~ cz10 + dur_us + C(eval_index)"
    m = smf.ols(f, data=l3).fit(cov_type="cluster", cov_kwds={"groups": l3.eval_index}, use_t=True)
    m0 = smf.ols(f, data=l3).fit()
    out = {}
    for term in ("cz10", "dur_us"):
        # wild cluster bootstrap (Rademacher) z restrykcją H0: coef=0
        fr = f.replace(f" {term} +", "").replace(f"+ {term} ", "")
        r0 = smf.ols(fr, data=l3).fit()
        tobs = m.tvalues[term]
        cnt, B = 0, 999
        cl = l3.eval_index.values
        ucl = np.unique(cl)
        for _ in range(B):
            w = dict(zip(ucl, rng.choice([-1, 1], len(ucl))))
            ystar = r0.fittedvalues + r0.resid * np.array([w[g] for g in cl])
            d = l3.assign(**{y: ystar})
            mb = smf.ols(f, data=d).fit(cov_type="cluster", cov_kwds={"groups": d.eval_index})
            cnt += abs(mb.tvalues[term]) >= abs(tobs)
        out[term] = (np.exp(m.params[term]), m.pvalues[term], m0.pvalues[term], (cnt + 1) / (B + 1))
    for term, (fac, pt, pols, pwb) in out.items():
        print(f"{y} {term}: factor {fac:.3f}; p klaster t(7) = {pt:.2g}; p OLS iid = {pols:.2g}; "
              f"p wild-cluster-bootstrap = {pwb:.3f}")
