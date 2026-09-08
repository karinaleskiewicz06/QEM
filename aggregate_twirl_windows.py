"""Combine per-window twirl+CDR runs into drift-banded results (methodology §9c, point b).

Each input CSV is one calibration/drift window produced by:
    python run_garnet_twirl.py --submit --arms cdr ... --window-id wK --out ...wK.csv

We aggregate ACROSS windows two ways:
  * per (placement, pattern, cz, arm, twirl): mean +/- inter-window std of err and r2
    -> the drift band on each measured point;
  * per (placement, pattern, cz, arm): the PAIRED difference ON-OFF computed WITHIN each
    window first, then mean +/- std across windows -> the correct drift band on the twirl
    gain (OFF/ON share a window, so the paired delta cancels common-mode drift).

Verdict per point: twirl gain is significant if |mean(delta)| > its inter-window std.

    python aggregate_twirl_windows.py garnet_twirl_w*.csv
    python aggregate_twirl_windows.py w1.csv w2.csv w3.csv --out garnet_twirl_banded.csv
"""
from __future__ import annotations

import argparse
import csv
import glob
import math
from collections import defaultdict


def _to_bool(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _mean_std(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None, 0
    m = sum(xs) / len(xs)
    # sample std (n-1); 0 when a single window
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1) if len(xs) > 1 else 0.0
    return m, math.sqrt(var), len(xs)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+", help="per-window CSVs (globs allowed)")
    ap.add_argument("--out", default="garnet_twirl_banded.csv")
    args = ap.parse_args()

    paths = sorted({p for pat in args.inputs for p in glob.glob(pat)})
    if not paths:
        raise SystemExit(f"no CSVs matched {args.inputs}")

    # rows[(placement,pattern,cz,arm)][window][twirl] = {"err":..,"r2":..}
    rows = defaultdict(lambda: defaultdict(dict))
    windows = set()
    for p in paths:
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                w = r.get("window", p)  # fall back to filename for legacy CSVs w/o window col
                windows.add(w)
                key = (r["placement"], r["pattern"], int(r["transpiled_cz"]), r["arm"])
                rows[key][w][_to_bool(r["twirl"])] = {
                    "err": _to_float(r["err"]), "r2": _to_float(r.get("cdr_r2")),
                }
    print(f"{len(paths)} file(s), {len(windows)} window(s): {sorted(windows)}\n")

    out_rows = []
    band_keys = ["placement", "pattern", "transpiled_cz", "arm"]
    # per-window, per-arm list of (cz, delta_r2) for the trend (gain-grows-with-routing) test
    trend = defaultdict(lambda: defaultdict(list))  # trend[arm][window] = [(cz, d_r2), ...]
    for key in sorted(rows, key=lambda k: (k[2], k[0], k[1], k[3])):
        placement, pattern, cz, arm = key
        wdata = rows[key]
        base = dict(zip(band_keys, key))
        # per-twirl bands (mean +/- inter-window std)
        for twirl in (False, True):
            e_m, e_s, ne = _mean_std([wdata[w].get(twirl, {}).get("err") for w in wdata])
            r_m, r_s, nr = _mean_std([wdata[w].get(twirl, {}).get("r2") for w in wdata])
            out_rows.append({**base, "twirl": twirl, "n_windows": max(ne, nr),
                             "err_mean": e_m, "err_std": e_s, "r2_mean": r_m, "r2_std": r_s,
                             "d_r2_mean": "", "d_r2_std": "", "d_err_mean": "", "d_err_std": "",
                             "r2_significant": "", "per_window_d_r2": ""})
        # paired ON-OFF WITHIN each window (cancels common-mode drift), keyed by window
        dw_r2, dw_err = {}, {}
        for w in wdata:
            on, off = wdata[w].get(True, {}), wdata[w].get(False, {})
            if on.get("r2") is not None and off.get("r2") is not None:
                dw_r2[w] = on["r2"] - off["r2"]
                trend[arm][w].append((cz, dw_r2[w]))
            if on.get("err") is not None and off.get("err") is not None:
                dw_err[w] = on["err"] - off["err"]
        d_r2, d_err = list(dw_r2.values()), list(dw_err.values())
        dr_m, dr_s, _ = _mean_std(d_r2)
        de_m, de_s, _ = _mean_std(d_err)
        sig = "" if dr_m is None else ("yes" if abs(dr_m) > (dr_s or 0) else "within-drift")
        per_w = "; ".join(f"{w}:{v:+.3f}" for w, v in sorted(dw_r2.items()))
        out_rows.append({**base, "twirl": "DELTA(ON-OFF)", "n_windows": len(d_r2),
                         "err_mean": "", "err_std": "", "r2_mean": "", "r2_std": "",
                         "d_r2_mean": dr_m, "d_r2_std": dr_s,
                         "d_err_mean": de_m, "d_err_std": de_s, "r2_significant": sig,
                         "per_window_d_r2": per_w})

        def fmt(m, s):
            return "   n/a  " if m is None else f"{m:+.4f}±{(s or 0):.4f}"
        print(f"  cz={cz:>3} {placement:>8}:{pattern:<11} {arm} | "
              f"Δr²={fmt(dr_m, dr_s)} ({sig}) | Δerr={fmt(de_m, de_s)} | [{per_w}]")

    # ---- trend test: does the twirl gain GROW with routing cost? (slope of Δr² vs cz) ---- #
    def _slope(pts):
        if len(pts) < 2:
            return None
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
        den = sum((x - mx) ** 2 for x in xs)
        return None if den == 0 else sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    print()
    for arm in sorted(trend):
        slopes = [s for s in (_slope(sorted(pts)) for pts in trend[arm].values()) if s is not None]
        sm, ss, nS = _mean_std(slopes)
        if sm is None:
            continue
        # slope units: Δr² per CZ; scale to per-100-CZ for readability
        verdict = "gain GROWS with routing" if sm > (ss or 0) else "trend within drift"
        print(f"  TREND {arm}: dΔr²/dCZ = {sm*100:+.4f}±{(ss or 0)*100:.4f} per 100 CZ "
              f"(n={nS} windows) -> {verdict}")

    fields = band_keys + ["twirl", "n_windows", "err_mean", "err_std", "r2_mean", "r2_std",
                          "d_r2_mean", "d_r2_std", "d_err_mean", "d_err_std", "r2_significant",
                          "per_window_d_r2"]
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in out_rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    print(f"\nwrote {args.out}")
    print("READ: twirl gain is real where Δr²>0 grows with cz AND r2_significant=yes "
          "(gain exceeds inter-window drift).")


if __name__ == "__main__":
    main()
