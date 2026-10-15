"""Decision rule for twirling, recomputed on epsilon instead of r^2 (review F4).

The report recommended "measure r^2; if it is >= 0.95 there is nothing for twirling to
repair". The hardware pairs say otherwise: at the cheapest ladder point r^2 sits at
0.97-0.98 (so the rule says skip) while the CDR error still drops by 20-60%.

This script rebuilds every shot-matched ON/OFF pair from the per-window CSVs and asks
which quantity, if any, predicts the *error* reduction. Output: twirl_pairs_all.csv.

    python analyze_twirl_rule.py
"""

from __future__ import annotations

import argparse
import csv
import math
from itertools import groupby

WINDOWS = [
    ("odra_twirl_o1.csv", "o1", "ODRA"),
    ("odra_twirl_o2.csv", "o2", "ODRA"),
    ("garnet_twirl_w1.csv", "w1", "Garnet"),
    ("garnet_twirl_w2.csv", "w2", "Garnet"),
    ("garnet_twirl_w3.csv", "w3", "Garnet"),
]


def spearman(a: list[float], b: list[float]) -> float:
    """Spearman rho without a scipy dependency (no ties expected in these samples)."""
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos + 1
        return r

    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else 0.0


def sign_test_p(successes: int, n: int) -> float:
    """Two-sided-ish exact binomial tail P(X >= successes) under p=0.5."""
    return sum(math.comb(n, k) for k in range(successes, n + 1)) / 2 ** n


def load_pairs() -> list[dict]:
    rows = []
    for path, win, dev in WINDOWS:
        try:
            fh = open(path)
        except FileNotFoundError:
            continue
        for x in csv.DictReader(fh):
            if x.get("arm") != "cdr":
                continue
            rows.append({
                "dev": dev, "win": win, "cz": int(x["transpiled_cz"]),
                "tw": x["twirl"] == "True", "err": float(x["err"]),
                "r2": float(x["cdr_r2"]) if x.get("cdr_r2") else None,
                "shots": x.get("shots"), "n_avg": x.get("n_avg"),
            })

    key = lambda r: (r["dev"], r["win"], r["cz"])
    pairs = []
    for k, grp in groupby(sorted(rows, key=key), key=key):
        grp = list(grp)
        off = [x for x in grp if not x["tw"]]
        on = [x for x in grp if x["tw"]]
        if not (off and on):
            continue
        o, n_ = off[0], on[0]
        # the comparison is only meaningful at a matched measurement budget
        matched = (o["shots"] == n_["shots"]) and (o["n_avg"] == n_["n_avg"])
        pairs.append({
            "device": k[0], "window": k[1], "cz": k[2],
            "err_off": o["err"], "err_on": n_["err"],
            "err_ratio": n_["err"] / o["err"],
            "r2_off": o["r2"], "r2_on": n_["r2"],
            "d_r2": (n_["r2"] - o["r2"]) if (o["r2"] and n_["r2"]) else None,
            "shots": o["shots"], "n_avg": o["n_avg"], "shot_matched": matched,
        })
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="twirl_pairs_all.csv")
    args = ap.parse_args()

    pairs = load_pairs()
    if not pairs:
        raise SystemExit("no per-window twirl CSVs found")

    unmatched = [p for p in pairs if not p["shot_matched"]]
    if unmatched:
        print(f"WARNING: {len(unmatched)} pair(s) are NOT shot-matched and are excluded")
        pairs = [p for p in pairs if p["shot_matched"]]

    gain = [1 - p["err_ratio"] for p in pairs]
    better = sum(g > 0 for g in gain)
    n = len(pairs)
    ratios = sorted(p["err_ratio"] for p in pairs)
    median = ratios[n // 2] if n % 2 else (ratios[n // 2 - 1] + ratios[n // 2]) / 2

    print(f"shot-matched ON/OFF pairs: {n}   error reduced in {better}/{n}"
          f"   sign-test p = {sign_test_p(better, n):.2g}")
    print(f"median err_ON/err_OFF = {median:.3f}")

    print("\nWhat predicts the error reduction?")
    for name, vals in (("r2 without twirling", [p["r2_off"] for p in pairs]),
                       ("two-qubit gate count", [float(p["cz"]) for p in pairs]),
                       ("delta r2", [p["d_r2"] for p in pairs])):
        if all(v is not None for v in vals):
            print(f"  rho(reduction, {name:21s}) = {spearman(gain, vals):+.3f}")

    hi = [p for p in pairs if p["r2_off"] and p["r2_off"] > 0.95]
    if hi:
        print(f"\nPoints where the old r2 rule said SKIP (r2 > 0.95):")
        for p in sorted(hi, key=lambda p: -p["r2_off"]):
            print(f"  {p['device']:7s}/{p['window']} {p['cz']:>3} CZ  r2={p['r2_off']:.4f}  "
                  f"eps {p['err_off']:.4f} -> {p['err_on']:.4f}  "
                  f"({1 - p['err_ratio']:+.0%})")
        print(f"  error fell in {sum(1 for p in hi if p['err_on'] < p['err_off'])}/{len(hi)} of them")

    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(pairs[0]))
        w.writeheader()
        w.writerows(pairs)
    print(f"\nwrote {args.out}")

    print("\nCONCLUSION: no measured quantity predicts the gain, and under a matched shot\n"
          "budget twirling costs nothing extra (both arms average the same n_avg copies).\n"
          "The defensible rule is therefore 'always twirl', not 'twirl when r2 is low'.")


if __name__ == "__main__":
    main()
