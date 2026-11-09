"""Figures for paper draft v3, one per step of the narrative (exploratory figures).

Data: runs/odra_campaign/* and paper_analysis/out/*. Hardware data only read, never sent.

    python -m paper_analysis.paper_figs_v3            # Polish labels (draft)
    python -m paper_analysis.paper_figs_v3 --lang en  # English labels (paper)

Writes paper_draft/v3/figs/fig{1..6}_*.{pdf,png}.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
RUNS = REPO / "runs" / "odra_campaign"
OUT = REPO / "paper_analysis" / "out"
FIGS = REPO / "paper_draft" / "v3" / "figs"

# Validated categorical palette (dataviz reference, light surface); fixed entity mapping.
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
C_CDR, C_TWIRL, C_ZNE, C_GARB, C_RAW = BLUE, ORANGE, AQUA, YELLOW, INK2

LANG = "pl"


def T(pl: str, en: str) -> str:
    """Label in the selected language."""
    return pl if LANG == "pl" else en


def style() -> None:
    """Recessive axes, thin marks, sizes for a two-column figure."""
    plt.rcParams.update({
        "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
        "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7.5,
        "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
        "ytick.color": INK2, "text.color": INK, "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.6, "axes.axisbelow": True, "lines.linewidth": 1.5,
        "legend.frameon": False, "figure.dpi": 200, "savefig.bbox": "tight",
        "pdf.fonttype": 42,
    })


def save(fig, name: str) -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIGS / f"{name}.{ext}")
    plt.close(fig)
    print("wrote", FIGS / f"{name}.pdf")


def panel(ax, letter: str) -> None:
    ax.text(-0.14, 1.04, f"({letter})", transform=ax.transAxes, fontweight="bold", va="bottom")


# ---------------------------------------------------------------------------------------
# Fig. 1: the device as a contraction (decision survey, w04m)

FAMILY = {"star": "ladder", "linear": "ladder", "circular": "ladder", "all_to_all": "ladder",
          "star_cz24": "cz", "star_cz36": "cz", "star_cz52": "cz",
          "star_idle24": "idle", "star_idle36": "idle", "star_idle52": "idle",
          "star_L6": "depth", "star_L9": "depth", "star_L13": "depth"}


def asap_us(qasm: str, t_cz: float = 60e-9, t_prx: float = 20e-9) -> float:
    """ASAP duration of a native QASM3 circuit in µs, delays included.

    The ``duration_s`` stored with the survey records leaves out inserted delays, so the
    idle rungs would all show the base duration; this recomputes it from the circuit.
    """
    t: dict[str, float] = collections.defaultdict(float)
    in_gate = False
    for line in qasm.split("\n"):
        line = line.strip()
        if line.startswith("gate"):
            in_gate = True
            continue
        if in_gate:
            in_gate = not line.startswith("}")
            continue
        if line.startswith("cz"):
            dt = t_cz
        elif line.startswith("r("):
            dt = t_prx
        elif line.startswith("delay"):
            dt = float(re.match(r"delay\[([0-9.e+-]+)s\]", line).group(1))
        else:
            continue
        qs = [a or b for a, b in re.findall(r"\$(\d+)|q\[(\d+)\]", line)]
        start = max(t[q] for q in qs)
        for q in qs:
            t[q] = start + dt
    return 1e6 * max(t.values())


def survey() -> pd.DataFrame:
    """Per-rung slope s, offset c and median ASAP duration from the decision survey."""
    d = pd.read_csv(RUNS / "w04m" / "margin.csv")
    dur: dict[str, list[float]] = {}
    for line in open(RUNS / "w04m" / "counts.jsonl"):
        r = json.loads(line)
        if r.get("kind") == "margin":
            dur.setdefault(r["rung"], []).append(asap_us(r["qasm3"]))
    rows = []
    for rung, g in d.groupby("rung"):
        s, c = np.polyfit(g.ideal, g.raw, 1)
        rows.append(dict(rung=rung, n_cz=int(g.n_cz.iloc[0]), s=s, c=c,
                         dur_us=float(np.median(dur[rung])), family=FAMILY[rung]))
    return pd.DataFrame(rows)


def fig1() -> None:
    d = pd.read_csv(RUNS / "w04m" / "margin.csv")
    sv = survey()
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.7))
    ax = axs[0]
    ladder = [("star", 12, BLUE), ("linear", 30, AQUA), ("circular", 39, YELLOW),
              ("all_to_all", 57, ORANGE)]
    xs = np.linspace(-0.8, 0.8, 2)
    for rung, cz, col in ladder:
        g = d[d.rung == rung]
        s, c = np.polyfit(g.ideal, g.raw, 1)
        ax.scatter(g.ideal, g.raw, s=6, color=col, alpha=0.45, linewidths=0)
        ax.plot(xs, s * xs + c, color=col)
        dy = {39: 0.035, 57: -0.035}.get(cz, 0.0)
        ax.text(0.82, s * 0.82 + c + dy, f"{cz} CZ: s = {s:.2f}".replace(".", "," if LANG == "pl" else "."),
                color=INK, fontsize=7, va="center")
    ax.plot(xs, xs, color=INK2, lw=0.8, ls="--")
    ax.text(0.38, 0.62, T("brak szumu", "noiseless"), color=INK2, fontsize=7, rotation=38)
    ax.set_xlim(-0.85, 1.25)
    ax.set_xlabel(r"$O_\mathrm{ideal}$")
    ax.set_ylabel(T(r"$O$ zmierzone (ODRA)", r"measured $O$ (ODRA)"))
    ax.set_title(T("Urządzenie ściska wynik ku zeru", "The device contracts the output"), loc="left")
    panel(ax, "a")

    ax = axs[1]
    fam = [("ladder", T("drabina (routing)", "ladder (routing)"), BLUE, "o"),
           ("cz", T("+ pary CZ·CZ", "+ CZ·CZ pairs"), ORANGE, "s"),
           ("idle", T("+ czekanie", "+ idle"), AQUA, "^"),
           ("depth", T("głębsze modele L6–L13", "deeper models L6–L13"), YELLOW, "D")]
    for key, lab, col, mk in fam:
        g = sv[sv.family == key].sort_values("dur_us")
        ax.plot(g.dur_us, g.s, color=col, marker=mk, ms=5, lw=1.0, label=lab,
                markeredgecolor="white", markeredgewidth=0.8)
    ax.set_xlabel(T("czas trwania obwodu [µs]", "circuit duration [µs]"))
    ax.set_ylabel(T("retencja sygnału s", "signal retention s"))
    ax.set_ylim(0, 1)
    ax.set_title(T("Ściśnięcie rośnie z czasem trwania", "Contraction grows with duration"), loc="left")
    ax.legend(loc="upper right")
    panel(ax, "b")
    fig.tight_layout()
    save(fig, "fig1_contraction")


# ---------------------------------------------------------------------------------------
# Fig. 2: ZNE collapses onto the garbage floor

def fig2() -> None:
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.6), sharey=True)
    for ax, (win, rung, cz), letter in zip(axs, [("w01A", "star", 12), ("w01A", "circular", 39)], "ab"):
        z = pd.read_csv(RUNS / win / "zne.csv")
        z = z[z.rung == rung]
        lam = [1, 3, 5]
        for var, col, lab in [("garbage", C_GARB, "garbage"), ("genuine", C_ZNE, T("ZNE (prawdziwy folding)", "ZNE (genuine folding)"))]:
            g = z[z.variant == var]
            for i, (_, r) in enumerate(g.iterrows()):
                ax.plot(lam, [r.ev_lam1, r.ev_lam3, r.ev_lam5], color=col, lw=1.0, alpha=0.9,
                        marker="o", ms=3, label=lab if i == 0 else None)
        g = z[z.variant == "genuine"]
        ax.scatter(np.zeros(len(g)), g.ideal, marker="*", s=40, color=INK, zorder=5,
                   label=T("wartość idealna", "ideal value"))
        ax.axhline(0, color=INK2, lw=0.6)
        ax.set_xticks([0, 1, 3, 5])
        ax.set_xlabel(T(r"wzmocnienie szumu $\lambda$", r"noise scale $\lambda$"))
        ax.set_title(f"{cz} CZ", loc="left")
        panel(ax, letter)
    axs[0].set_ylabel(r"$\langle O\rangle$")
    axs[1].text(5.1, 0.02, T("obwody λ = 5\nna podłodze garbage", "λ = 5 circuits\non the garbage floor"),
                fontsize=7, color=INK, va="bottom")
    h, lab = axs[0].get_legend_handles_labels()
    axs[1].legend(h, lab, loc="lower right", fontsize=7)
    fig.tight_layout()
    save(fig, "fig2_zne_collapse")


# ---------------------------------------------------------------------------------------
# Fig. 3: CDR frontier and the r² trap

def frontier_rows() -> pd.DataFrame:
    f = pd.read_csv(OUT / "frontier_rungs.csv")
    f = f[f.window.str.startswith(("w01", "w02"))]
    c = pd.read_csv(OUT / "decision_cells.csv")
    return f.merge(c[["window", "rung", "arm", "r2"]], on=["window", "rung", "arm"], how="left")


def fig3() -> None:
    f = frontier_rows()
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.7))
    ax = axs[0]
    rng = np.random.default_rng(0)
    for arm, col, mk, lab in [("off_copies", C_CDR, "o", T("CDR bez twirlingu", "CDR, untwirled")),
                              ("twirl_native", C_TWIRL, "s", T("CDR z twirlingiem", "CDR, twirled"))]:
        g = f[f.arm == arm]
        x, y = g.n_cz.values.astype(float), np.log(g.gain_geo.values)
        ax.scatter(x, g.gain_geo, color=col, marker=mk, s=22, edgecolors="white", linewidths=0.8,
                   zorder=4, label=lab)
        b, a = np.polyfit(x, y, 1)
        xx = np.linspace(8, 80, 100)
        if arm == "off_copies":
            boot = []
            for _ in range(2000):
                i = rng.integers(0, len(x), len(x))
                if len(set(x[i])) > 1:
                    boot.append(np.polyfit(x[i], y[i], 1))
            band = np.array([np.exp(bb[1] + bb[0] * xx) for bb in boot])
            ax.fill_between(xx, np.percentile(band, 2.5, 0), np.percentile(band, 97.5, 0),
                            color=col, alpha=0.12, linewidths=0)
            xc = -a / b
            ax.plot(xx[xx <= 57], np.exp(a + b * xx[xx <= 57]), color=col)
            ax.plot(xx[xx >= 57], np.exp(a + b * xx[xx >= 57]), color=col, ls="--")
            ax.plot([xc], [1], marker="o", ms=6, mfc="white", mec=col, mew=1.5, zorder=5)
            ax.annotate(T(f"przewaga znika\n≈ {xc:.0f} CZ", f"gain vanishes\n≈ {xc:.0f} CZ"),
                        (xc, 1), (xc - 22, 0.62), fontsize=7, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6))
        else:
            ax.plot(xx[xx <= 57], np.exp(a + b * xx[xx <= 57]), color=col)
    ax.axhline(1, color=INK2, lw=0.8)
    ax.text(9, 1.06, T("CDR = raw", "CDR = raw"), fontsize=7, color=INK2)
    ax.axvspan(57, 80, color=GRID, alpha=0.5, lw=0)
    ax.text(58.5, 0.42, T("poza drabiną", "beyond ladder"), fontsize=7, color=INK2)
    ax.set_yscale("log")
    ax.set_yticks([0.5, 1, 2, 4, 8])
    ax.set_yticklabels(["0,5" if LANG == "pl" else "0.5", "1", "2", "4", "8"])
    ax.set_xlim(8, 80)
    ax.set_xlabel(T("bramki CZ", "CZ gates"))
    ax.set_ylabel(T("przewaga: błąd raw / błąd CDR", "gain: raw error / CDR error"))
    ax.set_title(T("CDR opłaca się do ok. 60 CZ", "CDR pays up to about 60 CZ"), loc="left")
    ax.legend(loc="upper right")
    panel(ax, "a")

    ax = axs[1]
    for arm, col, mk in [("off_copies", C_CDR, "o"), ("twirl_native", C_TWIRL, "s")]:
        g = f[f.arm == arm]
        ax.scatter(g.n_cz, g.r2, color=col, marker=mk, s=22, edgecolors="white", linewidths=0.8, zorder=4)
    ax.axhline(0.8, color=INK2, lw=0.8, ls="--")
    ax.text(41, 0.81, T("dawny próg r² = 0,8", "former threshold r² = 0.8"), fontsize=7, color=INK2, va="bottom")
    ax.set_xlim(8, 60)
    ax.set_ylim(0.3, 1.02)
    ax.set_xlabel(T("bramki CZ", "CZ gates"))
    ax.set_ylabel(T("r² dopasowania CDR", "CDR fit r²"))
    ax.set_title(T("r² ogłasza załamanie za wcześnie", "r² declares breakdown too early"), loc="left")
    g = f[(f.arm == "off_copies") & (f.n_cz == 57)].iloc[0]
    ax.annotate(T(f"r² = {g.r2:.2f}, a CDR wciąż\n{g.gain_geo:.1f}× lepsze od raw".replace(".", ","),
                  f"r² = {g.r2:.2f}, yet CDR still\n{g.gain_geo:.1f}× better than raw"),
                (57, g.r2), (33, 0.36), fontsize=7, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6))
    panel(ax, "b")
    fig.tight_layout()
    save(fig, "fig3_cdr_frontier")


# ---------------------------------------------------------------------------------------
# Fig. 4: duration drives raw error, CZ drives the CDR residual (identity insertion)

def fig4() -> None:
    c = pd.read_csv(RUNS / "w01P5" / "cdr.csv")
    c = c[(c.fit == "ols") & (c.arm == "off_copies") & (c.rung.str.match(r"^star(_cz|_idle|$)"))]
    c["mode"] = np.where(c.rung.str.contains("cz"), "cz", np.where(c.rung.str.contains("idle"), "idle", "base"))
    c["dur"] = 1e6 * c.duration_sched_s
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.6), sharey=True)
    for ax, col_err, title, letter in [
            (axs[0], "err_raw", T("Błąd surowy rośnie z czasem", "Raw error grows with duration"), "a"),
            (axs[1], "err", T("Po CDR zostaje błąd od CZ", "After CDR, a CZ-linked error remains"), "b")]:
        base = c[c["mode"] == "base"]
        for mode, col, mk, lab in [("idle", AQUA, "^", T("+ czekanie (12 CZ)", "+ idle (12 CZ)")),
                                   ("cz", ORANGE, "s", T("+ pary CZ·CZ (24–52 CZ)", "+ CZ·CZ pairs (24–52 CZ)"))]:
            g = pd.concat([base, c[c["mode"] == mode]])
            m = g.groupby("rung").agg(dur=("dur", "median"), e=(col_err, "mean")).sort_values("dur")
            ax.scatter(g.dur + (0.03 if mode == "cz" else -0.03), g[col_err], s=7, color=col, alpha=0.35, linewidths=0)
            ax.plot(m.dur, m.e, color=col, marker=mk, ms=5, markeredgecolor="white", markeredgewidth=0.8, label=lab)
        ax.set_xlabel(T("czas trwania obwodu [µs]", "circuit duration [µs]"))
        ax.set_title(title, loc="left")
        panel(ax, letter)
    axs[0].set_ylabel(r"$|\langle O\rangle - O_\mathrm{ideal}|$")
    axs[0].set_ylim(0, 0.35)
    axs[1].legend(loc="upper left")
    fig.tight_layout()
    save(fig, "fig4_duration_vs_cz")


# ---------------------------------------------------------------------------------------
# Fig. 5: what the calibrated model misses, and what twirling removes

def fig5() -> None:
    v = pd.read_csv(OUT / "sim_vs_hw_cells.csv")
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.7))
    ax = axs[0]
    for meth, col, mk, lab in [("raw", C_RAW, "o", "raw"),
                               ("CDR", C_CDR, "o", T("CDR bez twirlingu", "CDR, untwirled")),
                               ("CDR+twirl", C_TWIRL, "s", T("CDR z twirlingiem", "CDR, twirled"))]:
        g = v[v.method == meth]
        ax.scatter(g.err_sim, g.err_hw, color=col, marker=mk, s=20, edgecolors="white", linewidths=0.8,
                   label=lab, zorder=4)
    lim = [0.003, 0.4]
    ax.plot(lim, lim, color=INK2, lw=0.8, ls="--")
    ax.text(0.2, 0.13, T("sprzęt = model", "hardware = model"), fontsize=7, color=INK2, rotation=38)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel(T("błąd w symulacji z kalibracji", "error, calibrated simulation"))
    ax.set_ylabel(T("błąd na ODRZE", "error on ODRA"))
    ax.set_title(T("Model nie widzi błędu, który psuje CDR", "The model misses what breaks CDR"), loc="left")
    ax.legend(loc="upper left")
    panel(ax, "a")

    ax = axs[1]
    rows = [(12, "12/12", 0.019, 0.031), (30, "12/30", 0.029, 0.036),
            (39, "15/39", 0.025, 0.032), (57, "30/57", 0.082, 0.088)]
    xs = np.arange(len(rows))
    for i, (cz, frac, lg, nt) in enumerate(rows):
        ax.plot([i, i], [lg, nt], color=GRID, lw=2, zorder=1)
    ax.scatter(xs, [r[2] for r in rows], color=AQUA, marker="o", s=28, edgecolors="white", linewidths=0.8,
               zorder=3, label=T("twirling logiczny (bez CZ routingu)", "logical twirling (routing CZ untwirled)"))
    ax.scatter(xs, [r[3] for r in rows], color=C_TWIRL, marker="s", s=28, edgecolors="white", linewidths=0.8,
               zorder=3, label=T("twirling natywny (każda CZ)", "native twirling (every CZ)"))
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{r[0]} CZ\n({r[1]})" for r in rows])
    ax.set_xlabel(T("szczebel (CZ twirlowane: logiczny/natywny)", "rung (CZ twirled: logical/native)"))
    ax.set_ylabel(T("błąd CDR", "CDR error"))
    ax.set_ylim(0, 0.11)
    ax.set_title(T("Twirlowanie CZ z routingu nic nie daje", "Twirling routing CZs adds nothing"), loc="left")
    ax.legend(loc="upper left")
    panel(ax, "b")
    fig.tight_layout()
    save(fig, "fig5_beyond_contraction")


# ---------------------------------------------------------------------------------------
# Fig. 6: decisions change only where the noiseless classifier is guessing

BINS = [0, 0.05, 0.10, 0.20, 0.40, 1.01]


def binned(margin, ok, flips):
    rows = []
    for lo, hi in zip(BINS[:-1], BINS[1:]):
        m = (margin >= lo) & (margin < hi)
        rows.append((m.sum(), ok[m].mean(), flips[m].sum()))
    return rows


def fig6() -> None:
    hw = pd.read_csv(RUNS / "w04m" / "margin.csv")
    sim = pd.concat([pd.read_csv(OUT / f"decisions_sim_{n}.csv") for n in ("two_curves", "linear", "manifold")])
    sim_di = np.where(sim.ideal >= 0, 1, -1)
    sim_dr = np.where(sim.raw >= 0, 1, -1)
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.7))
    labels = ["<0,05", "0,05–0,1", "0,1–0,2", "0,2–0,4", ">0,4"]
    if LANG == "en":
        labels = [x.replace(",", ".") for x in labels]
    xs = np.arange(len(labels))
    ax = axs[0]
    hwb = binned(hw.ideal.abs().values, (hw.dec_ideal == hw.label).values, (hw.dec_raw != hw.dec_ideal).values)
    smb = binned(sim.ideal.abs().values, sim_di == sim.label.values, sim_dr != sim_di)
    w = 0.38
    ax.bar(xs - w / 2 - 0.01, [r[2] for r in hwb], width=w, color=BLUE, label=T("ODRA (1300 decyzji)", "ODRA (1300 decisions)"))
    ax.bar(xs + w / 2 + 0.01, [r[2] for r in smb], width=w, color=YELLOW, label=T("symulacja, 3 zbiory (1900)", "simulation, 3 datasets (1900)"))
    for i, r in enumerate(hwb):
        ax.text(i - w / 2, r[2] + 1, str(r[2]), ha="center", fontsize=6.5)
    for i, r in enumerate(smb):
        ax.text(i + w / 2, r[2] + 1, str(r[2]), ha="center", fontsize=6.5)
    ax.set_xticks(xs); ax.set_xticklabels(labels)
    ax.set_xlabel(T(r"margines $|O_\mathrm{ideal}|$", r"margin $|O_\mathrm{ideal}|$"))
    ax.set_ylabel(T("decyzje zmienione przez szum", "decisions flipped by noise"))
    ax.set_title(T("Szum zmienia decyzje tylko przy granicy", "Noise flips decisions only near the boundary"), loc="left")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right")
    panel(ax, "a")

    ax = axs[1]
    ax.axhline(0.5, color=INK2, lw=0.8, ls="--")
    ax.text(4.35, 0.51, T("zgadywanie", "guessing"), fontsize=7, color=INK2, va="bottom", ha="right")
    ax.plot(xs, [r[1] for r in hwb], color=BLUE, marker="o", ms=5, markeredgecolor="white", markeredgewidth=0.8, label="ODRA")
    ax.plot(xs, [r[1] for r in smb], color=YELLOW, marker="D", ms=5, markeredgecolor="white", markeredgewidth=0.8, label=T("symulacja", "simulation"))
    ax.set_xticks(xs); ax.set_xticklabels(labels)
    ax.set_ylim(0.3, 1.0)
    ax.set_xlabel(T(r"margines $|O_\mathrm{ideal}|$", r"margin $|O_\mathrm{ideal}|$"))
    ax.set_ylabel(T("dokładność ideału", "noiseless accuracy"))
    ax.set_title(T("…a tam klasyfikator sam zgaduje", "…where the classifier itself is guessing"), loc="left")
    ax.legend(loc="upper left")
    panel(ax, "b")
    fig.tight_layout()
    save(fig, "fig6_decisions")


# ---------------------------------------------------------------------------------------
# Fig. 2 (new main result): inverting the line predicted by the calibrated simulator

FREE_ORDER = [("w01A", "star", "12"), ("w01P5", "star_idle24", "12, idle≈24"), ("w01P5", "star_idle36", "12, idle≈36"),
              ("w01P5", "star_idle52", "12, idle≈52"), ("w01P5", "star_cz24", "24 (pairs)"),
              ("w01P5", "star_L6", "24 (L6)"), ("w01B", "linear", "30"), ("w01P5", "star_cz36", "36 (pairs)"),
              ("w01P5", "star_L9", "36 (L9)"), ("w01A", "circular", "39"), ("w01P5", "star_cz52", "52 (pairs)"),
              ("w01P5", "star_L13", "52 (L13)"), ("w01B", "all_to_all", "57")]


def fig_free() -> None:
    # per-point lines from the full calibration simulator (line_source_compare.py)
    d = pd.read_csv(OUT / "line_source_points.csv").merge(
        pd.read_csv(OUT / "sim_line_points.csv")[["window", "rung", "point", "err_cdr", "err_cdr_twirl"]],
        on=["window", "rung", "point"])
    d["err_sim_rung"] = d["err_full"]
    m = d.groupby(["window", "rung"]).mean(numeric_only=True)
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.7), gridspec_kw=dict(width_ratios=[1.6, 1]))
    ax = axs[0]
    xs = np.arange(len(FREE_ORDER))
    series = [("err_raw", C_RAW, "o", T("bez mitygacji", "unmitigated")),
              ("err_sim_rung", AQUA, "D", T("prosta z symulatora (0 pomiarów treningowych)", "simulator line (no training shots)")),
              ("err_cdr", C_CDR, "o", T("CDR na sprzęcie", "CDR on hardware")),
              ("err_cdr_twirl", C_TWIRL, "s", T("CDR + twirling na sprzęcie", "CDR + twirling on hardware"))]
    for col, c, mk, lab in series:
        y = [m.loc[(w, r), col] for w, r, _ in FREE_ORDER]
        ax.scatter(xs, y, color=c, marker=mk, s=24, edgecolors="white", linewidths=0.8, zorder=3, label=lab)
    ax.set_xticks(xs)
    ax.set_xticklabels([lab for _, _, lab in FREE_ORDER], rotation=50, ha="right", fontsize=6.5)
    ax.set_xlabel(T("wariant obwodu (bramki CZ)", "circuit variant (CZ gates)"))
    ax.set_ylabel(T("średni błąd", "mean error"))
    ax.set_ylim(0, 0.27)
    ax.set_title(T("Odwrócenie przewidzianej prostej", "Inverting the predicted line"), loc="left")
    ax.legend(loc="upper left", fontsize=6.8)
    ax.grid(axis="x", visible=False)
    panel(ax, "a")

    ax = axs[1]
    lim = [0.004, 0.5]
    ax.scatter(np.maximum(d.err_cdr, 4e-3), np.maximum(d.err_sim_rung, 4e-3), s=10, color=AQUA,
               edgecolors="white", linewidths=0.5, alpha=0.9)
    ax.plot(lim, lim, color=INK2, lw=0.8, ls="--")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel(T("błąd CDR na sprzęcie", "error, CDR on hardware"))
    ax.set_ylabel(T("błąd prostej z symulatora", "error, simulator line"))
    ax.set_title(T("Na poziomie punktów: remis", "Per point: a tie"), loc="left")
    wins = int((d.err_sim_rung < d.err_cdr).sum())
    ax.text(0.005, 0.32, T(f"prosta lepsza w {wins}/{len(d)}", f"line better in {wins}/{len(d)}"), fontsize=7)
    panel(ax, "b")
    fig.tight_layout()
    save(fig, "fig_free_mitigation")


def main() -> None:
    global LANG
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["pl", "en"], default="pl")
    LANG = ap.parse_args().lang
    style()
    for f in (fig1, fig2, fig3, fig4, fig5, fig6, fig_free):
        f()


if __name__ == "__main__":
    main()
