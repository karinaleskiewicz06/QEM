"""Noiseless accuracy + transpiled-cost ladder for the 3 banknote ansatze.

Offline (statevector only, no noise / no hardware). Produces the Month-1 report
tables:
  * noiseless accuracy per ansatz x depth, mean +/- std over the 5 CV folds
    (the upper bound each QEM rung on hardware is chasing), and
  * transpiled CZ + depth on the ODRA star (the routing-cost independent variable).

Usage:
    python banknote_study/noiseless_and_cost.py
    python banknote_study/noiseless_and_cost.py --depths 2 4 6 --epoch 30
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys

import numpy as np

QEM_ROOT = pathlib.Path(__file__).resolve().parents[1]
UPSTREAM = QEM_ROOT / "banknote_study" / "upstream"
sys.path.insert(0, str(QEM_ROOT))
sys.path.insert(0, str(UPSTREAM / "src"))

from qiskit.quantum_info import SparsePauliOp, Statevector  # noqa: E402

from banknote_study.run_zne_banknote import (  # noqa: E402
    READOUT_QUBIT, build_full_circuit, load_weights,
)
from noisy_sim import IQM_BASIS_GATES, star_coupling_map  # noqa: E402
from qiskit import transpile  # noqa: E402


def full_fold(fold: int) -> tuple[np.ndarray, np.ndarray]:
    path = UPSTREAM / "cross_validation" / "Data" / f"fold_{fold}" / "test_data.csv"
    rows = list(csv.DictReader(open(path)))
    X = np.array([[float(r[str(i)]) for i in range(5)] for r in rows])
    y = np.array([float(r["target"]) for r in rows])
    return X, y


def observable(n: int, mq: int) -> SparsePauliOp:
    return SparsePauliOp.from_list([("I" * (n - 1 - mq) + "Z" + "I" * mq, 1.0)])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ansatze", nargs="+", default=["star", "odra", "simulator"])
    ap.add_argument("--depths", type=int, nargs="+", default=[2, 4, 6])
    ap.add_argument("--folds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    ap.add_argument("--epoch", type=int, default=30)
    ap.add_argument("--out", default="banknote_study/banknote_noiseless_cost.csv")
    args = ap.parse_args()
    n = 5

    print("=" * 74)
    print(f"Banknote noiseless accuracy + cost ladder (epoch {args.epoch}, "
          f"folds {args.folds})")
    print("=" * 74)
    print(f"{'ansatz':>10} {'depth':>5} {'readout':>7} {'CZ':>4} {'tdepth':>6} "
          f"{'acc_mean':>8} {'acc_std':>7}")

    rows = []
    for name in args.ansatze:
        for depth in args.depths:
            mq = READOUT_QUBIT[name]
            obs = observable(n, mq)
            # transpiled cost (data-independent: bind all params to 0.1)
            full, xparams, wparams = build_full_circuit(name, n, depth)
            probe = transpile(
                full.assign_parameters({p: 0.1 for p in full.parameters}),
                basis_gates=list(IQM_BASIS_GATES),
                coupling_map=star_coupling_map(n), optimization_level=1)
            n2q = sum(1 for i in probe.data if i.operation.name == "cz")
            tdepth = probe.depth()

            accs = []
            for fold in args.folds:
                weights = load_weights(name, depth, fold, args.epoch)
                circ_w = full.assign_parameters(dict(zip(wparams, weights)))
                X, y = full_fold(fold)
                ev = np.array([
                    np.real(Statevector.from_instruction(
                        circ_w.assign_parameters(dict(zip(xparams, x)))
                    ).expectation_value(obs)) for x in X])
                accs.append(float(np.mean(np.sign(ev) == y)))
            am, as_ = float(np.mean(accs)), float(np.std(accs))
            rows.append({"ansatz": name, "depth": depth, "readout_qubit": mq,
                         "transpiled_cz": n2q, "transpiled_depth": tdepth,
                         "acc_noiseless_mean": round(am, 4),
                         "acc_noiseless_std": round(as_, 4),
                         "folds": len(args.folds), "epoch": args.epoch})
            print(f"{name:>10} {depth:>5} {mq:>7} {n2q:>4} {tdepth:>6} "
                  f"{am:>8.3f} {as_:>7.3f}")

    out_path = QEM_ROOT / args.out
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
