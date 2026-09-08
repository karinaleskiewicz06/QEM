"""Wszystkie rysunki do raportu końcowego (final_raport.tex).

    fig1_cross_topology.png  -- CDR r^2 vs CZ na trzech topologiach (załamanie topologicznie ogólne)
    fig2_companion_sim.png   -- Δr² vs CZ w symulacji: null (depol) vs koherencja 0.05 / 0.10
    fig3_twirl_hardware.png  -- Δr² vs CZ na Garnecie z pasmami dryfu + poziom zerowy w tle
    fig4_method_comparison.png -- raw / CDR / ZNE vs CZ, panel na urządzenie
    fig5_correlation_map.png -- mapa korelacji Spearmana: metryki routingu vs metryki degradacji

    python make_final_figures.py
"""
from __future__ import annotations

import csv
import glob
import os
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

C_RAW, C_CDR, C_ZNE = "#8d99ae", "#2e86ab", "#d1495b"
C_DEV = {"ODRA": "#d1495b", "Garnet": "#2e86ab", "Emerald": "#3c896d"}
plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.25})


def _twirl_windows(paths):
    """{cz: {window: {True/False: (err, r2)}}} z plików kampanii twirlingowej."""
    d = defaultdict(lambda: defaultdict(dict))
    for p in paths:
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                if r["arm"] != "cdr" or not r.get("cdr_r2"):
                    continue
                tw = str(r["twirl"]).lower() == "true"
                d[int(r["transpiled_cz"])][r["window"]][tw] = (float(r["err"]), float(r["cdr_r2"]))
    return d


def _paired(d):
    """{cz: (mean Δr², std Δr², n)} — różnica sparowana ON-OFF w obrębie okna."""
    out = {}
    for cz, wins in d.items():
        deltas = [v[True][1] - v[False][1] for v in wins.values() if True in v and False in v]
        if deltas:
            out[cz] = (float(np.mean(deltas)), float(np.std(deltas, ddof=1)) if len(deltas) > 1 else 0.0,
                       len(deltas))
    return dict(sorted(out.items()))


# ODRA CDR: preferuj pomiar sprzętowy (run_odra_cdr.py); symulacja tylko jako zapasowa,
# gdyby kampania sprzętowa nie była jeszcze zebrana.
ODRA_CDR = next((p for p in ("odra_full_100pt.csv", "odra_cdr_100pt.csv", "odra_cdr_results.csv")
                 if os.path.exists(p)), "cdr_hard_results.csv")
ODRA_HW = ODRA_CDR != "cdr_hard_results.csv"


# ---------------------------------------------------------------- fig 1
def fig1():
    def odra():
        xy = [(int(r["transpiled_cz"]), float(r["cdr_r2"]))
              for r in csv.DictReader(open(ODRA_CDR)) if r["device"] == "odra"]
        return sorted(xy)

    def from_twirl(paths):
        acc = defaultdict(list)
        for p in paths:
            for r in csv.DictReader(open(p, newline="")):
                if r["arm"] == "cdr" and str(r["twirl"]).lower() == "false" and r.get("cdr_r2"):
                    acc[int(r["transpiled_cz"])].append(float(r["cdr_r2"]))
        return sorted((cz, float(np.mean(v))) for cz, v in acc.items())

    series = [
        (f"ODRA (gwiazda, 5q) — {'sprzęt' if ODRA_HW else 'SYMULACJA'}", odra(), "o",
         "-" if ODRA_HW else "--"),
        ("Garnet (krata, 20q) — sprzęt", from_twirl(sorted(p for p in glob.glob("garnet_twirl_w*.csv")
                                                           if "banded" not in p)), "s", "-"),
        ("Emerald (krata, 54q) — sprzęt", from_twirl(["emerald_xtopo.csv"]), "^", "-"),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.axhspan(0.4, 0.8, color=C_RAW, alpha=0.12)
    ax.axhline(0.8, color="#666", ls="--", lw=1)
    ax.text(2, 0.808, "obszar załamania ($r^2 < 0{,}8$)", color="#555", fontsize=8, va="bottom")
    for (label, pts, m, ls), col in zip(series, C_DEV.values()):
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], ls, marker=m, color=col,
                    markersize=8, lw=2, label=label,
                    markerfacecolor=("white" if ls == "--" else col))
    ax.set_xlabel("liczba bramek CZ po transpilacji  (koszt routingu →)")
    ax.set_ylabel("jakość dopasowania CDR  $r^2$")
    ax.set_title("Załamanie CDR pod narzutem routingu jest topologicznie ogólne\n"
                 + ("spadek monotoniczny na trzech urządzeniach sprzętowych" if ODRA_HW
                    else "spadek monotoniczny; ODRA symulowana"), fontsize=10.5)
    ax.set_ylim(0.45, 1.02); ax.set_xlim(0, 122); ax.legend(loc="lower left", fontsize=9)
    fig.tight_layout(); fig.savefig("fig1_cross_topology.png", dpi=160); plt.close(fig)
    print("  fig1_cross_topology.png")


