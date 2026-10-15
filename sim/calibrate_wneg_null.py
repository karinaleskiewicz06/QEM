"""Null distribution of W_neg at the campaign's shot count, and the folding controls.

``W_neg`` (the negative mass of state-by-state Richardson, ``qem.zne.negativity``) is
never exactly zero on real data: shot noise in ``P_s(lambda)`` is amplified by the
negative coefficient ``c_2``. Koster & Mauerer's thresholds (0.06 for valid folds, 0.64
for garbage) were read off 16 states at 4096 shots; we have 32 states and a different
shot count, so the threshold has to be recalibrated. This script does that in Aer under
**pure depolarizing noise**, where global folding scales the noise as Richardson
assumes, so any ``W_neg`` it produces is the shot-noise floor of a *valid* extrapolation.

It runs all three matched-cost fold variants (``qem.folding``) on the frozen classifier
along the routing ladder and writes, per circuit set:

* ``W_neg`` and its 1q-marginal version, ``frac_negative``, ``min P_hat``;
* ``<O>`` at every scale, the estimate, ``unphysical``;
* retention ``|<O>(1)| / |O_ideal|`` and ``SNR = |<O>(lambda_max)| / SE``;
* the floor ``f`` = mean garbage ``<O>`` at ``lambda_max`` for that ladder point, and
  the Eq. 2 tracking distance of the genuine estimate.

The summary gives quantiles of ``W_neg`` per variant. The genuine q95/q99 under this
null are the candidates for the pre-registered threshold (P9); garbage shows how far a
destroyed signal sits above it.

    python -m sim.calibrate_wneg_null                           # full ladder, 24 points
    python -m sim.calibrate_wneg_null --quick                   # star only, 4 points
    python -m sim.calibrate_wneg_null --calibration calibrations/odra_20260803.json

Nothing here touches hardware.
"""

from __future__ import annotations

import argparse
import csv
import pathlib

import numpy as np
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from noisy_sim import (IQM_BASIS_GATES, load_frozen_model, load_iqm_calibration,
                       observable_coeffs, perqubit_z_from_counts, readout_observable)
from qem.compile import compile_native
from qem.folding import FOLD_VARIANTS, fold_native
from qem.zne import diagnose_point

LADDER = ("star", "linear", "circular", "all_to_all")
OUT_DIR = pathlib.Path("results_sim/wneg_null")
QUANTILES = (0.5, 0.95, 0.99)


def depolarizing_model(p1q: float, p2q: float) -> NoiseModel:
    """Depolarizing on every ``r`` and ``cz``, nothing else: no T1, no readout error.

    Under this model folding multiplies the error per gate and Richardson is the right
    extrapolator, which is what makes the resulting ``W_neg`` a null.
    """
    nm = NoiseModel(basis_gates=IQM_BASIS_GATES)
    nm.add_all_qubit_quantum_error(depolarizing_error(p1q, 1), ["r"])
    nm.add_all_qubit_quantum_error(depolarizing_error(p2q, 2), ["cz"])
    return nm


def frozen_targets(models_dir: str, pattern: str, n_points: int):
    """Bound circuits of the frozen classifier for one ladder pattern, with ideals."""
    _, _, cfg = load_frozen_model(models_dir=models_dir)
    n = cfg["n_qubits"]
    md = pathlib.Path(models_dir)
    stem = f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}"
    X = np.load(md / f"{stem}_star_{cfg['readout']}_L{cfg['n_layers']}_reference.npz")["X_eval"]
    if n_points > len(X):
        raise ValueError(f"only {len(X)} reference points available; asked for {n_points}")
    wpath = md / f"{stem}_{pattern}_{cfg['readout']}_L{cfg['n_layers']}_weights.npy"
    weights = np.load(wpath) if wpath.exists() else np.load(md / cfg["weights_file"])
    ans = HardwareEfficientAnsatz(n, cfg["n_layers"], num_features=cfg["n_features"],
                                  entanglement=pattern,
                                  entangling_gate=cfg.get("entangling_gate", "cx"))
    circ = ans.build()
    circ_w = circ.assign_parameters(dict(zip(ans.weight_parameters(circ), weights)))
    xp = ans.feature_parameters(circ)
    obs = readout_observable(n, cfg["readout"])
    bound = [circ_w.assign_parameters(dict(zip(xp, x))) for x in X[:n_points]]
    ideals = [float(np.real(Statevector.from_instruction(b).expectation_value(obs)))
              for b in bound]
    return bound, ideals, observable_coeffs(obs, n)


