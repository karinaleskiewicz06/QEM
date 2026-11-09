"""Q6: duration / PRX-mismatch-aware CDR on night A.

Training circuits are shorter than the target (fewer PRX survive Clifford snapping + merging):
star target 20 PRX / 1.12 us vs training ~10 PRX / ~0.92 us (ASAP duration_s).
Variants (all OLS, 20 training circuits, 6 repeats averaged):
  D0  plain CDR
  D1  y ~ x + dd + 1, predict at dd = 0          (dd = d_i - d_target, us)
  D2  y ~ x + x:dd + 1, predict at dd = 0        (slope depends on duration)
  D3  y ~ x + dprx + 1 (PRX count instead of duration)
  D4  kernel-weighted CDR, w_i = exp(-|dprx_i| / h), h = median |dprx|
  D5  attenuation transfer: x_i -> x_i * exp(-gamma * (d_t - d_i)), gamma estimated on P5 from
      the CDR slopes of the idle-insertion rungs (star, idle24/36/52; duration-only change):
      log a = gamma * dur + point FE.  (a grows as the signal shrinks, so gamma_signal = slope of log a)
  D6  keep only the half of training circuits closest to the target in PRX count (10 of 20)
"""
from __future__ import annotations

import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import *  # noqa
import pandas as pd
import statsmodels.formula.api as smf


def gamma_from_p5(lines):
    g = cdr_groups(load("w01P5"))
    rows = []
    for rung in ("star", "star_idle24", "star_idle36", "star_idle52"):
        for e in EVAL:
            d = g[(rung, "off_copies", "near_target", e)]
            ks = sorted(d["train"])
            xs = [np.mean([r.expval for r in d["train"][i]]) for i in ks]
            ys = [d["train_ideal"][i] for i in ks]
            a, b, _ = ols(xs, ys)
            m = d["target"][0].meta
            dur = m.get("duration_sched_s") or m.get("duration_s")
            rows.append(dict(rung=rung, e=e, a=a, b=b, dur=dur * 1e6, la=np.log(a)))
    df = pd.DataFrame(rows)
    m = smf.ols("la ~ dur + C(e)", data=df).fit(cov_type="cluster", cov_kwds={"groups": df.e})
    gam = float(m.params["dur"])
    lines.append(f"P5 idle family: log(CDR slope) per us = {gam:.3f} (SE {m.bse['dur']:.3f}) -> "
                 f"signal attenuation x{np.exp(-gam):.3f} per us; mean slopes by rung: "
                 + ", ".join(f"{r} {s.a.mean():.3f}@{s.dur.mean():.2f}us" for r, s in df.groupby('rung', sort=False)))
    return gam


def fits(d, gam):
    ks = sorted(d["train"])
    x = np.array([np.mean([r.expval for r in d["train"][i]]) for i in ks])
    y = np.array([d["train_ideal"][i] for i in ks])
    dur = np.array([d["train"][i][0].meta["duration_s"] for i in ks]) * 1e6
    prx = np.array([np.mean([r.meta["n_prx"] for r in d["train"][i]]) for i in ks])
    tm = [r.meta for r in d["target"]]
    dt = np.mean([m["duration_s"] for m in tm]) * 1e6
    pt = np.mean([m["n_prx"] for m in tm])
    xt = np.mean([r.expval for r in d["target"]])
    dd, dp = dur - dt, prx - pt
    one = np.ones_like(x)
    out = {}
    a, b, _ = ols(x, y)
    out["D0 plain"] = a * xt + b
    c, *_ = np.linalg.lstsq(np.c_[x, dd, one], y, rcond=None)
    out["D1 +dur"] = c[0] * xt + c[2]
    c, *_ = np.linalg.lstsq(np.c_[x, x * dd, one], y, rcond=None)
    out["D2 x:dur"] = c[0] * xt + c[2]
    c, *_ = np.linalg.lstsq(np.c_[x, dp, one], y, rcond=None)
    out["D3 +prx"] = c[0] * xt + c[2]
    h = max(np.median(np.abs(dp)), 1e-9)
    w = np.sqrt(np.exp(-np.abs(dp) / h))
    c, *_ = np.linalg.lstsq(np.c_[x, one] * w[:, None], y * w, rcond=None)
    out["D4 kernel"] = c[0] * xt + c[1]
    xs = x * np.exp(-gam * (dt - dur))
    a, b, _ = ols(xs, y)
    out["D5 atten-transfer"] = a * xt + b
    idx = np.argsort(np.abs(dp))[: len(x) // 2]
    a, b, _ = ols(x[idx], y[idx])
    out["D6 closest-half"] = a * xt + b
    return out, float(np.mean(dd)), float(np.mean(dp))


def main():
    lines = []
    gam = gamma_from_p5(lines)
    g = cdr_groups(load("w01A"))
    for rung in ("star", "circular"):
        for arm in ("off_copies", "twirl_native", "spread"):
            res = defaultdict(list)
            dds, dps = [], []
            for e in EVAL:
                d = g[(rung, arm, "near_target", e)]
                o, dd, dp = fits(d, gam)
                dds.append(dd); dps.append(dp)
                for k, v in o.items():
                    res[k].append(abs(v - d["ideal"]))
            base = np.array(res["D0 plain"])
            lines.append(f"\n## {rung} {arm}: mean training-target duration gap {np.mean(dds):+.3f} us, PRX gap {np.mean(dps):+.1f}")
            for k, v in res.items():
                v = np.array(v)
                s = f"  {k:18s} {v.mean():.4f}"
                if k != "D0 plain":
                    s += "  | " + paired_report(v, base, "var", "plain")
                lines.append(s)
    txt = "\n".join(lines)
    (OUT / "q6_duration.txt").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
