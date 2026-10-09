"""Cross-topology CDR-breakdown figure: ODRA (star) vs Garnet (20q) vs Emerald (54q).

CDR fit r^2 (sharp coherence/linearity signal) vs transpiled-CZ routing cost, on the hard-model VQC,
across three superconducting topologies. Shows the routing-driven CDR breakdown is topology-general.
    ODRA     : cdr_hard_results.csv (Month-1 hard-model CDR ladder, optimal placements)
    Garnet   : garnet_twirl_w*.csv  (twirl-OFF CDR, averaged over drift windows)
    Emerald  : emerald_xtopo.csv    (CDR, single window, no twirl)
"""
from __future__ import annotations

import csv
import glob
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def odra():
    xs, ys = [], []
    with open("cdr_hard_results.csv") as f:
        for r in csv.DictReader(f):
            if r["device"] == "odra":
                xs.append(int(r["transpiled_cz"])); ys.append(float(r["cdr_r2"]))
    return xs, ys


def banded(paths):
    acc = defaultdict(list)
    for p in paths:
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                if r["arm"] == "cdr" and str(r["twirl"]).lower() == "false" and r["cdr_r2"]:
                    acc[int(r["transpiled_cz"])].append(float(r["cdr_r2"]))
    xs = sorted(acc)
    return xs, [sum(acc[c]) / len(acc[c]) for c in xs]


def main():
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    series = [
        ("ODRA (star, 5q)", *odra(), "#d1495b", "o", "-"),
        ("Garnet (20q lattice)", *banded([p for p in sorted(glob.glob("garnet_twirl_w*.csv"))
                                          if "banded" not in p]), "#2e86ab", "s", "-"),
        ("Emerald (54q lattice)", *banded(["emerald_xtopo.csv"]), "#3c896d", "^", "-"),
    ]
    for label, xs, ys, c, m, ls in series:
        if xs:
            pts = sorted(zip(xs, ys))
            ax.plot([x for x, _ in pts], [y for _, y in pts], ls, color=c, marker=m,
                    markersize=8, linewidth=2, label=label)

    ax.axhline(0.8, color="#888", ls="--", lw=1)
    ax.text(2, 0.805, "breakdown region (r² < 0.8)", color="#666", fontsize=8, va="bottom")
    ax.axhspan(0.4, 0.8, color="#d1495b", alpha=0.05)
    ax.set_xlabel("transpiled CZ count  (routing cost →)", fontsize=11)
    ax.set_ylabel("CDR fit  r²   (linearity / coherence)", fontsize=11)
    ax.set_title("Routing-driven CDR breakdown is topology-general\n(hard-model VQC, three superconducting topologies)",
                 fontsize=11)
    ax.set_ylim(0.45, 1.02); ax.set_xlim(0, 120)
    ax.grid(True, alpha=0.25); ax.legend(fontsize=10, loc="lower left")
    fig.tight_layout()
    fig.savefig("cross_topology_r2.png", dpi=150)
    print("wrote cross_topology_r2.png")


if __name__ == "__main__":
    main()
