"""Cross-topology breakdown: Garnet (20q) vs Emerald (54q) on a common routing-cost axis.

Uses the twirl-campaign twirl-OFF arms (raw / CDR / ZNE), which are measured identically on both
devices (Emerald has no twirl arm, so twirl-OFF is the apples-to-apples set). Garnet points are
averaged over the drift windows found (garnet_twirl_w*.csv); Emerald is a single window
(emerald_xtopo.csv). Reports, per device: raw ⟨O⟩-error, CDR ⟨O⟩-error, CDR fit r², ZNE error vs
transpiled CZ, plus Spearman(metric vs CZ) — does degradation track routing on EACH topology, and do
the two topologies fall on a common curve (topology-general breakdown)?

    python analyze_cross_topology.py
"""
from __future__ import annotations

import csv
import glob
from collections import defaultdict

from scipy.stats import spearmanr


def _load(paths):
    """Return {cz: {arm_twirl: [err,...], 'cdr_r2':[...]}} accumulating over windows/files."""
    acc = defaultdict(lambda: defaultdict(list))
    for p in paths:
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                if str(r["twirl"]).strip().lower() == "true":
                    continue  # twirl-OFF only (Emerald has no ON; keeps devices comparable)
                cz = int(r["transpiled_cz"])
                acc[cz][r["arm"]].append(float(r["err"]))
                if r["arm"] == "cdr" and r.get("cdr_r2") not in (None, ""):
                    acc[cz]["cdr_r2"].append(float(r["cdr_r2"]))
    return acc


def _rows(acc):
    out = []
    for cz in sorted(acc):
        d = acc[cz]
        mean = lambda k: sum(d[k]) / len(d[k]) if d.get(k) else None
        out.append({"cz": cz, "raw": mean("raw"), "cdr": mean("cdr"),
                    "cdr_r2": mean("cdr_r2"), "zne": mean("zne")})
    return out


def _spear(rows, key):
    xy = [(r["cz"], r[key]) for r in rows if r[key] is not None]
    if len(xy) < 3:
        return None
    rho, _ = spearmanr([a for a, _ in xy], [b for _, b in xy])
    return rho


def main():
    devices = {
        "Garnet(20q)": [p for p in sorted(glob.glob("garnet_twirl_w*.csv")) if "banded" not in p],
        "Emerald(54q)": ["emerald_xtopo.csv"],
    }
    summary = []
    for dev, paths in devices.items():
        paths = [p for p in paths if glob.glob(p)]
        if not paths:
            print(f"[skip] {dev}: no files"); continue
        rows = _rows(_load(paths))
        print(f"\n=== {dev}  (files: {', '.join(paths)}) ===")
        print(f"  {'CZ':>4} | {'raw err':>8} | {'cdr err':>8} | {'cdr r2':>7} | {'zne err':>8}")
        for r in rows:
            f = lambda v: f"{v:.4f}" if v is not None else "   -   "
            print(f"  {r['cz']:>4} | {f(r['raw']):>8} | {f(r['cdr']):>8} | {f(r['cdr_r2']):>7} | {f(r['zne']):>8}")
        rho_raw, rho_r2 = _spear(rows, "raw"), _spear(rows, "cdr_r2")
        print(f"  Spearman: raw-err vs CZ = {rho_raw:+.2f}" if rho_raw is not None else "  Spearman raw: n/a",
              end="")
        print(f"  |  cdr-r2 vs CZ = {rho_r2:+.2f}" if rho_r2 is not None else "  |  cdr-r2: n/a")
        for r in rows:
            summary.append({"device": dev, **r})

    with open("cross_topology_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["device", "cz", "raw", "cdr", "cdr_r2", "zne"])
        w.writeheader()
        for r in summary:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    print("\nwrote cross_topology_summary.csv")
    print("READ: if raw-err rises and cdr-r2 falls with CZ on BOTH devices, the routing-driven "
          "breakdown is topology-general (Core Value); compare the CZ at which cdr-r2 crosses ~0.8.")


if __name__ == "__main__":
    main()
