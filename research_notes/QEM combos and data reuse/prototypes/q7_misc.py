"""Q7: other quick offline checks on night A.

a) ZNE extrapolation variants on the stored genuine E(1), E(3), E(5) (with/without REM):
   Richardson{1,3,5}, Richardson{1,3}, linear LSQ{1,3,5}, exponential with a *measured* floor
   f (garbage lambda=5 of the same point, or the point-independent mean of garbage lambda=5):
   E(l) = f + (E1 - f) r^(l-1), r from LSQ on log((E_l - f)/(E1 - f)); E0 = f + (E1 - f)/r.
b) SNR of the largest scale measured against the floor instead of zero, and whether either
   SNR predicts "ZNE beats raw" per point.
c) Drift: the same target circuit measured in the ZNE block (lambda=1) and in the CDR
   off_copies block (hours apart): difference vs shot noise.
d) Twirl at M -> infinity: unbiased bias^2 estimate err^2 - a^2 var_frames / M per point.
"""
from __future__ import annotations

import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import *  # noqa
from q2_readout import readout_params, corr
from scipy.stats import spearmanr


def exp_floor(lam, E, f):
    u = (np.asarray(E) - f) / (E[0] - f)
    if np.any(u[1:] <= 0) or E[0] == f:
        return np.nan
    lr = np.log(u[1:]) / (np.asarray(lam[1:]) - 1)   # log r per extra scale step
    r = np.exp(np.mean(lr))
    return f + (E[0] - f) / r


def main():
    recs = load("w01A")
    z = zne_groups(recs)
    g = cdr_groups(recs)
    e01, e10 = readout_params()
    lam = np.array([1, 3, 5])
    lines = []
    for rung in ("star", "circular"):
        ideal = np.array([z[(rung, e)][("genuine", 1)].meta["ideal"] for e in EVAL])
        for rem in (False, True):
            get = (lambda r: corr(r, e01, e10)) if rem else (lambda r: r.expval)
            E = np.array([[get(z[(rung, e)][("genuine", s)]) for s in lam] for e in EVAL])
            G5 = np.array([get(z[(rung, e)][("garbage", 5)]) for e in EVAL])
            est = {
                "raw λ1": E[:, 0],
                "Rich{1,3,5}": E @ RICH[(1, 3, 5)],
                "Rich{1,3}": E[:, :2] @ RICH[(1, 3)],
                "lin LSQ{1,3,5}": np.array([np.polyval(np.polyfit(lam, row, 1), 0) for row in E]),
                "exp, floor=garbage λ5 (pt)": np.array([exp_floor(lam, row, f) for row, f in zip(E, G5)]),
                "exp, floor=mean garbage λ5": np.array([exp_floor(lam, row, G5.mean()) for row in E]),
            }
            lines.append(f"\n## {rung} {'REM' if rem else 'no REM'}  (garbage λ5 floor mean {G5.mean():+.4f}, sd {G5.std():.4f})")
            base = np.abs(est["raw λ1"] - ideal)
            for k, v in est.items():
                ok = np.isfinite(v)
                e = np.abs(v - ideal)
                s = f"  {k:28s} mean err {np.nanmean(e):.4f} (finite {ok.sum()}/8)"
                if k != "raw λ1" and ok.all():
                    s += " | vs raw: " + paired_report(e, base, "est", "raw")
                lines.append(s)
        # b) SNR
        recs5 = [z[(rung, e)][("genuine", 5)] for e in EVAL]
        se5 = np.array([np.sqrt(r.shot_var() / r.shots) for r in recs5])
        E5 = np.array([r.expval for r in recs5])
        G5 = np.array([z[(rung, e)][("garbage", 5)].expval for e in EVAL])
        E = np.array([[z[(rung, e)][("genuine", s)].expval for s in lam] for e in EVAL])
        gain = np.abs(E[:, 0] - ideal) - np.abs(E @ RICH[(1, 3, 5)] - ideal)   # >0 = ZNE helps
        snr0 = np.abs(E5) / se5
        snrf = np.abs(E5 - G5) / np.sqrt(se5 ** 2 + np.array([z[(rung, e)][("garbage", 5)].shot_var() / 8192 for e in EVAL]))
        snrf_mean = np.abs(E5 - G5.mean()) / se5
        lines.append(f"  SNR(λ5) vs 0: median {np.median(snr0):.1f}; vs point floor: median {np.median(snrf):.1f}; "
                     f"vs mean floor: median {np.median(snrf_mean):.1f}")
        lines.append(f"  E5-floor(mean) per point: {np.round(E5 - G5.mean(), 3)}; ideal {np.round(ideal, 3)}")
        lines.append(f"  ZNE gain (raw err - ZNE err) per point: {np.round(gain, 3)}")
        globals().setdefault("_snr_pool", []).append((snr0, snrf, snrf_mean, gain))
        # c) drift: ZNE-block lambda1 vs CDR off_copies target (same circuit)
        offk = [(rung, "off_copies", "near_target", e) for e in EVAL]
        t6 = np.array([np.mean([r.expval for r in g[k]["target"]]) for k in offk])
        se = np.array([np.sqrt(z[(rung, e)][("genuine", 1)].shot_var() / 8192 +
                               np.mean([r.shot_var() for r in g[k]["target"]]) / (6 * 8192)) for e, k in zip(EVAL, offk)])
        dz = (E[:, 0] - t6) / se
        lines.append(f"  drift check: ZNE-block λ1 minus CDR-block target, in SE units: {np.round(dz, 1)}; "
                     f"chi2/df {np.mean(dz**2):.1f}")
        # d) twirl at M -> inf
        for arm in ("off_copies", "twirl_native"):
            b2, e2 = [], []
            for e in EVAL:
                d = g[(rung, arm, "near_target", e)]
                ks = sorted(d["train"])
                xs = [np.mean([r.expval for r in d["train"][i]]) for i in ks]
                ys = [d["train_ideal"][i] for i in ks]
                a, b, _ = ols(xs, ys)
                v = np.array([r.expval for r in d["target"]])
                err2 = (a * v.mean() + b - d["ideal"]) ** 2
                e2.append(err2)
                b2.append(err2 - a ** 2 * np.var(v, ddof=1) / len(v))
            lines.append(f"  {arm:12s} RMS err (M=6) {np.sqrt(np.mean(e2)):.4f}; est. RMS bias at M->inf "
                         f"{np.sqrt(max(np.mean(b2), 0)):.4f} (mean b2 {np.mean(b2):+.2e})")
    s0, sf, sm, gn = map(np.concatenate, zip(*globals()["_snr_pool"]))
    lines.append(f"\nSNR as predictor of ZNE gain over 16 points (Spearman): vs0 rho={spearmanr(s0, gn)[0]:+.2f} "
                 f"(p={spearmanr(s0, gn)[1]:.2f}); vs point floor rho={spearmanr(sf, gn)[0]:+.2f} (p={spearmanr(sf, gn)[1]:.2f}); "
                 f"vs mean floor rho={spearmanr(sm, gn)[0]:+.2f} (p={spearmanr(sm, gn)[1]:.2f})")
    txt = "\n".join(lines)
    (OUT / "q7_misc.txt").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
