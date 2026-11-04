"""Figures for the paper draft, read-only from the w01 campaign tables.

    KMP_DUPLICATE_LIB_OK=TRUE python paper_draft/figs/make_figs.py

Inputs (never modified): runs/odra_campaign/w01A/{cdr,zne}.csv, the offline re-analysis
outputs in research_notes/QEM combos and data reuse/prototypes/out/ (Fig. 4),
runs/odra_campaign/w01P5/cdr.csv. Outputs: paper_draft/figs/fig_*.pdf, plus
fig_numbers.txt with every number the captions quote.
"""

from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
A = REPO / "runs/odra_campaign/w01A"
P5 = REPO / "runs/odra_campaign/w01P5"
FLOOR = 1e-4

BLUE, ORANGE, AQUA, YELLOW, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6"
INK, MUTED = "#0b0b0b", "#52514e"

plt.rcParams.update({
    "font.family": "serif", "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e4e3df", "grid.linewidth": 0.5,
    "lines.linewidth": 1.2, "pdf.fonttype": 42, "savefig.bbox": "tight",
})
NUM: list[str] = []


def note(s: str) -> None:
    NUM.append(s)


# ---------------------------------------------------------------- Fig. 1: twirling
def fig_twirl() -> None:
    c = pd.read_csv(A / "cdr.csv")
    o = c[(c.fit == "ols") & (c.train_set == "near_target")]
    fig, axes = plt.subplots(1, 2, figsize=(3.5, 1.9), sharey=True)
    for ax, (rung, ncz) in zip(axes, [("star", 12), ("circular", 39)]):
        off = o[(o.rung == rung) & (o.arm == "off_copies")].set_index("eval_index").err
        tw = o[(o.rung == rung) & (o.arm == "twirl_native")].set_index("eval_index").err
        idx = off.index
        x = np.arange(len(idx))
        for xi, a, b in zip(x, off.values, tw.values):
            ax.plot([xi, xi], [max(a, FLOOR), max(b, FLOOR)],
                    color=BLUE if b < a else ORANGE, lw=1.0, zorder=1)
        ax.scatter(x, np.maximum(off.values, FLOOR), marker="o", s=16, facecolor="white",
                   edgecolor=MUTED, lw=1.0, zorder=2, label="off_copies")
        ax.scatter(x, np.maximum(tw.values, FLOOR), marker="s", s=14, color=BLUE,
                   edgecolor="white", lw=0.5, zorder=3, label="twirl_native")
        d = np.log(np.maximum(tw.values, FLOOR)) - np.log(np.maximum(off.values, FLOOR))
        wins = int((tw.values < off.values).sum())
        ax.set_yscale("log")
        ax.set_ylim(5e-5, 1.0)
        ax.set_xticks(x, [str(i) for i in idx], rotation=0)
        ax.set_xlabel("evaluation point")
        ax.set_title(f"{ncz} CZ", fontsize=8)
        ax.text(0.98, 0.98, f"mean {off.mean():.3f}$\\to${tw.mean():.3f}\n"
                f"{wins}/8 pairs, ratio {np.exp(d.mean()):.2f}", transform=ax.transAxes,
                ha="right", va="top", fontsize=6, color=INK)
        note(f"fig1 {ncz}CZ off={off.mean():.4f} tw={tw.mean():.4f} wins={wins}/8 "
             f"geo={np.exp(d.mean()):.3f}")
    axes[0].set_ylabel(r"CDR error $\varepsilon$")
    axes[1].legend(loc="lower left", frameon=False, fontsize=6, handletextpad=0.2)
    fig.savefig(HERE / "fig_twirl_pairs.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Fig. 2: ZNE
def fig_zne() -> None:
    z = pd.read_csv(A / "zne.csv")
    c = pd.read_csv(A / "cdr.csv")
    fig, axes = plt.subplots(1, 2, figsize=(3.5, 2.0), gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axes[0]
    cats = [("raw ($\\lambda{=}1$)", None, MUTED, "o"), ("genuine", "genuine", BLUE, "s"),
            ("garbage", "garbage", ORANGE, "^"), ("identity", "identity", YELLOW, "D")]
    rungs = [("star", 12), ("circular", 39)]
    rng = np.random.default_rng(0)
    for ri, (rung, ncz) in enumerate(rungs):
        for ci, (lab, var, col, mk) in enumerate(cats):
            g = z[(z.rung == rung) & (z.variant == (var or "genuine"))]
            e = g.err_raw.values if var is None else g.err_zne.values
            xc = ri * 5 + ci
            ax.scatter(xc + rng.uniform(-0.18, 0.18, len(e)), e, s=6, color=col, alpha=0.45,
                       lw=0, marker=mk)
            ax.plot([xc - 0.35, xc + 0.35], [e.mean()] * 2, color=col, lw=2.0,
                    label=lab if ri == 0 else None, solid_capstyle="round")
            note(f"fig2 {ncz}CZ {lab} mean={e.mean():.4f}")
        gen = z[(z.rung == rung) & (z.variant == "genuine")]
        ft = gen.floor_tracking.median()
        ax.text(ri * 5 + 1.5, 0.39, f"floor dist.\n{ft:.3f}", ha="center", fontsize=6,
                color=INK)
        note(f"fig2 {ncz}CZ floor_tracking_median={ft:.4f} retention={gen.retention_norm.median():.3f} "
             f"wneg={gen.w_neg.median():.4f} snr={gen.snr_lmax.median():.2f}")
        cr = c[(c.rung == rung) & (c.fit == "ols") & (c.arm == "off_copies")].err_raw.mean()
        note(f"fig2 {ncz}CZ raw_from_CDR_target(M*S)={cr:.4f}")
    ax.set_xticks([1.5, 6.5], ["12 CZ", "39 CZ"])
    ax.set_ylim(0, 0.45)
    ax.set_ylabel(r"error $\varepsilon$")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.86), frameon=False, ncol=1,
              handlelength=1.0, fontsize=6)
    # right: mean <O>(lambda) relative to ideal sign, genuine vs garbage vs identity
    ax = axes[1]
    for rung, ncz, ls in [("star", 12, "-"), ("circular", 39, "--")]:
        for var, col, mk in [("genuine", BLUE, "s"), ("garbage", ORANGE, "^"),
                             ("identity", YELLOW, "D")]:
            g = z[(z.rung == rung) & (z.variant == var)]
            s = np.sign(g.ideal.values)
            y = [np.mean(np.abs(g.ideal.values))] + [np.mean(s * g[k].values)
                                                      for k in ("ev_lam1", "ev_lam3", "ev_lam5")]
            ax.plot([0, 1, 3, 5], y, ls=ls, color=col, marker=mk, ms=3,
                    label=f"{var}" if ncz == 12 else None)
    ax.axhline(0, color=MUTED, lw=0.6)
    ax.set_xticks([0, 1, 3, 5])
    ax.set_xlabel(r"scale $\lambda$ (0 = ideal)")
    ax.set_ylabel(r"mean sign$(O_{\rm id})\langle O\rangle$")
    ax.text(5.1, 0.02, "39 CZ\n(dashed)", fontsize=6, color=MUTED, va="bottom", ha="right")
    fig.tight_layout(w_pad=0.6)
    fig.savefig(HERE / "fig_zne_window.pdf")
    plt.close(fig)
    ident = z[z.variant == "identity"].groupby("rung")[["ev_lam3", "ev_lam5"]].mean()
    note(f"fig2 identity mean ev lam3/lam5: {ident.round(3).to_dict()}")


