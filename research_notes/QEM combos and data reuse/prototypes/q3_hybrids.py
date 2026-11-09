"""Q3: CDR x ZNE hybrids on existing data.

Night A (targets folded, training not):
  H1  CDR map applied to every folded target then Richardson  ==  a * ZNE + b   (Richardson is
      linear with sum c_k = 1, so the two orders coincide exactly)
  H2  simple average (CDR + ZNE) / 2
  H3  inverse-variance average (shot-noise variances; CDR variance by resampling repeats)
  H4  leave-one-point-out stacking: ideal ~ alpha*CDR + beta*ZNE + gamma fitted on the 7 other
      points of the rung (uses ideal values of other eval points = benchmark-only / oracle-ish)
  H5  ZNE on the CDR-corrected ladder with the CDR slope taken as a *prior on attenuation*:
      CDR estimate with intercept from CDR and slope from ZNE: (E1 - b_cdr) ... (skipped: ill-posed)
Night P5 (true variable-noise CDR possible): rungs star, star_cz24, star_cz36, star_cz52 carry the
same targets AND the same training circuits with 0/6/12/20 inserted CZ pairs (noise scale
lambda = n_cz/12 = 1, 2, 3, 4.33). Same for idle insertion (star_idle24/36/52, matched duration).
  vnCDR (Lowe et al. 2021): ideal ~ sum_k w_k x(lambda_k) [+ b] fitted on training, applied to target.
  Also ZNE-by-insertion on the targets (linear / quadratic in lambda) for comparison.
"""
from __future__ import annotations

import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import *  # noqa


def cdr_point(d):
    ks = sorted(d["train"])
    xs = [np.mean([r.expval for r in d["train"][i]]) for i in ks]
    ys = [d["train_ideal"][i] for i in ks]
    a, b, r2 = ols(xs, ys)
    t = np.mean([r.expval for r in d["target"]])
    return a * t + b, a, b


def cdr_var(d, rng, B=300):
    """Shot-noise variance of the CDR estimate: resample shots (multinomial) of every circuit."""
    ks = sorted(d["train"])
    ht = hw_hist(d["target"])
    hs = {i: hw_hist(d["train"][i]) for i in ks}
    ys = [d["train_ideal"][i] for i in ks]
    est = []
    for _ in range(B):
        xs = [HW_VAL @ rng.multinomial(hs[i].sum(), hs[i] / hs[i].sum()) / hs[i].sum() for i in ks]
        a, b, _ = ols(xs, ys)
        t = HW_VAL @ rng.multinomial(ht.sum(), ht / ht.sum()) / ht.sum()
        est.append(a * t + b)
    return float(np.var(est))


def night_a(lines):
    recs = load("w01A")
    g = cdr_groups(recs)
    z = zne_groups(recs)
    rng = np.random.default_rng(3)
    for rung in ("star", "circular"):
        for arm in ("off_copies", "twirl_native"):
            keys = [(rung, arm, "near_target", e) for e in EVAL]
            ideal = np.array([g[k]["ideal"] for k in keys])
            cd = np.array([cdr_point(g[k]) for k in keys])
            cdr, a, b = cd[:, 0], cd[:, 1], cd[:, 2]
            Erec = [[z[(rung, e)][("genuine", s)] for s in (1, 3, 5)] for e in EVAL]
            E = np.array([[r.expval for r in row] for row in Erec])
            zne = E @ RICH[(1, 3, 5)]
            vz = np.array([sum(c ** 2 * r.shot_var() / r.shots for c, r in zip(RICH[(1, 3, 5)], row)) for row in Erec])
            vc = np.array([cdr_var(g[k], rng) for k in keys])
            h1 = a * zne + b
            h2 = (cdr + zne) / 2
            w = (1 / vc) / (1 / vc + 1 / vz)
            h3 = w * cdr + (1 - w) * zne
            h4 = np.empty(8)
            for i in range(8):
                m = np.arange(8) != i
                X = np.c_[cdr[m], zne[m], np.ones(7)]
                coef, *_ = np.linalg.lstsq(X, ideal[m], rcond=None)
                h4[i] = np.array([cdr[i], zne[i], 1]) @ coef
            # H6: CDR applied to E1 measured in the ZNE block (same circuit, other time) = drift check
            h6 = a * E[:, 0] + b
            err = {n: np.abs(v - ideal) for n, v in
                   dict(CDR=cdr, ZNE=zne, H1_aZNEb=h1, H2_avg=h2, H3_ivw=h3, H4_LOOstack=h4,
                        CDR_on_ZNElam1=h6).items()}
            lines.append(f"\n## night A {rung} arm={arm} (CDR SE~{np.sqrt(vc).mean():.4f}, ZNE SE~{np.sqrt(vz).mean():.4f}; "
                         f"mean IVW weight on CDR {w.mean():.2f})")
            for n, e in err.items():
                lines.append(f"  {n:16s} mean err {e.mean():.4f}")
            for n in ("H1_aZNEb", "H2_avg", "H3_ivw", "H4_LOOstack"):
                lines.append(f"  {n} vs CDR: " + paired_report(err[n], err["CDR"], n, "CDR"))
                lines.append(f"  {n} vs ZNE: " + paired_report(err[n], err["ZNE"], n, "ZNE"))
            lines.append(f"  CDR slope a mean {a.mean():.2f}; ZNE implied gain ZNE/E1 (median) {np.median(zne / E[:, 0]):.2f}")