# ---------------------------------------------------------------- fig 2
def fig2():
    regimes = [("szum depolaryzujący (kontrola zerowa)", "night_null_w*.csv", "#8d99ae", "o", "--"),
               (r"koherentny $\theta = 0{,}05$ (reżim sprzętu)", "night_coh05_w*.csv", "#2e86ab", "s", "-"),
               (r"koherentny $\theta = 0{,}10$", "night_coh10_w*.csv", "#d1495b", "^", "-")]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.axhline(0, color="#444", lw=1)
    for label, pat, col, m, ls in regimes:
        paths = [p for p in sorted(glob.glob(pat)) if "banded" not in p]
        if not paths:
            continue
        pr = _paired(_twirl_windows(paths))
        cz = list(pr); mu = [pr[c][0] for c in cz]; sd = [pr[c][1] for c in cz]
        ax.errorbar(cz, mu, yerr=sd, fmt=m, ls=ls, color=col, lw=2, markersize=8,
                    capsize=4, label=label)
    ax.set_xlabel("liczba bramek CZ po transpilacji (symulacja)")
    ax.set_ylabel(r"zysk twirlingu  $\Delta r^2 = r^2(\mathrm{ON}) - r^2(\mathrm{OFF})$")
    ax.set_title("Mechanizm: twirling pomaga tylko wobec błędu koherentnego\n"
                 "(pomiary zrównane; słupki = odchylenie między oknami)", fontsize=10.5)
    ax.legend(fontsize=9, loc="upper left"); fig.tight_layout()
    fig.savefig("fig2_companion_sim.png", dpi=160); plt.close(fig)
    print("  fig2_companion_sim.png")


# ---------------------------------------------------------------- fig 3
def _pairs(paths):
    """[(r2_OFF, Δr²), ...] — po jednym punkcie na (CZ, okno)."""
    d = _twirl_windows(paths)
    return [(v[False][1], v[True][1] - v[False][1])
            for wins in d.values() for v in wins.values() if True in v and False in v]


def fig3():
    hw_paths = sorted(p for p in glob.glob("garnet_twirl_w*.csv") if "banded" not in p)
    null_paths = [p for p in sorted(glob.glob("night_null_w*.csv")) if "banded" not in p]
    hw = _paired(_twirl_windows(hw_paths))
    null = _paired(_twirl_windows(null_paths))

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(12.4, 4.7))

    # --- panel A: Δr² vs koszt routingu, z pasmami dryfu --------------------- #
    if null:
        vals = [v[0] for v in null.values()]; sds = [v[1] for v in null.values()]
        axA.axhspan(min(vals) - max(sds), max(vals) + max(sds), color=C_RAW, alpha=0.25,
                    label="obwiednia poziomu zerowego (symulacja, szum niekoherentny)")
    axA.axhline(0, color="#444", lw=1)
    cz = list(hw); mu = [hw[c][0] for c in cz]; sd = [hw[c][1] for c in cz]
    axA.errorbar(cz, mu, yerr=sd, fmt="s-", color=C_CDR, lw=2, markersize=9, capsize=5,
                 label="Garnet (sprzęt), pasma z okien kalibracyjnych")
    for c in cz:
        axA.annotate(f"n={hw[c][2]}", (c, hw[c][0]), textcoords="offset points",
                     xytext=(9, -13), fontsize=8, color="#555")
    axA.set_xlabel("liczba bramek CZ po transpilacji (sprzęt)")
    axA.set_ylabel(r"zysk twirlingu  $\Delta r^2$")
    axA.set_title("(a) Zysk wobec kosztu routingu\nistotny przy 57 CZ; przy 96 CZ dryf dominuje",
                  fontsize=10)
    axA.set_xlim(0, 108); axA.legend(fontsize=8, loc="upper left")

    # --- panel B: Δr² vs zniszczenie liniowości (mechanizm) ------------------ #
    series = [("Garnet (sprzęt)", _pairs(hw_paths), C_CDR, "s", 70),
              ("symulacja: szum niekoherentny", _pairs(null_paths), C_RAW, "o", 42),
              (r"symulacja: koherentny $\theta{=}0{,}05$", _pairs(
                  [p for p in sorted(glob.glob("night_coh05_w*.csv")) if "banded" not in p]),
               "#3c896d", "^", 42)]
    axB.axhline(0, color="#444", lw=1)
    for label, pts, col, m, s in series:
        if not pts:
            continue
        x = [1 - p[0] for p in pts]; y = [p[1] for p in pts]
        axB.scatter(x, y, c=col, marker=m, s=s, alpha=0.85, edgecolors="white",
                    linewidths=0.6, label=label, zorder=3)
        if len(x) > 2:  # linia trendu
            b, a = np.polyfit(x, y, 1)
            xs = np.linspace(min(x), max(x), 20)
            axB.plot(xs, b * xs + a, color=col, lw=1.4, ls="--", alpha=0.75, zorder=2)
    hw_pts = _pairs(hw_paths)
    rho = spearmanr([p[0] for p in hw_pts], [p[1] for p in hw_pts])
    axB.set_xlabel(r"jakość dopasowania bez twirlingu  $r^2(\mathrm{OFF})$"
                   "\n(w lewo = więcej zniszczonej liniowości)")
    axB.set_ylabel(r"zysk twirlingu  $\Delta r^2$")
    axB.set_title("(b) Mechanizm: twirling odzyskuje tyle, ile koherencja zepsuła\n"
                  rf"sprzęt: $\rho = {rho.statistic:+.2f}$, $p = {rho.pvalue:.3f}$ "
                  rf"($n={len(hw_pts)}$)",
                  fontsize=10)
    axB.legend(fontsize=8, loc="upper left")
    fig.tight_layout(); fig.savefig("fig3_twirl_hardware.png", dpi=160); plt.close(fig)
    print("  fig3_twirl_hardware.png (2 panele)")


