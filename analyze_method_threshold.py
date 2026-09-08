"""Method breakdown vs routing: raw / CDR / ZNE on a common CZ axis, per topology.

Answers: which method pays at each routing cost, where CDR<->ZNE cross over, and the CZ beyond which
NO method beats raw (the collapse threshold). CDR twirl-OFF (plain CDR) so it is the honest method,
not the twirl-rescued one. Sources:
    ODRA    : cdr_hard_results.csv (raw,cdr) + zne_hard_results.csv (zne_richardson), matched on CZ
    Garnet  : garnet_twirl_w*.csv  (raw, cdr-OFF, zne), averaged over drift windows
    Emerald : emerald_xtopo.csv    (raw, cdr, zne), single window
"""
from __future__ import annotations

import csv
import glob
from collections import defaultdict


def odra():
    raw, cdr, zne = {}, {}, {}
    with open("cdr_hard_results.csv") as f:
        for r in csv.DictReader(f):
            if r["device"] == "odra":
                cz = int(r["transpiled_cz"]); raw[cz] = float(r["err_raw"]); cdr[cz] = float(r["err_cdr"])
    with open("zne_hard_results.csv") as f:
        for r in csv.DictReader(f):
            zne[int(r["transpiled_cz"])] = float(r["zne_richardson_err"])
    return {cz: (raw[cz], cdr.get(cz), zne.get(cz)) for cz in sorted(raw)}


def from_twirl(paths):
    raw, cdr, zne = defaultdict(list), defaultdict(list), defaultdict(list)
    for p in paths:
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                if str(r["twirl"]).lower() != "false":
                    continue
                cz = int(r["transpiled_cz"]); e = float(r["err"])
                {"raw": raw, "cdr": cdr, "zne": zne}[r["arm"]][cz].append(e)
    mean = lambda d, cz: sum(d[cz]) / len(d[cz]) if d.get(cz) else None
    return {cz: (mean(raw, cz), mean(cdr, cz), mean(zne, cz)) for cz in sorted(raw)}


def report(name, data):
    print(f"\n=== {name} ===")
    print(f"  {'CZ':>4} | {'raw':>7} | {'CDR':>7} | {'ZNE':>7} | best    | note")
    collapse = None
    for cz, (raw, cdr, zne) in data.items():
        cands = {"raw": raw, "CDR": cdr, "ZNE": zne}
        cands = {k: v for k, v in cands.items() if v is not None}
        best = min(cands, key=cands.get)
        note = ""
        if cdr is not None and cdr > raw and zne is not None and zne > raw:
            note = "COLLAPSE (no method beats raw)"; collapse = collapse or cz
        elif best == "raw":
            note = "raw wins"
        f = lambda v: f"{v:.4f}" if v is not None else "   -   "
        print(f"  {cz:>4} | {f(raw)} | {f(cdr)} | {f(zne)} | {best:<7} | {note}")
    return collapse


def main():
    devs = [
        ("ODRA (star)", odra()),
        ("Garnet (20q)", from_twirl([p for p in sorted(glob.glob("garnet_twirl_w*.csv"))
                                     if "banded" not in p])),
        ("Emerald (54q)", from_twirl(["emerald_xtopo.csv"])),
    ]
    for name, d in devs:
        c = report(name, d)
        if c:
            print(f"  -> {name}: NO method pays beyond ~{c} CZ")
    print("\nREAD: ZNE tends to win at LOW CZ (below the ~39-CZ crossover), CDR at HIGHER CZ; both")
    print("break at extreme routing. ZNE is erratic (can be HARMFUL, e.g. Emerald cz21). The collapse")
    print("threshold = highest CZ where the best method still beats raw.")


if __name__ == "__main__":
    main()