# ---------------------------------------------------------------- Fig. 3: P5
def fig_p5() -> None:
    c = pd.read_csv(P5 / "cdr.csv")
    o = c[(c.fit == "ols") & (c.arm == "off_copies")].copy()
    o["dur_us"] = o.duration_sched_s * 1e6

    def family(r: str) -> str:
        if r == "star":
            return "base"
        if "_cz" in r:
            return "cz_pairs"
        if "_idle" in r:
            return "idle_matched"
        return "L6/L9/L13"

    o["family"] = o.rung.map(family)
    g = o.groupby(["rung", "family"]).agg(ncz=("n_cz", "first"), dur=("dur_us", "first"),
                                          raw=("err_raw", "mean"), cdr=("err", "mean"),
                                          raw_se=("err_raw", lambda s: s.std(ddof=1) / np.sqrt(len(s))),
                                          cdr_se=("err", lambda s: s.std(ddof=1) / np.sqrt(len(s))),
                                          n=("err", "size")).reset_index()
    styles = {"base": (INK, "o"), "cz_pairs": (BLUE, "s"), "idle_matched": (AQUA, "^"),
              "L6/L9/L13": (ORANGE, "D")}
    fig, axes = plt.subplots(1, 3, figsize=(7.16, 1.9))
    panels = [(axes[0], "dur", "raw", "raw_se", r"duration ($\mu$s, ASAP)", r"raw error"),
              (axes[1], "ncz", "raw", "raw_se", "CZ count", r"raw error"),
              (axes[2], "ncz", "cdr", "cdr_se", "CZ count", r"CDR error (off_copies)")]
    for ax, xk, yk, ek, xl, yl in panels:
        for fam, (col, mk) in styles.items():
            sub = g[(g.family == fam) | ((g.family == "base") & (fam != "base"))].sort_values(xk)
            if fam == "base":
                sub = g[g.family == "base"]
            ax.errorbar(sub[xk], sub[yk], yerr=sub[ek], color=col, marker=mk, ms=3.5,
                        lw=1.0 if fam != "base" else 0, elinewidth=0.7, capsize=1.5,
                        label=fam, markeredgecolor="white", markeredgewidth=0.4,
                        zorder=5 if fam == "base" else 2)
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        ax.set_ylim(bottom=0)
    axes[0].legend(frameon=False, loc="upper left", handlelength=1.2)
    fig.tight_layout(w_pad=0.8)
    fig.savefig(HERE / "fig_p5_depth.pdf")
    plt.close(fig)
    for _, r in g.sort_values(["family", "ncz", "dur"]).iterrows():
        note(f"fig3 {r.rung:12s} {r.family:13s} ncz={r.ncz} dur={r.dur:.2f}us "
             f"raw={r.raw:.4f} cdr={r.cdr:.4f} n={r.n}")


