"""P5: wrażliwość H7 na bloki dotknięte zmianą kalibracji (star_cz52 w trakcie, star_cz24 po)."""
import numpy as np, pandas as pd, statsmodels.formula.api as smf, warnings
warnings.filterwarnings("ignore")
p5 = pd.read_csv("runs/odra_campaign/w01P5/cdr.csv")
p5 = p5[(p5.fit == "ols") & (p5.arm == "off_copies")].copy()
p5["cz10"], p5["dur_us"] = p5.n_cz / 10, p5.duration_sched_s * 1e6
p5["ler"], p5["lec"] = np.log(np.maximum(p5.err_raw, 1e-4)), np.log(np.maximum(p5.err, 1e-4))
l3 = p5[~p5.rung.str.match(r"star_L\d+")]
for lab, drop in (("l3_only", []), ("bez cz24", ["star_cz24"]), ("bez cz52", ["star_cz52"]),
                  ("bez cz24 i cz52 (tylko stara kalibracja)", ["star_cz24", "star_cz52"])):
    s = l3[~l3.rung.isin(drop)]
    for y in ("ler", "lec"):
        m = smf.ols(f"{y} ~ cz10 + dur_us + C(eval_index)", data=s).fit(
            cov_type="cluster", cov_kwds={"groups": s.eval_index}, use_t=True)
        print(f"{lab:42s} {y}: cz10 x{np.exp(m.params.cz10):.3f} (p={m.pvalues.cz10:.2g})  "
              f"dur x{np.exp(m.params.dur_us):.3f} (p={m.pvalues.dur_us:.2g})  n={int(m.nobs)}")
