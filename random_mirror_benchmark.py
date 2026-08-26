"""Task-agnostic random-Clifford mirror benchmark (methodology_month_2.md §6).

Shows the routing frontier is a *device* property, not a VQC artifact, using
classifier-independent random Clifford mirror circuits (U U†, ideal output
|0...0>) at increasing transpiled 2q cost, per device and placement. Complements
the VQC mirror-fidelity backbone: same survival metric, no dependence on any task.

Usage (sim; no credentials):
  python random_mirror_benchmark.py --device odra
  python random_mirror_benchmark.py --device garnet --placement optimal --calibration <lat.json>
  python random_mirror_benchmark.py --device garnet --placement adverse
"""

from __future__ import annotations

import argparse
import csv

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import random_clifford

from noisy_sim import (
    DeviceCalibration,
    IQM_BASIS_GATES,
    logical_final_wires,
    make_noisy_simulator,
    synthesize_lattice_calibration,
    load_iqm_calibration,
)
from topology import placement

N_QUBITS = 5


def random_mirror(layers: int, seed: int) -> QuantumCircuit:
    """U U† where U = ``layers`` composed random 5-qubit Cliffords (ideal = |0...0>)."""
    rng = np.random.default_rng(seed)
    u = QuantumCircuit(N_QUBITS)
    for _ in range(layers):
        u.compose(random_clifford(N_QUBITS, seed=int(rng.integers(0, 2**31))).to_circuit(),
                  inplace=True)
    m = u.copy()
    m.compose(u.inverse(), inplace=True)
    return m


def _survival_on_wires(counts: dict[str, int], wires: list[int], width: int) -> float:
    """Fraction of shots with all ``wires`` measured 0 (|0...0> survival on the block)."""
    total = sum(counts.values())
    good = 0
    for b, c in counts.items():
        bits = b.replace(" ", "")[-width:].zfill(width)
        if all(bits[width - 1 - w] == "0" for w in wires):
            good += c
    return good / total if total else 0.0


def _calibration_for(device, path):
    if path:
        return load_iqm_calibration(path)
    return DeviceCalibration() if device in ("odra", "star") else synthesize_lattice_calibration(device)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="odra")
    ap.add_argument("--placement", default="optimal")
    ap.add_argument("--layers", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--calibration", default="")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="random_mirror_results.csv")
    args = ap.parse_args()

    cal = _calibration_for(args.device, args.calibration)
    layout = None if cal.num_qubits == N_QUBITS else placement(args.device, N_QUBITS, args.placement)
    sim = make_noisy_simulator(cal)

    print(f"random-Clifford mirror | device {args.device} placement {args.placement} | "
          f"shots {args.shots}")
    print(f"  {'layers':>6} {'2q':>4} {'survival':>9}")
    rows = []
    for layers in args.layers:
        mirror = random_mirror(layers, args.seed + layers)
        native = transpile(mirror, basis_gates=IQM_BASIS_GATES, coupling_map=cal.coupling_map,
                           initial_layout=layout, optimization_level=1, seed_transpiler=args.seed)
        n2q = sum(1 for i in native.data if i.operation.name == "cz")
        wires = logical_final_wires(native, N_QUBITS) if layout is not None else list(range(N_QUBITS))
        native.measure_all()
        counts = sim.run(native, shots=args.shots).result().get_counts()
        surv = _survival_on_wires(counts, wires, native.num_qubits)
        rows.append({"device": args.device, "placement": args.placement, "layers": layers,
                     "transpiled_cz": n2q, "survival": round(surv, 4), "shots": args.shots})
        print(f"  {layers:>6} {n2q:>4} {surv:>9.4f}")

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
