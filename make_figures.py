"""Publication figures for the QEM routing study.

Reads the result CSVs already produced and renders three panels:

  fig_two_curves_qpu_vs_sim.png
      two_curves locked classifier: <O>-error vs transpiled CZ, on the
      ODRA-calibrated SIMULATOR (zne_dryrun_results.csv) vs REAL ODRA HARDWARE
      (hardware_results.csv), across the mitigation ladder raw / +REM / +ZNE.
      Answers "how different is QPU from sim?".

  fig_banknote_ladder.png
      banknote ansatz ladder (star<odra<simulator) pooled over depths {2,4,6}:
      <O>-error and accuracy vs transpiled CZ across raw / +DD+REM / +ZNE.
      Shows the QEM recovery + where accuracy breaks down.

  fig_mirror_fidelity.png
      task-agnostic mirror-circuit survival probability vs mirror CZ (sim).

Shot-noise floor (1/sqrt(shots)) is drawn as a reference on the error panels.
Run:  python make_figures.py
"""

from __future__ import annotations

import csv
import glob
import os
import pathlib

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
FIGDIR = ROOT / "figures"
FIGDIR.mkdir(exist_ok=True)


def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def fnum(row, key, default=np.nan):
    try:
        return float(row[key])
    except (KeyError, ValueError, TypeError):
        return default


# --------------------------------------------------------------------------- #
# Figure 1: two_curves QPU vs simulator                                         #
# --------------------------------------------------------------------------- #

def fig_two_curves():
    sim = read(ROOT / "zne_dryrun_results.csv")
    qpu = read(ROOT / "hardware_results.csv")
    # simulator: one row per pattern (DD on). QPU: prefer DD=off rows (matches the
    # sim's "raw" DD baseline for a like-for-like curve); fall back to any.
    qpu_dd_off = {r["pattern"]: r for r in qpu if str(r["dd"]).lower() == "false"}
    qpu_use = qpu_dd_off if qpu_dd_off else {r["pattern"]: r for r in qpu}

    order = ["star", "linear", "circular", "all_to_all"]
    sim_by = {r["pattern"]: r for r in sim}
    pats = [p for p in order if p in sim_by and p in qpu_use]
    cz = [fnum(sim_by[p], "transpiled_cz") for p in pats]

    def col(rows_by, keys):
        for k in keys:
            if any(k in r for r in rows_by.values()):
                return [fnum(rows_by[p], k) for p in pats]
        return [np.nan] * len(pats)

    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    shots = fnum(sim[0], "shots", 4096)
    ax.axhline(1 / np.sqrt(shots), ls=":", c="gray",
               label=f"shot-noise floor (1/√{int(shots)})")

    series = [
        ("raw", ["raw_err"], "o", "-"),
        ("+ (DD+)REM", ["ddrem_err", "rem_err"], "s", "-"),
        ("+ZNE (Richardson)", ["zne_richardson_err"], "^", "-"),
    ]
    for label, keys, mk, ls in series:
        ax.plot(cz, col(sim_by, keys), ls, marker=mk, color="tab:blue", alpha=0.55,
                label=f"sim  {label}")
        ax.plot(cz, col(qpu_use, keys), ls, marker=mk, color="tab:red",
                label=f"QPU {label}")
    for p, x in zip(pats, cz):
        ax.annotate(p, (x, 0.0), textcoords="offset points", xytext=(0, -22),
                    ha="center", fontsize=8, rotation=30, color="dimgray")
    ax.set_xlabel("transpiled CZ (routing cost)")
    ax.set_ylabel(r"$|\langle O\rangle_{\mathrm{noisy}}-\langle O\rangle_{\mathrm{ideal}}|$")
    ax.set_title("two_curves: simulator vs real ODRA — error vs routing cost")
    ax.set_ylim(bottom=-0.02)
    ax.legend(fontsize=8, ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = FIGDIR / "fig_two_curves_qpu_vs_sim.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
# Figure 2: banknote ansatz ladder (sim, pooled over depths)                    #
# --------------------------------------------------------------------------- #

def fig_banknote():
    files = sorted(glob.glob(str(ROOT / "banknote_study" / "banknote_zne_d*.csv")))
    rows = []
    for fp in files:
        rows.extend(read(fp))
    if not rows:
        return None
    rows.sort(key=lambda r: fnum(r, "transpiled_cz"))
    cz = [fnum(r, "transpiled_cz") for r in rows]
    names = [r["ansatz"] for r in rows]
    colors = {"star": "tab:green", "odra": "tab:orange", "simulator": "tab:purple"}

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 5.0))
    shots = fnum(rows[0], "shots", 4096)

    # left: <O>-error vs CZ
    a1.axhline(1 / np.sqrt(shots), ls=":", c="gray", label="shot-noise floor")
    for key, mk, lab in [("everr_raw", "o", "raw"),
                         ("everr_ddrem", "s", "+DD+REM"),
                         ("everr_zne", "^", "+ZNE")]:
        a1.plot(cz, [fnum(r, key) for r in rows], marker=mk, label=lab)
    for r, x in zip(rows, cz):
        a1.annotate(f"{r['ansatz'][:4]}·d{r['depth']}", (x, fnum(r, 'everr_raw')),
                    fontsize=7, xytext=(0, 5), textcoords="offset points", ha="center")
    a1.set_xlabel("transpiled CZ"); a1.set_ylabel(r"$|\langle O\rangle$ error$|$")
    a1.set_title("banknote (sim): expectation-value error vs routing cost")
    a1.legend(fontsize=9); a1.grid(alpha=0.3)

    # right: accuracy vs CZ
    a2.axhline(0.5, ls=":", c="gray", label="chance")
    for key, mk, lab in [("acc_ideal", "D", "ideal"),
                         ("acc_raw", "o", "raw"),
                         ("acc_ddrem", "s", "+DD+REM"),
                         ("acc_zne", "^", "+ZNE")]:
        a2.plot(cz, [fnum(r, key) for r in rows], marker=mk, label=lab)
    a2.set_xlabel("transpiled CZ"); a2.set_ylabel("accuracy")
    a2.set_title("banknote (sim): accuracy vs routing cost")
    a2.set_ylim(0.45, 1.0); a2.legend(fontsize=9); a2.grid(alpha=0.3)

    fig.tight_layout()
    out = FIGDIR / "fig_banknote_ladder.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
