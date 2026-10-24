"""The confirmatory analysis of ``preregistration.md``, frozen with it under ``prereg-v1``.

Reads ``cdr.csv`` / ``zne.csv`` of the w01 nights (``campaign/odra_window.py --analyse``
writes them from ``counts.jsonl``) and runs exactly the tests the plan names. Nothing in
here may be changed after the tag without being reported as a deviation.

    python -m analysis.prereg_w01                         # runs/odra_campaign/w01{A,B,P5}
    python -m analysis.prereg_w01 --root <dir> --window w01
"""

from __future__ import annotations

import argparse
import pathlib

import numpy as np
import pandas as pd
from scipy.stats import binomtest, wilcoxon

FLOOR = 1e-4
ALPHA = 0.05
N_BOOT = 10_000
OUT = pathlib.Path("results")


def _read(path: pathlib.Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() else None


def paired(cdr: pd.DataFrame, a: tuple[str, str], b: tuple[str, str], fit: str = "ols"):
    """Errors of arm ``a`` and ``b`` on the same (rung, eval_index), aligned."""
    sel = cdr[cdr.fit == fit]
    ea = sel[(sel.arm == a[0]) & (sel.train_set == a[1])].set_index(["rung", "eval_index"])
    eb = sel[(sel.arm == b[0]) & (sel.train_set == b[1])].set_index(["rung", "eval_index"])
    j = ea[["err", "err_raw", "ideal", "mitigated", "raw"]].join(
        eb[["err", "mitigated"]], lsuffix="_a", rsuffix="_b", how="inner")
    return j


def ratio_ci(la: np.ndarray, lb: np.ndarray, seed: int = 0) -> tuple[float, float, float]:
    """Geometric-mean ratio a/b and its percentile bootstrap 95% CI over pairs."""
    d = la - lb
    rng = np.random.default_rng(seed)
    boots = [np.exp(d[rng.integers(0, len(d), len(d))].mean()) for _ in range(N_BOOT)]
    return float(np.exp(d.mean())), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))


def one_sided(j: pd.DataFrame, name: str, a: str, b: str) -> dict:
    """H: arm a has the smaller error. Wilcoxon signed-rank on log errors."""
    la = np.log(np.maximum(j.err_a.values, FLOOR))
    lb = np.log(np.maximum(j.err_b.values, FLOOR))
    p = float(wilcoxon(la, lb, alternative="less").pvalue) if len(j) else float("nan")
    r, lo, hi = ratio_ci(la, lb)
    return {"id": name, "comparison": f"{a} vs {b}", "n_pairs": int(len(j)), "p": p,
            "ratio": r, "ci_lo": lo, "ci_hi": hi,
            "a_better": int((la < lb).sum()), "per_rung": {
                rung: round(float(np.exp((np.log(np.maximum(g.err_a, FLOOR))
                                          - np.log(np.maximum(g.err_b, FLOOR))).mean())), 4)
                for rung, g in j.groupby(level="rung")}}


def holm(rows: list[dict]) -> None:
    """Holm step-down: adds ``p_holm`` and ``reject`` in place."""
    order = sorted(range(len(rows)), key=lambda i: rows[i]["p"])
    m, running = len(rows), 0.0
    for k, i in enumerate(order):
        running = max(running, min(1.0, (m - k) * rows[i]["p"]))
        rows[i]["p_holm"] = running
    for r in rows:
        r["reject"] = bool(r["p_holm"] < ALPHA)


def depth_terms(p5_dir: pathlib.Path) -> list[dict]:
    from analysis.depth_regression import load, fit
    df = load([p5_dir])
    sub = df[~df.rung.str.match(r"star_L\d+")]
    out = []
    for r in fit(sub, "log_err_raw", "l3_only"):
        if r["term"] in ("cz10", "dur_us"):
            # one-sided in the registered direction; the fitted p is two-sided
            p = r["p"] / 2 if r["coef"] > 0 else 1 - r["p"] / 2
            out.append({"id": "H7a" if r["term"] == "cz10" else "H7b",
                        "comparison": f"coefficient of {r['term']} on log raw error",
                        "n_pairs": r["n"], "p": float(p), "ratio": r["factor"],
                        "ci_lo": float(np.exp(r["ci_lo"])), "ci_hi": float(np.exp(r["ci_hi"])),
                        "a_better": None, "per_rung": None})
    return out


