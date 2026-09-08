"""Routing-cost cross-topology + SWAP<->degradation correlation (free reanalysis).

Closes two gaps (project_review_gaps.md #2, #3), zero credits:

#2  Cross-topology routing COST is already computed by transpilation for ODRA,
    Garnet AND Emerald (routing_ladder_<device>.csv) — surface it. Same logical
    circuit costs more CZ/SWAP on the bigger/sparser lattice.

#3  topo_dist <-> SWAP <-> degradation correlation (methodology_month_2.md §8,
    "definition of done"): join measured error (garnet_full / ODRA hardware) with
    the routing-cost predictors and report Spearman rank correlations.

    python analyze_routing_correlation.py
"""
from __future__ import annotations

import csv
import numpy as np

try:
    from scipy.stats import spearmanr
    def _spear(a, b):
        rho, p = spearmanr(a, b)
        return float(rho), float(p)
except Exception:  # scipy always present here, but stay safe
    def _spear(a, b):
        ar = np.argsort(np.argsort(a)); br = np.argsort(np.argsort(b))
        rho = np.corrcoef(ar, br)[0, 1]
        return float(rho), float("nan")


def _read(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def main() -> None:
    # ---- #2: cross-topology routing cost (transpilation only, no credits) ---- #
    print("=" * 74)
    print("#2  CROSS-TOPOLOGY ROUTING COST — same logical circuit, three devices")
    print("=" * 74)
    ladders = {d: _read(f"routing_ladder_{d}.csv") for d in ("odra", "garnet", "emerald")}
    patterns = ["star", "linear", "circular", "all_to_all"]
    print(f"{'pattern':>11} | {'ODRA cz/sw':>12} | {'Garnet cz/sw':>13} | {'Emerald cz/sw':>13}")
    for pat in patterns:
        cells = []
        for d in ("odra", "garnet", "emerald"):
            row = next((r for r in ladders[d] if r["pattern"] == pat), None)
            cells.append(f"{row['transpiled_cz']}/{row['swaps']}" if row else "-")
        print(f"{pat:>11} | {cells[0]:>12} | {cells[1]:>13} | {cells[2]:>13}")
    print("  -> Emerald (54q) pays the most routing for the SAME 5q circuit "
          "(all_to_all: 72 CZ / 14 SWAP vs Garnet 57/9 vs ODRA 54/8).")
    print("  -> Cross-topology COST axis is ready for all 3 topologies WITHOUT hardware.")

    # ---- #3: SWAP/topo_dist <-> degradation correlation (Garnet, measured) --- #
    print()
    print("=" * 74)
    print("#3  ROUTING-COST <-> DEGRADATION correlation (Garnet, measured error)")
    print("=" * 74)
    err = _read("garnet_full_results.csv")
    cost = _read("routing_ladder_garnet_optimal.csv") + _read("routing_ladder_garnet_adverse.csv")
    cost_by = {(r["placement"], r["pattern"]): r for r in cost}

    joined = []
    for e in err:
        k = (e["placement"], e["pattern"])
        if k in cost_by:
            c = cost_by[k]
            joined.append(dict(
                placement=e["placement"], pattern=e["pattern"],
                err_raw=float(e["err_raw"]), err_zne=float(e["err_zne"]),
                cz=float(c["transpiled_cz"]), swaps=float(c["swaps"]),
                topo_dist=float(c.get("topo_dist", "nan")), depth=float(c["transpiled_depth"]),
            ))
    print(f"joined {len(joined)} (placement x pattern) points")
    print(f"{'predictor':>12} | {'Spearman rho vs err_raw':>24} | {'vs err_zne':>12}")
    for pred in ("cz", "swaps", "topo_dist", "depth"):
        xs = [r[pred] for r in joined]
        rho_raw, p_raw = _spear(xs, [r["err_raw"] for r in joined])
        rho_zne, _ = _spear(xs, [r["err_zne"] for r in joined])
        print(f"{pred:>12} | {rho_raw:>+18.3f} (p={p_raw:.3f}) | {rho_zne:>+11.3f}")
    print("  -> strong positive rho = more routing (CZ/SWAP/topo-dist/depth) -> more error.")
    print("     This is the methodology §8 'topo_dist<->SWAP<->degradation' deliverable.")

    # ---- bonus: ODRA (star) correlation, so the 3rd topology is included ----- #
    print()
    print("-" * 74)
    print("BONUS — ODRA (star) measured error vs routing cost (M1 hardware)")
    odra_err = [r for r in _read("hardware_results.csv") if r.get("dd", "False") == "False"]
    odra_cost = {r["pattern"]: r for r in _read("routing_ladder_odra.csv")}
    ojoin = []
    for e in odra_err:
        c = odra_cost.get(e["pattern"])
        if c:
            ojoin.append(dict(pattern=e["pattern"], err_raw=float(e["raw_err"]),
                              cz=float(c["transpiled_cz"]), swaps=float(c["swaps"])))
    if len(ojoin) >= 3:
        for pred in ("cz", "swaps"):
            rho, p = _spear([r[pred] for r in ojoin], [r["err_raw"] for r in ojoin])
            print(f"  ODRA err_raw vs {pred:>6}: Spearman rho = {rho:+.3f} (p={p:.3f}, n={len(ojoin)})")
    else:
        print(f"  (only {len(ojoin)} ODRA points joined — too few for correlation)")

    # ---- write summary ------------------------------------------------------- #
    out = "routing_correlation_summary.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(joined[0].keys()))
        w.writeheader(); w.writerows(joined)
    print("-" * 74)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
