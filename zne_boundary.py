"""Granica opłacalności ZNE: przewidywanie analityczne vs zmierzone dane.

Przy zrównanym budżecie S pomiarów (ZNE dzieli go na |Lambda| skal) estymator Richardsona ma
wariancję (sum c_i^2) * |Lambda| * V / S, gdzie V to wariancja obserwabla na pojedynczy pomiar.
Porównując MSE estymatora surowego (B^2 + V/S) z MSE estymatora ZNE otrzymujemy warunek
opłacalności

    B^2  >  [ (sum c_i^2) * |Lambda| - 1 ] * V / S    =>    B* = sqrt(kappa * V / S),

gdzie B to obciążenie (błąd surowy), a kappa zależy wyłącznie od wyboru węzłów. Skrypt liczy B*
dla naszych budżetów i konfrontuje przewidywanie "pomoże/zaszkodzi" ze zmierzonymi wynikami.

    python zne_boundary.py
"""
from __future__ import annotations

import csv
import glob
from collections import defaultdict

import numpy as np

SCALES = [1, 3, 5]


def richardson_coeffs(lams):
    return [float(np.prod([lj / (lj - li) for lj in lams if lj != li])) for li in lams]


def per_shot_variance(n_qubits=5, obs_coeff=0.2):
    """Wariancja obserwabla mean-Z na pojedynczy pomiar (górne ograniczenie).

    mean-Z = sum_i c_i Z_i z c_i = 1/n. Dla nieskorelowanych kubitów o <Z_i> ~ 0 mamy
    Var = sum_i c_i^2 Var(Z_i) <= n * (1/n)^2 * 1 = 1/n. Korelacje mogą tę wartość podnieść,
    więc traktujemy ją jako oszacowanie rzędu wielkości.
    """
    return n_qubits * obs_coeff ** 2


def load_points():
    """[(urządzenie, cz, shots, err_raw, err_zne)] z kampanii sprzętowych."""
    out = []
    acc = defaultdict(lambda: defaultdict(list))
    shots = {}
    for p in [q for q in sorted(glob.glob("garnet_twirl_w*.csv")) if "banded" not in q]:
        for r in csv.DictReader(open(p, newline="")):
            if str(r["twirl"]).lower() == "false" and r["arm"] in ("raw", "zne"):
                acc[("Garnet", int(r["transpiled_cz"]))][r["arm"]].append(float(r["err"]))
                shots[("Garnet", int(r["transpiled_cz"]))] = int(r["shots"])
    for r in csv.DictReader(open("emerald_xtopo.csv", newline="")):
        if r["arm"] in ("raw", "zne"):
            acc[("Emerald", int(r["transpiled_cz"]))][r["arm"]].append(float(r["err"]))
            shots[("Emerald", int(r["transpiled_cz"]))] = int(r["shots"])
    for key in sorted(acc, key=lambda k: (k[0], k[1])):
        d = acc[key]
        if "raw" in d and "zne" in d:
            out.append((key[0], key[1], shots[key], float(np.mean(d["raw"])), float(np.mean(d["zne"]))))
    return out


def main():
    c = richardson_coeffs(SCALES)
    sc2 = sum(ci ** 2 for ci in c)
    kappa = sc2 * len(SCALES) - 1.0
    V = per_shot_variance()
    print(f"Wspolczynniki Richardsona {SCALES}: {[round(x,4) for x in c]}")
    print(f"  sum c_i^2 = {sc2:.4f}   |Lambda| = {len(SCALES)}   kappa = {kappa:.3f}")
    print(f"  wariancja obserwabla na pomiar V ~ {V:.3f}")
    print()
    print("Granica oplacalnosci  B* = sqrt(kappa*V/S):")
    for S in (1024, 2048, 4096, 8192, 16384):
        print(f"   S={S:>6}:  B* = {np.sqrt(kappa*V/S):.4f}")
    print()
    print(f"{'urzadzenie':<9} {'CZ':>4} {'shots':>6} {'B (raw)':>8} {'B*':>7} "
          f"{'przewid.':>9} {'zmierz.':>9} {'zgodne?':>8}")
    ok = tot = 0
    for dev, cz, S, raw, zne in load_points():
        Bstar = np.sqrt(kappa * V / S)
        pred = "pomoze" if raw > Bstar else "zaszkodzi"
        meas = "pomoze" if zne < raw else "zaszkodzi"
        agree = "TAK" if pred == meas else "NIE"
        tot += 1; ok += (pred == meas)
        print(f"{dev:<9} {cz:>4} {S:>6} {raw:>8.4f} {Bstar:>7.4f} {pred:>9} {meas:>9} {agree:>8}")
    print(f"\nzgodnosc przewidywania: {ok}/{tot}")
    print("\nODCZYT: punkty ponizej B* to reżim, w ktorym wzmocniona wariancja przewyzsza usuwane")
    print("obciazenie -> ZNE szkodzi. Niezgodnosci przy wysokim CZ nalezy tlumaczyc DRUGIM")
    print("mechanizmem (kolaps sygnalu, zne_signal_retention.py), nie ta granica.")


if __name__ == "__main__":
    main()