def p5_vncdr(lines):
    recs = load("w01P5")
    g = cdr_groups(recs)
    fam = {"cz": [("star", 1.0), ("star_cz24", 2.0), ("star_cz36", 3.0), ("star_cz52", 52 / 12)],
           "idle": [("star", 1.0), ("star_idle24", 2.0), ("star_idle36", 3.0), ("star_idle52", 52 / 12)]}
    rng = np.random.default_rng(5)
    for fname, rungs in fam.items():
        res = defaultdict(list)
        for e in EVAL:
            ds = [g[(r, "off_copies", "near_target", e)] for r, _ in rungs]
            lam = np.array([l for _, l in rungs])
            ks = sorted(ds[0]["train"])
            for d in ds[1:]:
                assert sorted(d["train"]) == ks
                assert all(abs(d["train_ideal"][i] - ds[0]["train_ideal"][i]) < 1e-12 for i in ks), "training sets differ"
                assert abs(d["ideal"] - ds[0]["ideal"]) < 1e-12
            y = np.array([ds[0]["train_ideal"][i] for i in ks])
            ideal = ds[0]["ideal"]
            X = np.array([[np.mean([r.expval for r in d["train"][i]]) for d in ds] for i in ks])   # 20 x L
            t = np.array([np.mean([r.expval for r in d["target"]]) for d in ds])                   # L
            res["raw"].append(abs(t[0] - ideal))
            a, b, _ = ols(X[:, 0], y)
            res["CDR(λ=1)"].append(abs(a * t[0] + b - ideal))
            for L in (2, 3, 4):
                A = np.c_[X[:, :L], np.ones(len(y))]
                w, *_ = np.linalg.lstsq(A, y, rcond=None)
                res[f"vnCDR+b L={L}"].append(abs(np.r_[t[:L], 1] @ w - ideal))
                w2, *_ = np.linalg.lstsq(X[:, :L], y, rcond=None)
                res[f"vnCDR(no b) L={L}"].append(abs(t[:L] @ w2 - ideal))
            # ZNE by insertion on the targets alone
            for deg, L in ((1, 2), (1, 4), (2, 3), (2, 4)):
                c = np.polyfit(lam[:L], t[:L], deg)
                res[f"ZNE-ins deg{deg} L={L}"].append(abs(np.polyval(c, 0) - ideal))
            # CDR then ZNE: CDR-correct each lambda with its own map, then extrapolate linearly
            cl = []
            for j in range(4):
                aj, bj, _ = ols(X[:, j], y)
                cl.append(aj * t[j] + bj)
            res["CDR-per-λ then lin-ZNE L=4"].append(abs(np.polyval(np.polyfit(lam, cl, 1), 0) - ideal))
            res["mean of per-λ CDR L=4"].append(abs(np.mean(cl) - ideal))
            # equal-cost vnCDR: each level at 1/L of the shots (subsample pooled repeats), L=2 and 4
            HT = {(j, i): hw_hist(ds[j]["train"][i]) for j in range(4) for i in ks}
            HG = [hw_hist(ds[j]["target"]) for j in range(4)]
            for L in (2, 4):
                ee = []
                for _ in range(200):
                    Xs = np.array([[sub_hist(HT[(j, i)], 49152 // L, rng) for j in range(L)] for i in ks])
                    ts = np.array([sub_hist(HG[j], 49152 // L, rng) for j in range(L)])
                    w, *_ = np.linalg.lstsq(np.c_[Xs, np.ones(len(y))], y, rcond=None)
                    ee.append(abs(np.r_[ts, 1] @ w - ideal))
                res[f"vnCDR+b L={L} @equal cost"].append(np.mean(ee))
        lines.append(f"\n## P5 variable-noise CDR, family '{fname}' (scales {[round(l,2) for _, l in rungs]})")
        base = np.array(res["CDR(λ=1)"])
        for n, v in res.items():
            v = np.array(v)
            s = f"  {n:28s} mean err {v.mean():.4f}"
            if n != "CDR(λ=1)":
                s += " | vs CDR: " + paired_report(v, base, "x", "CDR")
            lines.append(s)


def main():
    lines = []
    night_a(lines)
    p5_vncdr(lines)
    txt = "\n".join(lines)
    (OUT / "q3_hybrids.txt").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
