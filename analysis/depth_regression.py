"""P5: what drives the error -- CZ count, PRX count or duration?

Reads ``cdr.csv`` of one or more windows (``campaign/odra_window.py``) and regresses, per
evaluation point and rung,

    log err  ~  n_cz + n_prx + duration  +  point fixed effects

with standard errors clustered by evaluation point. The P5 night makes the three
separable: identity insertion adds CZ at fixed PRX (``star_cz*``), idle insertion adds
duration at fixed gate counts (``star_idle*``), and the L6/L9/L13 classifiers add PRX on
top. Point fixed effects absorb that the same input has a different signal size; the L
rungs are different classifiers, so their ideal values differ too, which is why the
regression is also reported without them (``l3_only``).

Units: per 10 CZ, per 10 PRX, per microsecond. Outcomes: raw error and the OLS CDR error
of the untwirled arm, both on the log scale (a coefficient c means a factor exp(c)).

    python -m analysis.depth_regression runs/odra_campaign/w01P5 [more windows]
"""

from __future__ import annotations

import argparse
import pathlib

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ARM = ("off_copies", "near_target")
OUT = pathlib.Path("results/depth_regression.csv")
FLOOR = 1e-4            # log of an error that is exactly 0 is undefined


def load(run_dirs) -> pd.DataFrame:
    frames = []
    for d in run_dirs:
        df = pd.read_csv(pathlib.Path(d) / "cdr.csv")
        df["window"] = pathlib.Path(d).name
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = df[(df.arm == ARM[0]) & (df.train_set == ARM[1]) & (df.fit == "ols")].copy()
    if df.empty:
        raise SystemExit(f"no {ARM[0]}:{ARM[1]} rows in {run_dirs}")
    df["cz10"] = df.n_cz / 10.0
    df["prx10"] = df.n_prx / 10.0
    df["dur_us"] = df.duration_sched_s * 1e6
    df["log_err_raw"] = np.log(np.maximum(df.err_raw, FLOOR))
    df["log_err_cdr"] = np.log(np.maximum(df.err, FLOOR))
    return df


def fit(df: pd.DataFrame, outcome: str, label: str) -> list[dict]:
    """OLS with point fixed effects, clustered SE by point; one row per regressor."""
    fe = " + C(eval_index)" if df.eval_index.nunique() > 1 else ""
    win = " + C(window)" if df.window.nunique() > 1 else ""
    regs = [r for r in ("cz10", "prx10", "dur_us") if df[r].nunique() > 1]
    model = smf.ols(f"{outcome} ~ {' + '.join(regs)}{fe}{win}", data=df).fit(
        cov_type="cluster", cov_kwds={"groups": df.eval_index})
    ci = model.conf_int()
    return [{"sample": label, "outcome": outcome, "term": t, "coef": model.params[t],
             "ci_lo": ci.loc[t, 0], "ci_hi": ci.loc[t, 1], "p": model.pvalues[t],
             "factor": float(np.exp(model.params[t])), "n": int(model.nobs),
             "n_points": int(df.eval_index.nunique()), "n_rungs": int(df.rung.nunique())}
            for t in regs]


def run(run_dirs, out: pathlib.Path = OUT) -> pd.DataFrame:
    df = load(run_dirs)
    rows = []
    for label, sub in (("all", df), ("l3_only", df[~df.rung.str.match(r"star_L\d+")])):
        if sub.rung.nunique() < 3:
            continue
        for outcome in ("log_err_raw", "log_err_cdr"):
            rows += fit(sub, outcome, label)
    res = pd.DataFrame(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out, index=False)
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    res = run(a.run_dirs, pathlib.Path(a.out))
    pd.set_option("display.width", 140)
    print(res.round(4).to_string(index=False))
    print(f"\nwrote {a.out}  (factor = multiplicative change of the error per unit)")


if __name__ == "__main__":
    main()