# ---------------------------------------------------------------- Fig. 4: cost curve
PROTO = REPO / "research_notes/QEM combos and data reuse/prototypes/out"


def _parse_cost() -> dict:
    """Read the equal-budget re-analysis outputs (offline prototypes, exploratory)."""
    import re
    txt = (PROTO / "q1b_prespecified.txt").read_text()
    out: dict = {}
    for block in txt.split("## ")[1:]:
        rung = block.split(":")[0].strip()
        m = re.search(r"ZNE ([0-9.]+), REM\+ZNE ([0-9.]+)", block)
        d = {"zne": float(m.group(1)), "remzne": float(m.group(2))}
        for arm in ("off_copies", "twirl_native"):
            line = re.search(rf"cost curve {arm} .*?\):(.*)", block).group(1)
            pts = re.findall(r"([0-9.]+)x:([0-9.]+)", line)
            d[arm] = [(float(a), float(b)) for a, b in pts]
        out[rung] = d
    q1 = (PROTO / "q1_equal_budget.txt").read_text()
    for rung in out:
        sec = q1.split(f"## {rung}")[1]
        out[rung]["raw24"] = float(re.search(r"raw at 24,576 sh \(expected\) ([0-9.]+)",
                                             sec).group(1))
    return out


def fig_cost() -> None:
    d = _parse_cost()
    unit = 24576
    fig, axes = plt.subplots(1, 2, figsize=(3.5, 2.25), sharey=False)
    for ax, (rung, ncz) in zip(axes, [("star", 12), ("circular", 39)]):
        r = d[rung]
        for arm, col, mk, lab in [("off_copies", MUTED, "o", "CDR off_copies"),
                                  ("twirl_native", BLUE, "s", "CDR twirl_native")]:
            x = np.array([a for a, _ in r[arm]]) * unit
            y = np.array([b for _, b in r[arm]])
            ax.plot(x, y, color=col, marker=mk, ms=3, label=lab)
        ax.scatter([unit], [r["zne"]], marker="^", color=ORANGE, s=22, zorder=5, label="ZNE")
        ax.scatter([unit], [r["remzne"]], marker="v", color=AQUA, s=22, zorder=5,
                   label="REM+ZNE")
        ax.scatter([unit], [r["raw24"]], marker="x", color=INK, s=18, zorder=5,
                   label="raw (same shots)")
        ax.axvline(unit, color=MUTED, lw=0.5, ls=":")
        ax.set_xscale("log")
        ax.set_xlabel("shots per point")
        ax.set_title(f"{ncz} CZ", fontsize=8)
        ax.set_ylim(bottom=0)
        note(f"fig4 {ncz}CZ zne={r['zne']} remzne={r['remzne']} raw24={r['raw24']} "
             f"off={r['off_copies']} tw={r['twirl_native']}")
    axes[0].set_ylabel(r"mean error $\varepsilon$")
    h, lab = axes[1].get_legend_handles_labels()
    fig.tight_layout(w_pad=0.6, rect=(0, 0.13, 1, 1))
    fig.legend(h, lab, frameon=False, fontsize=6, loc="lower center", ncol=3,
               handlelength=1.2, columnspacing=0.8, bbox_to_anchor=(0.5, -0.02))
    fig.savefig(HERE / "fig_cost_curve.pdf")
    plt.close(fig)


if __name__ == "__main__":
    fig_twirl()
    fig_zne()
    fig_p5()
    fig_cost()
    (HERE / "fig_numbers.txt").write_text("\n".join(NUM) + "\n")
    print("\n".join(NUM))