# Figure 2b: banknote on REAL QPU (full fold, 275 pts)                          #
# --------------------------------------------------------------------------- #

def fig_banknote_qpu():
    fp = ROOT / "banknote_study" / "banknote_hardware_fullfold.csv"
    if not fp.exists():
        return None
    rows = [r for r in read(fp) if str(r.get("dd", "False")).lower() == "false"]
    rows.sort(key=lambda r: fnum(r, "transpiled_cz"))
    if not rows:
        return None
    cz = [fnum(r, "transpiled_cz") for r in rows]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 5.0))
    shots = fnum(rows[0], "shots", 4096)

    a1.axhline(1 / np.sqrt(shots), ls=":", c="gray", label="shot-noise floor")
    for key, mk, lab in [("raw_err", "o", "raw"),
                         ("rem_err", "s", "+REM"),
                         ("zne_richardson_err", "^", "+ZNE")]:
        a1.plot(cz, [fnum(r, key) for r in rows], marker=mk, label=lab)
    for r, x in zip(rows, cz):
        a1.annotate(f"{r['ansatz'][:4]}·d{r['depth']}", (x, fnum(r, 'raw_err')),
                    fontsize=7, xytext=(0, 5), textcoords="offset points", ha="center")
    a1.set_xlabel("transpiled CZ"); a1.set_ylabel(r"$|\langle O\rangle$ error$|$")
    a1.set_title("banknote (real ODRA, full fold): error vs routing cost")
    a1.legend(fontsize=9); a1.grid(alpha=0.3)

    a2.axhline(0.56, ls=":", c="gray", label="majority floor (0.56)")
    for key, mk, lab in [("acc_ideal", "D", "ideal"),
                         ("acc_raw", "o", "raw"),
                         ("acc_zne_richardson", "^", "+ZNE")]:
        a2.plot(cz, [fnum(r, key) for r in rows], marker=mk, label=lab)
    for r, x in zip(rows, cz):
        a2.annotate(f"{r['ansatz'][:4]}·d{r['depth']}", (x, fnum(r, 'acc_raw')),
                    fontsize=7, xytext=(0, -12), textcoords="offset points", ha="center")
    a2.set_xlabel("transpiled CZ"); a2.set_ylabel("accuracy")
    a2.set_title("banknote (real ODRA, full fold): accuracy vs routing cost")
    a2.set_ylim(0.5, 0.95); a2.legend(fontsize=9); a2.grid(alpha=0.3)

    fig.tight_layout()
    out = FIGDIR / "fig_banknote_qpu.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
# Figure 3: mirror-circuit fidelity                                             #
# --------------------------------------------------------------------------- #

def fig_mirror():
    fp = ROOT / "banknote_study" / "banknote_mirror_fidelity.csv"
    if not fp.exists():
        return None
    rows = sorted(read(fp), key=lambda r: fnum(r, "mirror_cz"))
    cz = [fnum(r, "mirror_cz") for r in rows]
    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    ax.plot(cz, [fnum(r, "F_survival_raw") for r in rows], "o-", label="DD off")
    ax.plot(cz, [fnum(r, "F_survival_dd") for r in rows], "s-", label="DD on")
    for r, x in zip(rows, cz):
        ax.annotate(f"{r['ansatz'][:4]}·d{r['depth']}", (x, fnum(r, 'F_survival_dd')),
                    fontsize=7, xytext=(0, 5), textcoords="offset points", ha="center")
    ax.set_xlabel("mirror CZ (2 × ansatz CZ)")
    ax.set_ylabel(r"survival probability  $P(|0\rangle^{\otimes n})$")
    ax.set_title("Mirror-circuit fidelity vs routing cost (sim)")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    out = FIGDIR / "fig_mirror_fidelity.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def main():
    made = []
    for fn in (fig_two_curves, fig_banknote, fig_banknote_qpu, fig_mirror):
        try:
            out = fn()
            if out:
                made.append(out)
                print(f"wrote {out}")
        except FileNotFoundError as e:
            print(f"skip {fn.__name__}: missing {e}")
    print(f"\n{len(made)} figure(s) in {FIGDIR}")


if __name__ == "__main__":
    main()
