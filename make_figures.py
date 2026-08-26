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
    # long format: one row per (ansatz, depth, dd) with a single F_survival column.
    rows = read(fp)

    def is_dd(r):
        return str(r.get("dd", "")).lower() in ("true", "1")

    def series(dd_flag):
        sub = sorted((r for r in rows if is_dd(r) == dd_flag),
                     key=lambda r: fnum(r, "mirror_cz"))
        return sub, [fnum(r, "mirror_cz") for r in sub], [fnum(r, "F_survival") for r in sub]

    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    off_rows, off_cz, off_f = series(False)
    on_rows, on_cz, on_f = series(True)
    ax.plot(off_cz, off_f, "o-", label="DD off")
    ax.plot(on_cz, on_f, "s-", label="DD on")
    ax.axhline(2 ** -5, ls=":", c="gray", label=r"floor depol. $2^{-5}$")
    for r, x, y in zip(off_rows, off_cz, off_f):
        ax.annotate(f"{r['ansatz'][:4]}·d{r['depth']}", (x, y),
                    fontsize=7, xytext=(0, 5), textcoords="offset points", ha="center")
    ax.set_xlabel("mirror CZ (2 × ansatz CZ)")
    ax.set_ylabel(r"survival probability  $P(|0\rangle^{\otimes n})$")
    ax.set_title("Banknote mirror-circuit fidelity vs routing cost (QPU)")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    out = FIGDIR / "fig_mirror_fidelity.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
# Month-2 Garnet campaign figures (real 20q hardware)                            #
# --------------------------------------------------------------------------- #

_PL_STYLE = {"optimal": ("tab:green", "o"), "adverse": ("tab:red", "s")}


def _ladder(rows, placement):
    """(cz, ...) sorted by CZ for one placement."""
    sub = sorted((r for r in rows if r["placement"] == placement),
                 key=lambda r: fnum(r, "transpiled_cz"))
    return sub


def fig_garnet_routing():
    """<O>-error vs routing cost, optimal vs adverse, raw -> +ZNE. The thesis."""
    fp = ROOT / "garnet_full_results.csv"
    if not fp.exists():
        return None
    rows = read(fp)
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    shots = fnum(rows[0], "shots", 4096)
    ax.axhline(1 / np.sqrt(shots), ls=":", c="gray", label=f"shot-noise floor (1/√{int(shots)})")
    for pl, (c, mk) in _PL_STYLE.items():
        sub = _ladder(rows, pl)
        if not sub:
            continue
        cz = [fnum(r, "transpiled_cz") for r in sub]
        ax.plot(cz, [fnum(r, "err_raw") for r in sub], mk + "--", color=c, alpha=0.5,
                label=f"{pl} raw")
        ax.plot(cz, [fnum(r, "err_zne") for r in sub], mk + "-", color=c,
                label=f"{pl} +ZNE")
        for r, x in zip(sub, cz):
            ax.annotate(r["pattern"][:4], (x, fnum(r, "err_raw")), fontsize=7,
                        xytext=(0, 5), textcoords="offset points", ha="center", color=c)
    ax.set_xlabel("transpiled CZ (routing cost)")
    ax.set_ylabel(r"$|\langle O\rangle_{\mathrm{noisy}}-\langle O\rangle_{\mathrm{ideal}}|$")
    ax.set_title("Garnet (20q): expectation-value error vs routing cost — optimal vs adverse")
    ax.set_ylim(bottom=-0.01)
    ax.legend(fontsize=8, ncol=2); ax.grid(alpha=0.3)
    fig.tight_layout()
    out = FIGDIR / "fig_garnet_routing_ladder.png"
    fig.savefig(out, dpi=150); plt.close(fig)
    return out


