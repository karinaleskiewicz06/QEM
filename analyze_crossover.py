"""Crossover analysis — which mitigation method pays up to what 2q budget (Core Value).

Free reanalysis of existing Garnet CSVs. Quantifies the project's headline claim
instead of eyeballing make_method_comparison.py:

1. QUALITY crossover: ZNE vs CDR on the SAME VQC (matched placement/pattern), the
   transpiled-CZ at which CDR's mitigated error overtakes ZNE's (interpolated).
2. COST-normalised ranking: at a target error tol, which method reaches it at the
   fewest effective device shots (shots_to_target.compare_methods).
3. Per-method breakdown: ZNE error-reduction gain vs CZ (where mitigation fades).

QEC ([[4,2,2]]) runs a different circuit (random-Clifford mirror), so it is reported
on the cost axis with an explicit caveat, NOT in the direct ZNE-vs-CDR error crossover.

    python analyze_crossover.py
"""
from __future__ import annotations

import csv
import numpy as np

from shots_to_target import (
    zne_effective_shots, cdr_effective_shots, compare_methods,
)


def _read(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def main() -> None:
    # NOTE: standalone [[4,2,2]] QEC is intentionally excluded here — it will be
    # replaced by the QEC+ZNE composition arm (see qec_logical_directions.md §6).
    zne = _read("garnet_full_results.csv")
    cdr = _read("garnet_cdr_results.csv")

    # --- align ZNE and CDR on matched (placement, pattern) points ------------- #
    def key(r):
        return (r["placement"], r["pattern"])
    zne_by = {key(r): r for r in zne if r["pattern"] in ("star", "all_to_all")}
    cdr_by = {key(r): r for r in cdr}
    shared = sorted(set(zne_by) & set(cdr_by), key=lambda k: float(zne_by[k]["transpiled_cz"]))

    ZNE_SHOTS, ZNE_SCALES = 4096, 3          # scales {1,3,5}
    CDR_SHOTS, CDR_NTRAIN = 2048, 40

    print("=" * 78)
    print("ZNE vs CDR — matched VQC points (same circuit), ordered by transpiled CZ")
    print("=" * 78)
    print(f"{'CZ':>4} {'placement':>9} {'pattern':>11} | {'err_ZNE':>8} {'err_CDR':>8} "
          f"{'winner':>7} | {'eff_ZNE':>8} {'eff_CDR':>8}")
    rows = []
    cz_list, ezne_list, ecdr_list = [], [], []
    for k in shared:
        z, c = zne_by[k], cdr_by[k]
        cz = float(z["transpiled_cz"])
        ez, ec = float(z["err_zne"]), float(c["err_cdr"])
        eff_z = zne_effective_shots(ZNE_SHOTS, ZNE_SCALES)
        eff_c = cdr_effective_shots(CDR_SHOTS, CDR_NTRAIN)
        win = "ZNE" if ez < ec else "CDR"
        cz_list.append(cz); ezne_list.append(ez); ecdr_list.append(ec)
        rows.append(dict(cz=cz, placement=k[0], pattern=k[1], err_zne=ez, err_cdr=ec,
                         eff_zne=eff_z, eff_cdr=eff_c, winner=win))
        print(f"{cz:>4.0f} {k[0]:>9} {k[1]:>11} | {ez:>8.4f} {ec:>8.4f} {win:>7} | "
              f"{eff_z:>8.0f} {eff_c:>8.0f}")

    # --- QUALITY crossover: interpolate CZ where err_cdr == err_zne ----------- #
    cz_arr = np.array(cz_list); d = np.array(ezne_list) - np.array(ecdr_list)  # >0 => CDR better
    order = np.argsort(cz_arr); cz_s, d_s = cz_arr[order], d[order]
    cross = None
    for i in range(1, len(cz_s)):
        if d_s[i - 1] < 0 <= d_s[i]:  # ZNE better -> CDR better
            frac = (0 - d_s[i - 1]) / (d_s[i] - d_s[i - 1])
            cross = cz_s[i - 1] + frac * (cz_s[i] - cz_s[i - 1])
            break
    print("-" * 78)
    if cross is not None:
        print(f"QUALITY CROSSOVER ~ {cross:.0f} transpiled CZ:")
        print(f"  below ~{cross:.0f} CZ  -> ZNE gives lower error (and is ~"
              f"{cdr_effective_shots(CDR_SHOTS,CDR_NTRAIN)/zne_effective_shots(ZNE_SHOTS,ZNE_SCALES):.0f}x cheaper)")
        print(f"  above ~{cross:.0f} CZ  -> CDR gives lower error (worth its extra cost)")
    else:
        print("No clean quality crossover in range.")

    # --- per-method ZNE gain vs CZ (breakdown) -------------------------------- #
    print("-" * 78)
    print("ZNE error-reduction gain (err_raw / err_zne) vs CZ  [mitigation fades to ~1]:")
    for r in sorted(zne, key=lambda x: float(x["transpiled_cz"])):
        if r["pattern"] in ("star", "all_to_all"):
            g = float(r["err_raw"]) / max(float(r["err_zne"]), 1e-9)
            print(f"  CZ {float(r['transpiled_cz']):>4.0f} {r['placement']:>9} "
                  f"{r['pattern']:>11}: gain {g:.2f}x")

    # --- COST-normalised ranking at target tolerances (compare_methods) ------- #
    print("-" * 78)
    print("COST-normalised: cheapest method reaching a target error (effective shots)")
    print("  (standalone QEC omitted — to be replaced by the QEC+ZNE combo arm)")
    # build a comparable record set at the high-cost point (adverse all_to_all-ish)
    for tol in (0.15, 0.10, 0.05):
        recs = []
        # ZNE + CDR at the high-CZ shared point
        hi = max(shared, key=lambda k: float(zne_by[k]["transpiled_cz"]))
        recs.append(dict(method="ZNE", err=float(zne_by[hi]["err_zne"]),
                         effective_shots=zne_effective_shots(ZNE_SHOTS, ZNE_SCALES)))
        recs.append(dict(method="CDR", err=float(cdr_by[hi]["err_cdr"]),
                         effective_shots=cdr_effective_shots(CDR_SHOTS, CDR_NTRAIN)))
        ranked = compare_methods([dict(r) for r in recs], target_tol=tol, metric="err")
        best = ranked[0]
        tag = "meets" if best["meets_target"] else "NONE meets"
        print(f"  tol {tol:.2f} @ CZ {float(zne_by[hi]['transpiled_cz']):.0f}: "
              f"winner={best['method']} ({tag}, err={best['err']:.3f}, "
              f"eff={best['effective_shots']:.0f})")

    # --- write summary CSV ---------------------------------------------------- #
    out = "garnet_crossover_summary.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("-" * 78)
    print(f"wrote {out}")
    if cross is not None:
        print(f"CORE-VALUE ONE-LINER: on Garnet, ZNE pays up to ~{cross:.0f} transpiled CZ; "
              f"beyond that only CDR keeps reducing error, at ~7x the device-shot cost.")


if __name__ == "__main__":
    main()
