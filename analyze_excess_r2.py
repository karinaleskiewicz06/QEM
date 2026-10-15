"""Is the r^2 decay a coherence signature, or does incoherent noise do it too? (review F1)

The report derives that a depolarizing channel rescales every expectation value by the
same factor, so CDR's linear map stays exact and r^2 -> 1. The conclusion drawn from
that was: r^2 decay is a signature of *coherent* error.

The simulation says otherwise. With no coherent term at all, r^2 still falls with gate
count, because the derivation holds for expectation values and not for finite-shot
estimates: as noise compresses the signal, the spread of the ideal training values
(SS_tot) shrinks while the shot noise in the measured values does not -- textbook
regression attenuation. T1 and readout are also non-unital, so the intercept picks up a
circuit dependence of its own.

So r^2 on its own cannot be read as "coherence". What may still carry signal is the
*excess* decay over a null built from the device's own measured calibration. This script
quantifies that, using the nested models produced by nested_null_odra.sh:

    theta = 0.00   device calibration only            (the null)
    theta = 0.02   same + weak coherent over-rotation
    theta = 0.05   same + stronger

    python analyze_excess_r2.py
"""

from __future__ import annotations

import argparse
import csv
import glob
import math

SERIES = [("nested_cal00_banded.csv", "null (theta=0)"),
          ("nested_cal02_banded.csv", "theta=0.02"),
          ("nested_cal05_banded.csv", "theta=0.05")]

# Only ODRA hardware is compared against the null: the null is built from ODRA's own
# measured calibration, and calibrations/garnet.json carries topology only (no T1/T2,
# p_1q, p_2q or readout), so there is no Garnet null to compare Garnet against. Holding
# Garnet up to an ODRA-calibrated null would be exactly the protocol confound the review
# flags in F2.
HARDWARE = [("odra_twirl_banded.csv", "ODRA hardware")]


def ladder(path: str) -> dict[int, tuple[float, float, int]]:
    """CZ -> (mean r2 without twirling, sd, n_windows) from a banded file."""
    out = {}
    try:
        rows = list(csv.DictReader(open(path)))
    except FileNotFoundError:
        return out
    for x in rows:
        if x.get("arm") == "cdr" and x.get("twirl") == "False" and x.get("r2_mean"):
            r2 = float(x["r2_mean"])
            # fit_cdr returns exactly 0.0 when the training set is degenerate
            # (SS_tot ~ 0, i.e. every near-Clifford circuit landed on the same ideal
            # value). That is a missing measurement, not an r2 of zero -- keeping it
            # would drag the curve down and invent a huge "excess".
            if r2 == 0.0:
                continue
            out[int(x["transpiled_cz"])] = (r2, float(x["r2_std"] or 0),
                                            int(x["n_windows"] or 0))
    return out


def interp(curve: dict[int, tuple[float, float, int]], cz: int) -> tuple[float | None, bool]:
    """Null curve at an arbitrary gate count. Returns (value, outside_range).

    Outside the measured range the value is clamped to the nearest endpoint, which is
    extrapolation, not interpolation -- the caller must flag it rather than quote it as
    if it were measured.
    """
    if not curve:
        return None, False
    xs = sorted(curve)
    if cz < xs[0]:
        return curve[xs[0]][0], True
    if cz > xs[-1]:
        return curve[xs[-1]][0], True
    for a, b in zip(xs, xs[1:]):
        if a <= cz <= b:
            ya, yb = curve[a][0], curve[b][0]
            return (ya if a == b else ya + (cz - a) / (b - a) * (yb - ya)), False
    return curve[xs[-1]][0], False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="r2_excess_over_null.csv")
    args = ap.parse_args()

    curves = {label: ladder(path) for path, label in SERIES}
    null = curves.get("null (theta=0)", {})
    if not null:
        raise SystemExit("nested_cal00_banded.csv missing -- run nested_null_odra.sh first")

    print("Nested simulations on the ODRA calibration (r2 of the CDR fit, no twirling):\n")
    allcz = sorted({cz for c in curves.values() for cz in c})
    head = "  " + "CZ".rjust(5) + "".join(f"{lab:>20s}" for _, lab in SERIES)
    print(head)
    for cz in allcz:
        line = f"  {cz:>5}"
        for _, lab in SERIES:
            v = curves[lab].get(cz)
            line += f"{(f'{v[0]:.4f} ± {v[1]:.3f}' if v else '—'):>20s}"
        print(line)

    print("\nExcess decay over the device null, at matched gate count:")
    print(f"  {'CZ':>5}{'theta=0.02':>14}{'theta=0.05':>14}")
    for cz in allcz:
        base = null.get(cz)
        if not base:
            continue
        row = f"  {cz:>5}"
        for _, lab in SERIES[1:]:
            v = curves[lab].get(cz)
            row += f"{(f'{v[0]-base[0]:+.4f}' if v else '—'):>14s}"
        print(row)

    rows = []
    print("\nHardware against the interpolated null:")
    print(f"  {'device':16s}{'CZ':>5}{'r2 measured':>14}{'null here':>12}{'excess':>10}  note")
    for path, label in HARDWARE:
        for cz, (r2, sd, nw) in sorted(ladder(path).items()):
            nv, outside = interp(null, cz)
            exc = (r2 - nv) if nv is not None else None
            note = "extrapolated null" if outside else ""
            print(f"  {label:16s}{cz:>5}{r2:>14.4f}"
                  f"{(f'{nv:.4f}' if nv is not None else '—'):>12s}"
                  f"{(f'{exc:+.4f}' if exc is not None else '—'):>10s}  {note}")
            rows.append({"source": label, "cz": cz, "r2": r2, "sd": sd, "n_windows": nw,
                         "null_at_cz": nv, "excess": exc, "null_extrapolated": outside})

    if rows:
        with open(args.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {args.out}")

    print("\nHow to read this: a null column that falls with CZ means r^2 alone is NOT a\n"
          "coherence probe. The probe survives only if the coherent columns sit clearly\n"
          "below the null at matched gate count, and if hardware shows a negative excess.")


if __name__ == "__main__":
    main()
