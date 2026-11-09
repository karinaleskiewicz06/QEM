"""Numbers for deck slides 25 (twirling and CDR) and 26 (which method when), all rungs.

Reads cdr.csv / zne.csv of night A (12, 39 CZ) and night B (30, 57 CZ), as written by
``odra_window.py --analyse``. Same conventions as the numbers already on the slides:
OLS fit, mean |O - O_ideal| over the 8 points, geometric ratio with error floor 1e-4,
raw = target of the off_copies arm.

    python campaign/slide_numbers.py
    python campaign/slide_numbers.py --runs runs/odra_campaign/w01A runs/odra_campaign/w01B
"""
from __future__ import annotations

import argparse
import pathlib

import numpy as np
import pandas as pd
from scipy.stats import binomtest, wilcoxon

FLOOR = 1e-4
RUNG_ORDER = ["star", "linear", "circular", "all_to_all"]


def _load(runs):
    cdr, zne = [], []
    for r in runs:
        r = pathlib.Path(r)
        if not (r / "cdr.csv").exists():
            print(f"(skipping {r}: no cdr.csv; run odra_window.py --analyse {r})")
            continue
        cdr.append(pd.read_csv(r / "cdr.csv"))
        if (r / "zne.csv").exists():
            zne.append(pd.read_csv(r / "zne.csv"))
    cdr = pd.concat(cdr)
    cdr = cdr[cdr.fit == "ols"]
    return cdr, pd.concat(zne) if zne else pd.DataFrame()


def _arm(cdr, rung, arm, ts="near_target"):
    return cdr[(cdr.rung == rung) & (cdr.arm == arm) & (cdr.train_set == ts)].set_index("eval_index")


def _logdiff(a, b):
    idx = a.index.intersection(b.index)
    return np.log(np.maximum(a.loc[idx], FLOOR)) - np.log(np.maximum(b.loc[idx], FLOOR))


def _p(d, alt="less"):
    return float(wilcoxon(d, alternative=alt).pvalue) if np.any(np.asarray(d) != 0) else 1.0


def f(x):
    return f"{x:.3f}".replace(".", ",")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+",
                    default=["runs/odra_campaign/w01A", "runs/odra_campaign/w01B"])
    args = ap.parse_args(argv)
    cdr, zne = _load(args.runs)
    rungs = [r for r in RUNG_ORDER if r in set(cdr.rung)]
    ncz = cdr.groupby("rung").n_cz.first().to_dict()

    print("\n=== SLAJD 25: CDR bez twirlingu vs z twirlingiem (natywny, near_target) ===")
    print(f"{'CZ':>4} | {'CDR bez':>8} | {'CDR z tw.':>9} | {'wygrane':>7} | {'iloraz':>6} | p (1-str.)")
    pooled = []
    for r in rungs:
        off, tw = _arm(cdr, r, "off_copies"), _arm(cdr, r, "twirl_native")
        d = _logdiff(tw.err, off.err)
        pooled.append(d)
        print(f"{ncz[r]:>4} | {f(off.err.mean()):>8} | {f(tw.err.mean()):>9} | "
              f"{int((d < 0).sum())} / {len(d):<3} | {np.exp(d.mean()):6.2f} | {_p(d):.3f}")
    d = pd.concat(pooled)
    print(f"H1 (wszystkie szczeble): {int((d < 0).sum())} z {len(d)} par wygranych, "
          f"Wilcoxon p = {_p(d):.3f}, test znaków p = "
          f"{binomtest(int((d < 0).sum()), int((d != 0).sum()), alternative='greater').pvalue:.3f}, "
          f"iloraz {np.exp(d.mean()):.2f}")
    print("logiczny vs natywny (shared_random), średni błąd:")
    for r in rungs:
        lo, na = _arm(cdr, r, "twirl_logical", "shared_random"), _arm(cdr, r, "twirl_native", "shared_random")
        if len(lo) and len(na):
            dd = _logdiff(na.err, lo.err)
            print(f"  {ncz[r]:>2} CZ: logiczny {f(lo.err.mean())}, natywny {f(na.err.mean())}, "
                  f"natywny lepszy w {int((dd < 0).sum())}/{len(dd)}, p = {_p(dd):.3f}")

    print("\n=== SLAJD 26: która metoda kiedy (średni błąd) ===")
    print(f"{'CZ':>4} | {'raw':>6} | {'ZNE':>6} | {'garbage':>7} | {'CDR+tw':>6} | {'spread':>6}")
    for r in rungs:
        g = zne[zne.rung == r] if len(zne) else zne
        gen = g[g.variant == "genuine"].set_index("eval_index") if len(g) else None
        gar = g[g.variant == "garbage"].set_index("eval_index") if len(g) else None
        zg = f(gen.err_zne.mean()) if gen is not None and len(gen) else "--"
        zb = f(gar.err_zne.mean()) if gar is not None and len(gar) else "--"
        print(f"{ncz[r]:>4} | {f(_arm(cdr, r, 'off_copies').err_raw.mean()):>6} | {zg:>6} | {zb:>7} | "
              f"{f(_arm(cdr, r, 'twirl_native').err.mean()):>6} | {f(_arm(cdr, r, 'spread').err.mean()):>6}")
    print("testy ZNE (H4: ZNE < raw, ZNE < garbage, mediana W_neg <= 0,02, mediana SNR >= 2):")
    for r in rungs:
        g = zne[zne.rung == r] if len(zne) else zne
        if not len(g):
            continue
        gen = g[g.variant == "genuine"].set_index("eval_index")
        gar = g[g.variant == "garbage"].set_index("eval_index")
        p_raw = _p(_logdiff(gen.err_zne, gen.err_raw))
        p_gar = _p(_logdiff(gen.err_zne, gar.err_zne))
        ok = p_raw < 0.05 and p_gar < 0.05 and gen.w_neg.median() <= 0.02 and gen.snr_lmax.median() >= 2
        print(f"  {ncz[r]:>2} CZ: ZNE<raw p = {p_raw:.3f}; ZNE<garbage p = {p_gar:.3f}; "
              f"W_neg {gen.w_neg.median():.3f}; SNR {gen.snr_lmax.median():.1f} -> "
              f"{'ZNE uczciwe' if ok else 'H4 niespełnione'}")
    print("\nshoty / punkt: raw 8 192, ZNE 24 576, CDR 1 032 192")


if __name__ == "__main__":
    main()