def run_null(targets, ideals, coeffs, *, sim: AerSimulator, shots: int, scales,
             variants=FOLD_VARIANTS, seed: int = 0, label: str = "") -> list[dict]:
    """Fold every target in every variant, execute once, and diagnose.

    Returns one row per (variant, point). The floor used for the tracking test is the
    mean garbage ``<O>`` at ``lambda_max`` over this call's points, so pass all points
    of one ladder point together.
    """
    scales = [int(s) for s in scales]
    natives = [compile_native(t).circuit for t in targets]
    keys, circs = [], []
    for i, nat in enumerate(natives):
        for v in variants:
            for s in scales:
                keys.append((v, i, s))
                circs.append(fold_native(nat, s, v, seed=seed * 100_003 + i, measure=True))
    result = sim.run(circs, shots=shots, seed_simulator=seed).result()
    counts = {k: result.get_counts(j) for j, k in enumerate(keys)}
    n_cz = {k: c.count_ops().get("cz", 0) for k, c in zip(keys, circs)}
    ev = {k: float(np.dot(coeffs, perqubit_z_from_counts(c, len(coeffs))))
          for k, c in counts.items()}

    floor = (float(np.mean([ev[("garbage", i, scales[-1])] for i in range(len(natives))]))
             if "garbage" in variants else None)
    bound = float(np.sum(np.abs(coeffs)))
    rows = []
    for v in variants:
        for i, ideal in enumerate(ideals):
            d = diagnose_point(scales, [ev[(v, i, s)] for s in scales], ideal=ideal,
                               bound=bound, counts_per_scale=[counts[(v, i, s)] for s in scales],
                               coeffs=coeffs, floor=floor)
            rows.append({"label": label, "variant": v, "point_index": i, "seed": seed,
                         "shots": shots,
                         **{f"n_cz_lam{s}": n_cz[(v, i, s)] for s in scales}, **d})
    return rows


def summarise(rows: list[dict]) -> list[dict]:
    """Quantiles of ``W_neg`` (and median SNR) per ladder point and variant, plus pooled."""
    out = []
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["label"], r["variant"]), []).append(r)
        groups.setdefault(("ALL", r["variant"]), []).append(r)
    for (label, variant), rs in sorted(groups.items()):
        w = np.array([r["w_neg"] for r in rs])
        wm = np.array([r["w_neg_marg"] for r in rs])
        row = {"label": label, "variant": variant, "n": len(rs),
               "w_neg_mean": round(float(w.mean()), 5)}
        row.update({f"w_neg_q{int(q * 100)}": round(float(np.quantile(w, q)), 5)
                    for q in QUANTILES})
        row["w_neg_max"] = round(float(w.max()), 5)
        row["w_neg_marg_q95"] = round(float(np.quantile(wm, 0.95)), 5)
        row["snr_lmax_median"] = round(float(np.median([r["snr_lmax"] for r in rs])), 3)
        row["unphysical"] = int(sum(r["unphysical"] for r in rs))
        out.append(row)
    return out


def _write(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--patterns", nargs="+", default=list(LADDER), choices=LADDER)
    ap.add_argument("--eval-points", type=int, default=24)
    ap.add_argument("--shots", type=int, default=8192, help="per circuit, as in the campaign")
    ap.add_argument("--reps", type=int, default=3, help="independent shot-noise draws")
    ap.add_argument("--scales", type=int, nargs="+", default=[1, 3, 5])
    ap.add_argument("--variants", nargs="+", default=list(FOLD_VARIANTS), choices=FOLD_VARIANTS)
    ap.add_argument("--p1q", type=float, default=1e-3)
    ap.add_argument("--p2q", type=float, default=1e-2)
    ap.add_argument("--calibration", default=None,
                    help="take p1q (mean over qubits) and p2q from this calibration JSON; "
                         "still depolarizing only")
    ap.add_argument("--models-dir", default="trained_models_hard")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--quick", action="store_true", help="star only, 4 points, 1 rep")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--tag", default=None, help="file stem (default from the settings)")
    args = ap.parse_args()
    if args.quick:
        args.patterns, args.eval_points, args.reps = ["star"], 4, 1

    p1q, p2q = args.p1q, args.p2q
    if args.calibration:
        cal = load_iqm_calibration(args.calibration)
        p1q, p2q = float(np.mean(cal.p_1q)), float(cal.p_2q)
    sim = AerSimulator(method="density_matrix", noise_model=depolarizing_model(p1q, p2q))
    print(f"W_neg null | depolarizing p1q={p1q:.2e} p2q={p2q:.2e} | shots {args.shots} | "
          f"scales {args.scales} | {args.eval_points} pts x {args.reps} reps | "
          f"variants {args.variants}")

    rows = []
    for pattern in args.patterns:
        targets, ideals, coeffs = frozen_targets(args.models_dir, pattern, args.eval_points)
        for rep in range(args.reps):
            rows += run_null(targets, ideals, coeffs, sim=sim, shots=args.shots,
                             scales=args.scales, variants=args.variants,
                             seed=args.seed + rep, label=pattern)
        cz1 = rows[-1][f"n_cz_lam{args.scales[0]}"]
        print(f"  {pattern:<11} cz={cz1:>3} done")

    summary = summarise(rows)
    tag = args.tag or (f"depol_p2q{p2q:.0e}_S{args.shots}_lam" + "-".join(map(str, args.scales)))
    out = pathlib.Path(args.out_dir)
    _write(out / f"{tag}_points.csv", rows)
    _write(out / f"{tag}_summary.csv", summary)
    print(f"\n{'label':<11} {'variant':<9} {'mean':>8} {'q50':>8} {'q95':>8} {'q99':>8} "
          f"{'max':>8} {'SNR med':>8}")
    for s in summary:
        print(f"{s['label']:<11} {s['variant']:<9} {s['w_neg_mean']:>8.4f} {s['w_neg_q50']:>8.4f} "
              f"{s['w_neg_q95']:>8.4f} {s['w_neg_q99']:>8.4f} {s['w_neg_max']:>8.4f} "
              f"{s['snr_lmax_median']:>8.2f}")
    print(f"\nwrote {out / (tag + '_points.csv')} and _summary.csv")
    print("READ: genuine/identity quantiles are the null; a threshold for P9 is taken "
          "from them and fixed before the campaign.")


if __name__ == "__main__":
    main()
