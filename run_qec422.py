"""[[4,2,2]] detection demonstrator — QEC-lite runner (methodology_month_2.md §4, W5).

Sim prototype of the Option-C arm: a code-preserving mirror (U U†) on the 4-qubit
[[4,2,2]] block, run at increasing payload 2q cost, comparing three quantities per
rung:
  * bare survival        P(|00>_L)  with NO post-selection,
  * detected survival    P(|00>_L)  AFTER Z-parity post-selection,
  * acceptance rate      kept / total shots (the post-selection overhead),
and the effective shots (shots / acceptance) so it lands on the shots-to-target axis.

This is the "prototype in the calibrated simulator first" step; the hardware run
embeds the 4-qubit block on Garnet/Emerald via a code-block placement (methodology
§7) and adds the optimal/adverse comparison. Option A (surrogate classifier) reuses
``qec422.build_encoded_surrogate`` with a near-Clifford payload — wire your surrogate
into the ``--arm A`` hook.

Usage (sim; no credentials):
  python run_qec422.py --layers 1 2 3 --shots 8192
  python run_qec422.py --p2q 0.02          # stronger 2q error
"""

from __future__ import annotations

import argparse
import csv

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import random_clifford

from noisy_sim import DeviceCalibration, IQM_BASIS_GATES, make_noisy_simulator
from qec422 import (
    N_DATA,
    Z_LOGICAL1,
    build_detection_mirror,
    codespace_survival,
    logical_z_expval,
    postselect_z_parity,
)
from shots_to_target import qec_effective_shots
from topology import star_coupling_map


def random_clifford_payload(layers: int, seed: int) -> QuantumCircuit:
    """A code-block payload of ``layers`` composed random 4-qubit Cliffords."""
    rng = np.random.default_rng(seed)
    qc = QuantumCircuit(N_DATA)
    for _ in range(layers):
        cl = random_clifford(N_DATA, seed=int(rng.integers(0, 2**31)))
        qc.compose(cl.to_circuit(), inplace=True)
    return qc


def _block_calibration(p2q: float) -> DeviceCalibration:
    """4-qubit code-block calibration (Spark-class), hub-0 star so encode is native."""
    return DeviceCalibration(num_qubits=N_DATA, coupling_map=star_coupling_map(N_DATA, 0),
                             p_2q=p2q)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--layers", type=int, nargs="+", default=[1, 2, 3],
                    help="payload cost ladder (composed random Cliffords)")
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--p2q", type=float, default=0.01, help="2q depolarizing error")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="qec422_results.csv")
    args = ap.parse_args()

    cal = _block_calibration(args.p2q)
    sim = make_noisy_simulator(cal)
    print(f"[[4,2,2]] detection demonstrator (Option C mirror) | p2q={args.p2q} | "
          f"shots {args.shots}")
    print("  layers  2q | logicalErr bare->det | survival bare->det | accept | eff_shots")
    rows = []
    for layers in args.layers:
        payload = random_clifford_payload(layers, args.seed + layers)
        mirror = build_detection_mirror(payload, detect=True)
        native = transpile(mirror, basis_gates=IQM_BASIS_GATES,
                           coupling_map=cal.coupling_map, optimization_level=1,
                           seed_transpiler=args.seed)
        n2q = sum(1 for i in native.data if i.operation.name == "cz")
        counts = sim.run(native, shots=args.shots).result().get_counts()
        bare = codespace_survival(counts)
        kept, acc = postselect_z_parity(counts)
        detected = codespace_survival(kept)
        # logical <O>-error: the mirror ideally returns to |00>_L, where Zbar_1 = +1,
        # so this is the [[4,2,2]] analogue of the ZNE/CDR <O>-error (comparable axis).
        err_bare = abs(1.0 - logical_z_expval(counts, Z_LOGICAL1))
        err_det = abs(1.0 - logical_z_expval(kept, Z_LOGICAL1))
        eff = int(qec_effective_shots(args.shots, acc)) if acc > 0 else -1
        rows.append({"layers": layers, "transpiled_cz": n2q,
                     "err_bare": round(err_bare, 4), "err_detected": round(err_det, 4),
                     "bare_survival": round(bare, 4), "detected_survival": round(detected, 4),
                     "acceptance": round(acc, 4), "shots": args.shots, "effective_shots": eff})
        print(f"  {layers:>6} {n2q:>4} | logicalErr {err_bare:.3f}->{err_det:.3f} "
              f"| surv {bare:.3f}->{detected:.3f} | acc {acc:.3f} | eff {eff}")

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {args.out}")
    print("Detection helps iff detected_survival > bare_survival AND the acceptance "
          "cost (effective_shots) is worth it — a clean negative is a valid result.")


if __name__ == "__main__":
    main()