def fig_garnet_methods():
    """Fair method comparison: reduction factor (raw / mitigated) each method
    achieved against ITS OWN raw. ZNE (4096 shots) and CDR (2048 shots) ran as
    separate jobs with different baselines, so absolute mitigated values are not
    comparable across methods -- the within-run reduction ratio is."""
    zfp, cfp = ROOT / "garnet_full_results.csv", ROOT / "garnet_cdr_results.csv"
    if not (zfp.exists() and cfp.exists()):
        return None
    zne = {(r["placement"], r["pattern"]): r for r in read(zfp)}
    cdr = read(cfp)
    cdr.sort(key=lambda r: (r["placement"], fnum(r, "transpiled_cz")))

    def ratio(num, den):
        return num / den if den and den > 0 else np.nan

    labels, zred, cred = [], [], []
    for r in cdr:
        z = zne.get((r["placement"], r["pattern"]))
        labels.append(f"{r['placement'][:3]}\n{r['pattern'][:4]}\n{int(fnum(r,'transpiled_cz'))}CZ")
        zred.append(ratio(fnum(z, "err_raw"), fnum(z, "err_zne")) if z else np.nan)
        cred.append(ratio(fnum(r, "err_raw"), fnum(r, "err_cdr")))
    x = np.arange(len(labels)); w = 0.36
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    b1 = ax.bar(x - w / 2, zred, w, label="ZNE", color="tab:blue")
    b2 = ax.bar(x + w / 2, cred, w, label="CDR", color="tab:orange")
    ax.bar_label(b1, fmt="%.1f×", fontsize=8, padding=2)
    ax.bar_label(b2, fmt="%.1f×", fontsize=8, padding=2)
    ax.axhline(1.0, ls=":", c="gray", label="no improvement (1×)")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel(r"error-reduction factor  $|\langle O\rangle|_{\mathrm{raw}}/|\langle O\rangle|_{\mathrm{mit}}$")
    ax.set_title("Garnet (20q): fair method comparison — reduction vs each method's own raw (higher = better)")
    ax.legend(); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    out = FIGDIR / "fig_garnet_methods.png"
    fig.savefig(out, dpi=150); plt.close(fig)
    return out


def fig_garnet_mirror():
    """Task-agnostic mirror survival vs routing cost, optimal vs adverse."""
    fp = ROOT / "garnet_mirror_results.csv"
    if not fp.exists():
        return None
    rows = read(fp)
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    for pl, (c, mk) in _PL_STYLE.items():
        sub = sorted((r for r in rows if r["placement"] == pl),
                     key=lambda r: fnum(r, "mirror_cz"))
        if not sub:
            continue
        cz = [fnum(r, "mirror_cz") for r in sub]
        f = [fnum(r, "survival") for r in sub]
        err = [fnum(r, "survival_std") for r in sub]
        ax.errorbar(cz, f, yerr=err, fmt=mk + "-", color=c, capsize=3, label=pl)
        for r, x, y in zip(sub, cz, f):
            ax.annotate(r["pattern"][:4], (x, y), fontsize=7, xytext=(0, 6),
                        textcoords="offset points", ha="center", color=c)
    ax.axhline(2 ** -5, ls=":", c="gray", label=r"depol. floor $2^{-5}$")
    ax.set_xlabel("mirror CZ (2 × ansatz CZ)")
    ax.set_ylabel(r"survival $P(|0\rangle^{\otimes n})$")
    ax.set_title("Garnet (20q): mirror-circuit fidelity vs routing cost")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    out = FIGDIR / "fig_garnet_mirror.png"
    fig.savefig(out, dpi=150); plt.close(fig)
    return out


def fig_garnet_qec422():
    """[[4,2,2]] detection: bare vs detected logical error + acceptance vs depth."""
    fp = ROOT / "garnet_qec422_results.csv"
    if not fp.exists():
        return None
    rows = read(fp)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 5.0))
    for pl, (c, mk) in _PL_STYLE.items():
        sub = sorted((r for r in rows if r["placement"] == pl),
                     key=lambda r: fnum(r, "transpiled_cz"))
        if not sub:
            continue
        cz = [fnum(r, "transpiled_cz") for r in sub]
        a1.plot(cz, [fnum(r, "err_bare") for r in sub], mk + "--", color=c, alpha=0.5,
                label=f"{pl} bare")
        a1.errorbar(cz, [fnum(r, "err_detected") for r in sub],
                    yerr=[fnum(r, "err_detected_std") for r in sub],
                    fmt=mk + "-", color=c, capsize=3, label=f"{pl} detected")
        a2.plot(cz, [fnum(r, "acceptance") for r in sub], mk + "-", color=c, label=pl)
    a1.set_xlabel("transpiled CZ"); a1.set_ylabel(r"logical $|\langle Z_L\rangle$ error$|$")
    a1.set_title("[[4,2,2]] on Garnet: post-selection lowers logical error")
    a1.legend(fontsize=8); a1.grid(alpha=0.3)
    a2.axhline(0.5, ls=":", c="gray", label="½ shots kept")
    a2.set_xlabel("transpiled CZ"); a2.set_ylabel("acceptance (kept fraction)")
    a2.set_title("[[4,2,2]] detection cost: acceptance vs depth")
    a2.set_ylim(0, 1); a2.legend(fontsize=8); a2.grid(alpha=0.3)
    fig.tight_layout()
    out = FIGDIR / "fig_garnet_qec422.png"
    fig.savefig(out, dpi=150); plt.close(fig)
    return out


def main():
    made = []
    for fn in (fig_two_curves, fig_banknote, fig_banknote_qpu, fig_mirror,
               fig_garnet_routing, fig_garnet_methods, fig_garnet_mirror,
               fig_garnet_qec422):
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