def zne_window(zne: pd.DataFrame, cdr: pd.DataFrame) -> pd.DataFrame:
    """H4 per rung: genuine beats raw and garbage, W_neg <= 0.02, SNR >= 2."""
    rows = []
    for rung, g in zne.groupby("rung"):
        gen = g[g.variant == "genuine"].set_index("eval_index")
        gar = g[g.variant == "garbage"].set_index("eval_index")
        common = gen.index.intersection(gar.index)
        p_raw = float(wilcoxon(np.log(np.maximum(gen.err_zne, FLOOR)),
                               np.log(np.maximum(gen.err_raw, FLOOR)),
                               alternative="less").pvalue) if len(gen) > 1 else float("nan")
        rows.append({"rung": rung, "n_cz": int(gen.n_cz.iloc[0]), "n_points": int(len(gen)),
                     "err_raw": float(gen.err_raw.mean()), "err_zne": float(gen.err_zne.mean()),
                     "err_garbage": float(gar.loc[common, "err_zne"].mean()) if len(common) else np.nan,
                     "p_zne_below_raw": p_raw,
                     "median_w_neg": float(gen.w_neg.median()),
                     "median_snr_lmax": float(gen.snr_lmax.median())})
    t = pd.DataFrame(rows)
    if not t.empty:
        t["pays"] = ((t.p_zne_below_raw < ALPHA) & (t.err_zne < t.err_garbage)
                     & (t.median_w_neg <= 0.02) & (t.median_snr_lmax >= 2))
    return t


def decisions(j: pd.DataFrame) -> dict:
    """H5: McNemar raw vs mitigated (arm a), and where the changes fall."""
    ok_raw = np.sign(j.raw) == np.sign(j.ideal)
    ok_m = np.sign(j.mitigated_a) == np.sign(j.ideal)
    b, c = int((ok_raw & ~ok_m).sum()), int((~ok_raw & ok_m).sum())
    small = j.ideal.abs() < j.ideal.abs().median()
    changed = ok_raw != ok_m
    return {"n": int(len(j)), "agree_raw": float(ok_raw.mean()), "agree_mitigated": float(ok_m.mean()),
            "b_raw_only": b, "c_mitigated_only": c,
            "p_mcnemar": float(binomtest(c, b + c, 0.5).pvalue) if b + c else float("nan"),
            "changes": int(changed.sum()), "changes_below_median_margin": int((changed & small).sum())}


def run(root: pathlib.Path, window: str, out: pathlib.Path = OUT) -> dict:
    a_b = [d for d in (root / f"{window}A", root / f"{window}B") if (d / "cdr.csv").exists()]
    cdr = pd.concat([pd.read_csv(d / "cdr.csv") for d in a_b], ignore_index=True) if a_b else None
    zne = pd.concat([pd.read_csv(d / "zne.csv") for d in a_b if (d / "zne.csv").exists()],
                    ignore_index=True) if a_b else None
    primary = []
    if cdr is not None:
        primary.append(one_sided(paired(cdr, ("twirl_native", "near_target"),
                                        ("off_copies", "near_target")), "H1",
                                 "twirl_native:near_target", "off_copies:near_target"))
        primary.append(one_sided(paired(cdr, ("twirl_native", "shared_random"),
                                        ("twirl_logical", "shared_random")), "H3",
                                 "twirl_native:shared_random", "twirl_logical:shared_random"))
        primary.append(one_sided(paired(cdr, ("spread", "near_target"),
                                        ("twirl_native", "near_target")), "H6",
                                 "spread:near_target", "twirl_native:near_target"))
    p5 = root / f"{window}P5"
    if (p5 / "cdr.csv").exists():
        primary += depth_terms(p5)
    holm(primary)

    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(primary).to_csv(out / f"prereg_{window}_primary.csv", index=False)
    res = {"primary": primary}
    if zne is not None and not zne.empty:
        z = zne_window(zne, cdr)
        z.to_csv(out / f"prereg_{window}_zne_window.csv", index=False)
        res["zne"] = z
    if cdr is not None:
        dec = decisions(paired(cdr, ("twirl_native", "near_target"), ("off_copies", "near_target")))
        pd.DataFrame([dec]).to_csv(out / f"prereg_{window}_decisions.csv", index=False)
        res["decisions"] = dec
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="runs/odra_campaign")
    ap.add_argument("--window", default="w01")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    res = run(pathlib.Path(a.root), a.window, pathlib.Path(a.out))
    pd.set_option("display.width", 160)
    print("PRIMARY (Holm across the family):")
    print(pd.DataFrame(res["primary"]).drop(columns=["per_rung"]).round(4).to_string(index=False))
    for r in res["primary"]:
        if r.get("per_rung"):
            print(f"  {r['id']} ratio per rung: {r['per_rung']}")
    if "zne" in res:
        print("\nH4 ZNE window (secondary):")
        print(res["zne"].round(4).to_string(index=False))
    if "decisions" in res:
        print("\nH5 decisions (secondary):", res["decisions"])
    print(f"\nwrote {a.out}/prereg_{a.window}_*.csv")


if __name__ == "__main__":
    main()
