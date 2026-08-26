"""Method-comparison figure: ZNE vs CDR vs [[4,2,2]] on the routing-cost axis.

Reads the three ODRA-sim result CSVs and produces one figure with two panels:
  (A) <O>-error (raw dashed, mitigated solid) vs transpiled CZ, all three methods;
  (B) cost to mitigate (effective shots, log scale) — the shots-to-target view.

Writes figures/fig_method_comparison.png.
"""

from __future__ import annotations

import csv
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _read(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def _col(rows, key, cast=float):
    return [cast(r[key]) for r in rows]


def main() -> None:
    figdir = pathlib.Path("figures")
    figdir.mkdir(exist_ok=True)

    zne = sorted(_read("zne_dryrun_results.csv"), key=lambda r: float(r["transpiled_cz"]))
    cdr = sorted(_read("cdr_results.csv"), key=lambda r: float(r["transpiled_cz"]))
    qec = sorted(_read("qec422_results.csv"), key=lambda r: float(r["transpiled_cz"]))

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(12, 4.8))

    # ---- Panel A: <O>-error vs CZ ----
    zcz = _col(zne, "transpiled_cz")
    axA.plot(zcz, _col(zne, "raw_err"), "o--", color="#1f77b4", alpha=0.6, label="ZNE raw")
    axA.errorbar(zcz, _col(zne, "zne_richardson_err"),
                 yerr=_col(zne, "zne_richardson_err_std"),
                 fmt="o-", color="#1f77b4", capsize=3, label="ZNE mitigated")

    ccz = _col(cdr, "transpiled_cz")
    axA.plot(ccz, _col(cdr, "err_raw"), "s--", color="#2ca02c", alpha=0.6, label="CDR raw")
    axA.plot(ccz, _col(cdr, "err_cdr"), "s-", color="#2ca02c", label="CDR mitigated")

    qcz = _col(qec, "transpiled_cz")
    axA.plot(qcz, _col(qec, "err_bare"), "^--", color="#ff7f0e", alpha=0.6,
             label="[[4,2,2]] bare (logical)")
    axA.plot(qcz, _col(qec, "err_detected"), "^-", color="#ff7f0e",
             label="[[4,2,2]] detected (logical)")

    axA.set_xlabel("transpiled 2q-gate (CZ) cost")
    axA.set_ylabel(r"$|\langle O\rangle - \langle O\rangle_{\mathrm{ideal}}|$")
    axA.set_title("(A) Error vs routing cost\n(mitigation strongest cheap, fades with CZ)")
    axA.legend(fontsize=8, ncol=1)
    axA.grid(alpha=0.3)

    # ---- Panel B: cost (effective shots) ----
    shots = 8192
    star_zne = shots * 3                                  # 3 noise scales
    star_cdr = int(cdr[0]["effective_shots"])            # shots*(n_train+1)
    star_qec = int(qec[0]["effective_shots"])            # shots/acceptance
    methods = ["raw", "ZNE", "CDR", "[[4,2,2]]"]
    costs = [shots, star_zne, star_cdr, star_qec]
    colors = ["#7f7f7f", "#1f77b4", "#2ca02c", "#ff7f0e"]
    bars = axB.bar(methods, costs, color=colors)
    axB.set_yscale("log")
    axB.set_ylabel("effective QPU shots (log)")
    axB.set_title("(B) Cost to mitigate (cheapest rung)\nsame quality, very different price")
    for b, c in zip(bars, costs):
        axB.text(b.get_x() + b.get_width() / 2, c * 1.1, f"{c:,}",
                 ha="center", va="bottom", fontsize=8)
    axB.grid(alpha=0.3, axis="y")

    fig.suptitle("QEM/QEC method comparison on the routing-cost axis "
                 "(ODRA sim, real calibration)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = figdir / "fig_method_comparison.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