# ---------------------------------------------------------------- fig 4
def fig4():
    def odra():
        # raw / CDR / ZNE z JEDNEJ kampanii, jeśli runner zapisał ramię ZNE (kolumna err_zne);
        # inaczej ZNE z osobnej kampanii Month-1 (inne ustawienie DD -- patrz raport)
        raw, cdr, zne = {}, {}, {}
        for r in csv.DictReader(open(ODRA_CDR)):
            if r["device"] != "odra":
                continue
            cz = int(r["transpiled_cz"])
            raw[cz] = float(r["err_raw"]); cdr[cz] = float(r["err_cdr"])
            if r.get("err_zne"):
                zne[cz] = float(r["err_zne"])
        if not zne:
            for r in csv.DictReader(open("zne_hard_results.csv")):
                zne[int(r["transpiled_cz"])] = float(r["zne_richardson_err"])
        return raw, cdr, zne

    def from_twirl(paths):
        acc = {"raw": defaultdict(list), "cdr": defaultdict(list), "zne": defaultdict(list)}
        for p in paths:
            for r in csv.DictReader(open(p, newline="")):
                if str(r["twirl"]).lower() == "false" and r["arm"] in acc:
                    acc[r["arm"]][int(r["transpiled_cz"])].append(float(r["err"]))
        m = lambda d: {cz: float(np.mean(v)) for cz, v in d.items()}
        return m(acc["raw"]), m(acc["cdr"]), m(acc["zne"])

    devs = [("ODRA (gwiazda)", *odra()),
            ("Garnet (20q)", *from_twirl(sorted(p for p in glob.glob("garnet_twirl_w*.csv")
                                                if "banded" not in p))),
            ("Emerald (54q)", *from_twirl(["emerald_xtopo.csv"]))]
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.3), sharey=True)
    for ax, (name, raw, cdr, zne) in zip(axes, devs):
        for d, col, lab, m in [(raw, C_RAW, "bez mitygacji", "o"), (cdr, C_CDR, "CDR", "s"),
                               (zne, C_ZNE, "ZNE", "^")]:
            pts = sorted(d.items())
            if pts:
                ax.plot([p[0] for p in pts], [p[1] for p in pts], "-", marker=m, color=col,
                        lw=2, markersize=7, label=lab)
        ax.set_title(name, fontsize=10.5); ax.set_xlabel("CZ po transpilacji")
    axes[0].set_ylabel(r"błąd  $\varepsilon = |\langle O\rangle - \langle O\rangle_{\rm ideal}|$")
    axes[0].legend(fontsize=9)
    axes[2].annotate("kolaps: mitygacja\nszkodzi", xy=(114, 0.279), xytext=(70, 0.30),
                     fontsize=8.5, color=C_ZNE,
                     arrowprops=dict(arrowstyle="->", color=C_ZNE, lw=1.2))
    fig.suptitle("Porównanie metod na wspólnej osi kosztu routingu "
                 "(ZNE wygrywa nisko, CDR wysoko, powyżej ~114 CZ żadna)", fontsize=11)
    fig.tight_layout(); fig.savefig("fig4_method_comparison.png", dpi=160); plt.close(fig)
    print("  fig4_method_comparison.png")


