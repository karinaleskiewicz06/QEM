"""⚠️ WIP / DO NOT USE — the full-syndrome circuit here is KNOWN-BROKEN and the
whole comparison is SUPERSEDED. Kept only as a record.

Why broken: `_full_syndrome_circuit` measures XXXX (X-basis) and then reads the
data qubits in Z — non-commuting, so it scrambles the Z bitstring even at p2q=0
(the noiseless sanity gate FAILS: err~0.3, acc~0.7 instead of err~0, acc~1).

Why superseded: a statevector test showed that for this study's Z-basis observable,
Z-type (phase) errors DO NOT corrupt the result, so XXXX detection is pure wasted
acceptance. ZZZZ-only is complete. See qec_logical_directions.md §1b. Conclusion:
do NOT add XXXX; do NOT use this script's numbers.

--- original (invalid) docstring below ---
Compare detection power: half (ZZZZ only) vs full (ZZZZ + XXXX) on [[4,2,2]].

Free calibrated-sim experiment (gaps #1b). The current arm post-selects only on
ZZZZ parity -> catches X-type errors only (half the code). "Full" adds an XXXX
syndrome ancilla -> also catches Z-type (phase) errors. Question: how much more
error does full detection remove, and what does it cost in acceptance?

Sanity gate: at p2q=0 both schemes must give acceptance ~1.0 and logical err ~0.

    python scope_detection_compare.py --layers 1 2 3 --p2q 0.01
"""
from __future__ import annotations

import argparse
import csv

import numpy as np
from qiskit import QuantumCircuit, transpile

from noisy_sim import DeviceCalibration, IQM_BASIS_GATES, make_noisy_simulator
from qec422 import N_DATA, Z_LOGICAL1, encode_422
from run_qec422 import random_clifford_payload
from topology import star_coupling_map


def _mirror(payload: QuantumCircuit) -> QuantumCircuit:
    qc = QuantumCircuit(N_DATA)
    qc.compose(encode_422(), inplace=True)
    qc.barrier(); qc.compose(payload, inplace=True)
    qc.barrier(); qc.compose(payload.inverse(), inplace=True)
    return qc


def _full_syndrome_circuit(payload: QuantumCircuit) -> QuantumCircuit:
    """4 data + ancZ(4) + ancX(5); measure data + both syndromes."""
    qc = QuantumCircuit(6, 6)
    qc.compose(_mirror(payload), qubits=range(N_DATA), inplace=True)
    qc.barrier()
    # ZZZZ syndrome -> ancZ (q4): parity of data in Z
    for d in range(N_DATA):
        qc.cx(d, 4)
    # XXXX syndrome -> ancX (q5): parity of data in X
    qc.h(5)
    for d in range(N_DATA):
        qc.cx(5, d)
    qc.h(5)
    qc.barrier()
    qc.measure(range(6), range(6))
    return qc


def _bits(b):  # normalize a counts key to 6 chars, LSB = qubit 0
    return b.replace(" ", "").zfill(6)


def _logical_z(counts, want_ancZ0=True, want_ancX0=None):
    """Logical <Zbar1>=<Z0 Z1> over shots passing the requested syndrome filters."""
    num = den = 0.0
    for b, c in counts.items():
        s = _bits(b)
        ancZ = int(s[6 - 1 - 4]); ancX = int(s[6 - 1 - 5])
        if want_ancZ0 and ancZ != 0:
            continue
        if want_ancX0 and ancX != 0:
            continue
        val = 1.0
        for q in Z_LOGICAL1:
            val *= 1.0 - 2.0 * int(s[6 - 1 - q])
        num += val * c; den += c
    return (num / den if den else 0.0), den


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--layers", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--p2q", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="scope_detection_compare_results.csv")
    args = ap.parse_args()

    def run(p2q):
        cal = DeviceCalibration(num_qubits=6, coupling_map=star_coupling_map(6, 0), p_2q=p2q)
        sim = make_noisy_simulator(cal)
        out = []
        for layers in args.layers:
            payload = random_clifford_payload(layers, args.seed + layers)
            circ = _full_syndrome_circuit(payload)
            native = transpile(circ, basis_gates=IQM_BASIS_GATES, coupling_map=cal.coupling_map,
                               optimization_level=1, seed_transpiler=args.seed)
            n2q = sum(1 for i in native.data if i.operation.name == "cz")
            counts = sim.run(native, shots=args.shots).result().get_counts()
            total = sum(counts.values())
            # raw (no PS)
            z_raw, _ = _logical_z(counts, want_ancZ0=False)
            # half: post-select ZZZZ only
            z_half, kept_half = _logical_z(counts, want_ancZ0=True)
            # full: post-select ZZZZ AND XXXX
            z_full, kept_full = _logical_z(counts, want_ancZ0=True, want_ancX0=True)
            out.append(dict(layers=layers, cz=n2q,
                            err_raw=abs(1 - z_raw), err_half=abs(1 - z_half), err_full=abs(1 - z_full),
                            acc_half=kept_half / total, acc_full=kept_full / total))
        return out

    # --- sanity gate: noiseless ---------------------------------------------- #
    print("SANITY (p2q=0): expect acc~1.0, err~0 for both schemes")
    for r in run(0.0):
        print(f"  cz {r['cz']:>3}: err_half {r['err_half']:.3f} err_full {r['err_full']:.3f} "
              f"| acc_half {r['acc_half']:.3f} acc_full {r['acc_full']:.3f}")

    print(f"\nNOISY (p2q={args.p2q}): half (ZZZZ) vs full (ZZZZ+XXXX)")
    print(f"{'cz':>4} | {'err_raw':>7} {'err_half':>8} {'err_full':>8} | "
          f"{'acc_half':>8} {'acc_full':>8}")
    rows = run(args.p2q)
    for r in rows:
        print(f"{r['cz']:>4} | {r['err_raw']:>7.3f} {r['err_half']:>8.3f} {r['err_full']:>8.3f} | "
              f"{r['acc_half']:>8.3f} {r['acc_full']:>8.3f}")

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("-" * 68)
    print(f"wrote {args.out}")
    print("READ: full removes more error than half IFF err_full < err_half, but acc_full < "
          "acc_half (stricter filter = fewer shots kept). Trade-off is the point.")


if __name__ == "__main__":
    main()
