"""Sim-scoping: does detection ([[4,2,2]] post-selection) COMPOSE with ZNE?

Free calibrated-simulator experiment (qec_logical_directions.md §6, gaps #2b).
On the [[4,2,2]] detection mirror at increasing routing cost, compares four arms
at matched circuit:

  raw       : scale 1, no post-selection            (baseline)
  detect    : scale 1, Z-parity post-selection       (QEC-lite alone)
  zne       : Richardson over scales {1,3,5}, no PS   (ZNE alone)
  det+zne   : Richardson over scales {1,3,5}, PS      (the composition)

Key questions: (a) does det+zne beat min(detect, zne)?  (b) how fast does
acceptance fall under ZNE folding (the shot penalty)?  (c) effective-shot cost.

    python scope_qec_zne.py --layers 1 2 3 --p2q 0.01
"""
from __future__ import annotations

import argparse
import csv

import numpy as np
from qiskit import QuantumCircuit, transpile

from noisy_sim import DeviceCalibration, IQM_BASIS_GATES, make_noisy_simulator
from qec422 import (
    N_DATA, Z_LOGICAL1, encode_422, postselect_z_parity, logical_z_expval,
)
from run_qec422 import random_clifford_payload
from zne_dryrun import SCALE_FACTORS, fold_global, extrapolate
from shots_to_target import qec_effective_shots, zne_effective_shots
from topology import star_coupling_map


def _mirror_unitary(payload: QuantumCircuit) -> QuantumCircuit:
    """encode -> payload -> payload^dag  (no measurement); ideal = |00>_L."""
    qc = QuantumCircuit(N_DATA)
    qc.compose(encode_422(), inplace=True)
    qc.barrier()
    qc.compose(payload, inplace=True)
    qc.barrier()
    qc.compose(payload.inverse(), inplace=True)
    return qc


def _run_counts(native_unitary: QuantumCircuit, sim, shots: int) -> dict:
    qc = native_unitary.copy()
    qc.measure_all()
    return sim.run(qc, shots=shots).result().get_counts()


def _zbar(counts: dict) -> float:
    return logical_z_expval(counts, Z_LOGICAL1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--layers", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--p2q", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="scope_qec_zne_results.csv")
    args = ap.parse_args()

    cal = DeviceCalibration(num_qubits=N_DATA, coupling_map=star_coupling_map(N_DATA, 0),
                            p_2q=args.p2q)
    sim = make_noisy_simulator(cal)
    print(f"QEC+ZNE composition scoping | p2q={args.p2q} | shots {args.shots} | "
          f"scales {list(SCALE_FACTORS)}")
    print(f"{'cz':>4} | {'raw':>6} {'detect':>6} {'zne':>6} {'det+zne':>7} | "
          f"{'acc@1':>6} {'acc@hi':>6} | {'eff_zne':>8} {'eff_dz':>8}")
    rows = []
    for layers in args.layers:
        payload = random_clifford_payload(layers, args.seed + layers)
        mirror = _mirror_unitary(payload)
        native = transpile(mirror, basis_gates=IQM_BASIS_GATES, coupling_map=cal.coupling_map,
                           optimization_level=1, seed_transpiler=args.seed)
        n2q = sum(1 for i in native.data if i.operation.name == "cz")

        zbar_noPS, zbar_PS, accs = [], [], []
        for s in SCALE_FACTORS:
            folded = fold_global(native, s)
            counts = _run_counts(folded, sim, args.shots)
            kept, acc = postselect_z_parity(counts)
            zbar_noPS.append(_zbar(counts))
            zbar_PS.append(_zbar(kept) if acc > 0 else 0.0)
            accs.append(acc)

        # errors: mirror ideal returns to |00>_L where Zbar_1 = +1
        err_raw = abs(1.0 - zbar_noPS[0])
        err_detect = abs(1.0 - zbar_PS[0])
        err_zne = abs(1.0 - extrapolate(SCALE_FACTORS, zbar_noPS, "richardson"))
        err_detzne = abs(1.0 - extrapolate(SCALE_FACTORS, zbar_PS, "richardson"))

        mean_acc = float(np.mean(accs))
        eff_zne = int(zne_effective_shots(args.shots, len(SCALE_FACTORS)))
        eff_dz = int(zne_effective_shots(args.shots, len(SCALE_FACTORS)) / max(mean_acc, 1e-9))

        rows.append({"layers": layers, "transpiled_cz": n2q,
                     "err_raw": round(err_raw, 4), "err_detect": round(err_detect, 4),
                     "err_zne": round(err_zne, 4), "err_detzne": round(err_detzne, 4),
                     "acc_scale1": round(accs[0], 4), "acc_scalehi": round(accs[-1], 4),
                     "mean_acc": round(mean_acc, 4),
                     "eff_zne": eff_zne, "eff_detzne": eff_dz, "shots": args.shots})
        print(f"{n2q:>4} | {err_raw:>6.3f} {err_detect:>6.3f} {err_zne:>6.3f} {err_detzne:>7.3f} "
              f"| {accs[0]:>6.3f} {accs[-1]:>6.3f} | {eff_zne:>8} {eff_dz:>8}")

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("-" * 78)
    print(f"wrote {args.out}")
    print("READ: det+zne WINS iff err_detzne < min(err_detect, err_zne) AND the acceptance")
    print("      penalty (eff_detzne vs eff_zne) is worth it. acc@hi << acc@1 = folding hurts PS.")


if __name__ == "__main__":
    main()
