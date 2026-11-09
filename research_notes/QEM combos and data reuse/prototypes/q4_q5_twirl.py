"""Q4: twirl x n_CZ interaction on night A.  Q5: frame-to-frame variance vs copy-to-copy variance.

Q4 model (per outcome):  log err ~ twirl + twirl:circular + C(rung:point)   (32 rows: 2 arms x 2 rungs x 8 pts)
The rung main effect is absorbed by the 16 point fixed effects. Equivalent to paired
differences d = log err_twirl - log err_off; interaction = mean d(circular) - mean d(star).
CIs: classical t (df 14), and a point bootstrap (resample points within rung, B=20000).

Q5: per target / training circuit, the empirical variance across its M=6 repeats is compared
with the multinomial shot variance sigma^2/S; excess = frame (or drift) variance.
"""
from __future__ import annotations

import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import *  # noqa
import pandas as pd
import statsmodels.formula.api as smf

FLOOR = 1e-4


def q4(lines):
    df = pd.read_csv(REPO / "runs/odra_campaign/w01A/cdr.csv")
    nt = df[df.train_set == "near_target"]
    rng = np.random.default_rng(11)
    for fit in ("ols", "eiv"):
        for twarm in ("twirl_native", "spread"):
            for outcome in ("err", "err_raw"):
                sub = nt[(nt.fit == fit) & nt.arm.isin(["off_copies", twarm])].copy()
                sub["twirl"] = (sub.arm == twarm).astype(int)
                sub["circ"] = (sub.rung == "circular").astype(int)
                sub["y"] = np.log(np.maximum(sub[outcome], FLOOR))
                m = smf.ols("y ~ twirl + twirl:circ + C(rung):C(eval_index)", data=sub).fit()
                ci = m.conf_int()
                piv = sub.pivot_table(index=["rung", "eval_index"], columns="twirl", values="y")
                d = (piv[1] - piv[0])
                ds, dc = d.loc["star"].values, d.loc["circular"].values
                bs = []
                for _ in range(20000):
                    bs.append(rng.choice(dc, 8).mean() - rng.choice(ds, 8).mean())
                lo, hi = np.quantile(bs, [0.025, 0.975])
                bst = [rng.choice(ds, 8).mean() for _ in range(20000)]
                bci = [rng.choice(dc, 8).mean() for _ in range(20000)]
                lines.append(
                    f"[{fit} {outcome}] twirl={twarm}: twirl effect @12CZ x{np.exp(m.params['twirl']):.2f} "
                    f"[t-CI {np.exp(ci.loc['twirl',0]):.2f},{np.exp(ci.loc['twirl',1]):.2f}; boot {np.exp(np.quantile(bst,.025)):.2f},{np.exp(np.quantile(bst,.975)):.2f}]; "
                    f"@39CZ x{np.exp(dc.mean()):.2f} [boot {np.exp(np.quantile(bci,.025)):.2f},{np.exp(np.quantile(bci,.975)):.2f}]; "
                    f"interaction (ratio of ratios) x{np.exp(m.params['twirl:circ']):.2f} "
                    f"[t-CI {np.exp(ci.loc['twirl:circ',0]):.2f},{np.exp(ci.loc['twirl:circ',1]):.2f}; boot {np.exp(lo):.2f},{np.exp(hi):.2f}], "
                    f"p_t={m.pvalues['twirl:circ']:.3f}")
    # r^2 of CDR fits
    lines.append("\nCDR fit r^2 (OLS), mean [min,max] over 8 points:")
    for rung in ("star", "circular"):
        for arm, ts in (("off_copies", "near_target"), ("twirl_native", "near_target"), ("spread", "near_target"),
                        ("twirl_logical", "shared_random"), ("twirl_native", "shared_random")):
            s = df[(df.rung == rung) & (df.arm == arm) & (df.train_set == ts) & (df.fit == "ols")]
            se = df[(df.rung == rung) & (df.arm == arm) & (df.train_set == ts) & (df.fit == "eiv")]
            lines.append(f"  {rung:8s} {arm}:{ts:13s} r2 {s.r2.mean():.3f} [{s.r2.min():.3f},{s.r2.max():.3f}]  "
                         f"slope a OLS {s.a.mean():.2f}, EIV {se.a.mean():.2f}")
    from scipy.stats import wilcoxon
    for rung in ("star", "circular"):
        a = df[(df.rung == rung) & (df.arm == "off_copies") & (df.fit == "ols")].sort_values("eval_index").r2.values
        b = df[(df.rung == rung) & (df.arm == "twirl_native") & (df.train_set == "near_target") & (df.fit == "ols")].sort_values("eval_index").r2.values
        lines.append(f"  {rung}: r2 twirl_native - off_copies = {np.mean(b-a):+.3f} (twirl higher {int((b>a).sum())}/8, Wilcoxon p={wilcoxon(b,a).pvalue:.3f})")


def q5(lines):
    recs = load("w01A")
    g = cdr_groups(recs)
    rows = []
    for rung in ("star", "circular"):
        for arm in ("off_copies", "twirl_native"):
            for e in EVAL:
                d = g[(rung, arm, "near_target", e)]
                t = d["target"]
                v = np.array([r.expval for r in t])
                shot = np.mean([r.shot_var() / r.shots for r in t])
                ks = sorted(d["train"])
                xs = np.array([np.mean([r.expval for r in d["train"][i]]) for i in ks])
                tr_var = np.array([np.var([r.expval for r in d["train"][i]], ddof=1) for i in ks])
                tr_shot = np.array([np.mean([r.shot_var() / r.shots for r in d["train"][i]]) for i in ks])
                ys = np.array([d["train_ideal"][i] for i in ks])
                a, b, _ = ols(xs, ys)
                err = abs(a * v.mean() + b - d["ideal"])
                var_x = np.var(xs, ddof=1)
                sig2_mean = tr_var.mean() / 6
                rows.append(dict(rung=rung, arm=arm, e=e, tgt_var=np.var(v, ddof=1), tgt_shot=shot,
                                 tr_var=tr_var.mean(), tr_shot=tr_shot.mean(), a=a, err=err,
                                 se_contrib=abs(a) * np.sqrt(np.var(v, ddof=1) / 6),
                                 dilution=(var_x - sig2_mean) / var_x, var_x=var_x))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "q5_frame_variance.csv", index=False)
    lines.append("\nQ5 frame vs copy variance (means over 8 points):")
    for (rung, arm), s in df.groupby(["rung", "arm"], sort=False):
        lines.append(
            f"  {rung:8s} {arm:12s} target var/shot-var {np.mean(s.tgt_var/s.tgt_shot):6.1f} "
            f"(target SD across M {np.sqrt(s.tgt_var).mean():.4f} vs shot SD {np.sqrt(s.tgt_shot).mean():.4f}); "
            f"training var/shot-var {np.mean(s.tr_var/s.tr_shot):5.1f}; "
            f"|a|*SE(target mean) {s.se_contrib.mean():.4f} vs CDR err {s.err.mean():.4f} "
            f"(share of err^2 {np.mean(s.se_contrib**2)/np.mean(s.err**2):.3f}); "
            f"regression dilution factor {s.dilution.mean():.4f}")


def main():
    lines = []
    q4(lines)
    q5(lines)
    txt = "\n".join(lines)
    (OUT / "q4_q5_twirl.txt").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