# ---------------------------------------------------------------- fig 5
def fig5():
    rows = list(csv.DictReader(open("routing_correlation_summary.csv")))
    mirror = {(r["placement"], r["pattern"]): float(r["survival"])
              for r in csv.DictReader(open("garnet_mirror_results.csv"))}
    cdr = {(r["placement"], r["pattern"]): (float(r["err_cdr"]), float(r["cdr_r2"]))
           for r in csv.DictReader(open("garnet_cdr_results.csv"))}

    data = defaultdict(list)
    for r in rows:
        k = (r["placement"], r["pattern"])
        data["CZ"].append(float(r["cz"])); data["SWAP"].append(float(r["swaps"]))
        data["głębokość"].append(float(r["depth"])); data["odl. topol."].append(float(r["topo_dist"]))
        data["błąd raw"].append(float(r["err_raw"])); data["błąd ZNE"].append(float(r["err_zne"]))
        data["1 - wierność\nlustrzana"].append(1 - mirror[k] if k in mirror else np.nan)
        data["błąd CDR"].append(cdr[k][0] if k in cdr else np.nan)
        data["$r^2$ CDR"].append(cdr[k][1] if k in cdr else np.nan)

    cost = ["CZ", "SWAP", "głębokość", "odl. topol."]
    degr = ["błąd raw", "błąd ZNE", "błąd CDR", "1 - wierność\nlustrzana", "$r^2$ CDR"]
    M = np.full((len(degr), len(cost)), np.nan); N = np.zeros_like(M, dtype=int)
    for i, dn in enumerate(degr):
        for j, cn in enumerate(cost):
            a, b = np.array(data[dn], float), np.array(data[cn], float)
            ok = ~np.isnan(a) & ~np.isnan(b)
            if ok.sum() >= 3:
                M[i, j] = spearmanr(a[ok], b[ok]).statistic; N[i, j] = ok.sum()

    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    im = ax.imshow(M, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cost)), cost)
    ax.set_yticks(range(len(degr)), degr, fontsize=9)
    for i in range(len(degr)):
        for j in range(len(cost)):
            if not np.isnan(M[i, j]):
                ax.text(j, i, f"{M[i,j]:+.2f}\n(n={N[i,j]})", ha="center", va="center", fontsize=8.5,
                        color="white" if abs(M[i, j]) > 0.55 else "#222")
    ax.set_title("Mapa korelacji Spearmana: miary kosztu routingu vs miary degradacji\n"
                 "(Garnet; $r^2$ CDR koreluje ujemnie — spada z routingiem)", fontsize=10.5)
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="współczynnik Spearmana $\\rho$", shrink=0.85)
    fig.tight_layout(); fig.savefig("fig5_correlation_map.png", dpi=160); plt.close(fig)
    print("  fig5_correlation_map.png")


# ---------------------------------------------------------------- fig 6
def fig6():
    """Wzorce splątania ansatzu: graf logiczny + liczba bramek CZ po transpilacji."""
    from ansatz import ENTANGLEMENT_PATTERNS, entangling_pairs
    # liczby CZ zmierzone na żywym backendzie Garneta (rozmieszczenie optimal / adverse)
    CZ_HW = {"star": (12, 36), "linear": (24, 42), "circular": (39, 54), "all_to_all": (57, 96)}
    order = ["star", "linear", "circular", "all_to_all"]
    fig, axes = plt.subplots(1, 4, figsize=(13.6, 3.9))
    n = 5
    ang = np.linspace(np.pi / 2, np.pi / 2 + 2 * np.pi, n, endpoint=False)
    pos = np.c_[np.cos(ang), np.sin(ang)]
    for ax, pat in zip(axes, order):
        pairs = entangling_pairs(n, pat)
        for a, b in pairs:
            ax.plot(*zip(pos[a], pos[b]), color=C_CDR, lw=1.8, alpha=0.75, zorder=1)
        ax.scatter(pos[:, 0], pos[:, 1], s=430, c="white", edgecolors="#333",
                   linewidths=1.6, zorder=2)
        for q in range(n):
            ax.text(*pos[q], str(q), ha="center", va="center", fontsize=10, zorder=3)
        lo, hi = CZ_HW[pat]
        ax.set_title(f"{pat}\n{len(pairs)} bramek logicznych\n"
                     f"CZ: {lo} (optimal) / {hi} (adverse)", fontsize=9.5, pad=8)
        ax.set_xlim(-1.45, 1.45); ax.set_ylim(-1.45, 1.55)
        ax.set_aspect("equal"); ax.axis("off")
    fig.suptitle("Wzorce splątania ansatzu i ich koszt po transpilacji na Garneta",
                 fontsize=12, y=1.04)
    fig.tight_layout(); fig.savefig("fig6_ansatz_patterns.png", dpi=160); plt.close(fig)
    print("  fig6_ansatz_patterns.png")


if __name__ == "__main__":
    print("generuję rysunki:")
    for f in (fig1, fig2, fig3, fig4, fig5, fig6):
        try:
            f()
        except Exception as e:
            print(f"  BŁĄD w {f.__name__}: {e}")
