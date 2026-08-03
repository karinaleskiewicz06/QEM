"""Routing/mapping sweep: emit a monotonic ladder of transpiled 2q-gate costs.

Month-1 deliverable (plan.md §9): produce circuits with a documented, monotonic
ladder of **transpiled two-qubit-gate counts** by varying the entangling pattern
and/or the physical layout on the Tier-A star, holding the logical payload fixed.
The transpiled 2q-gate count (CZ on IQM) is the physically meaningful cost variable
and the x-axis for every downstream ZNE plot.

The star topology is the SWAP generator: any interaction between two *outer* qubits
must route through the hub, so ``all_to_all`` forces many SWAPs while ``star`` is
native (minimal). Decomposition target is the IQM native basis {r, cz}.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib

from qiskit import QuantumCircuit, transpile

from ansatz import HardwareEfficientAnsatz, two_qubit_gate_count
from noisy_sim import IQM_BASIS_GATES, star_coupling_map

# Patterns ordered by expected routing pressure (native -> maximal).
LADDER_PATTERNS: list[str] = ["star", "linear", "circular", "all_to_all"]


def _count_cz(circuit: QuantumCircuit) -> int:
    return sum(1 for inst in circuit.data if inst.operation.name == "cz")


def build_logical_vqc(
    n_qubits: int,
    n_layers: int,
    n_features: int,
    entanglement: str,
    entangling_gate: str = "cz",
) -> QuantumCircuit:
    """Fixed logical VQC payload with a chosen entangling pattern (params unbound).

    For a pure gate-count sweep we do not need bound parameters -- only the
    two-qubit connectivity matters. We use the native CZ entangler so the logical
    2q count maps cleanly onto the transpiled CZ count.
    """
    return HardwareEfficientAnsatz(
        num_qubits=n_qubits,
        num_layers=n_layers,
        num_features=n_features,
        entanglement=entanglement,
        entangling_gate=entangling_gate,
    ).build()


def sweep(
    n_qubits: int = 5,
    n_layers: int = 2,
    n_features: int = 8,
    hub: int = 0,
    seed_transpiler: int = 42,
    patterns: list[str] | None = None,
) -> list[dict]:
    """Transpile the logical VQC under each pattern onto the star; record costs."""
    patterns = patterns or LADDER_PATTERNS
    coupling = star_coupling_map(n_qubits, hub)
    rows: list[dict] = []
    for pattern in patterns:
        logical = build_logical_vqc(n_qubits, n_layers, n_features, pattern)
        logical_2q = two_qubit_gate_count(logical)
        tqc = transpile(
            logical,
            basis_gates=IQM_BASIS_GATES,
            coupling_map=coupling,
            optimization_level=1,
            seed_transpiler=seed_transpiler,
        )
        rows.append(
            {
                "pattern": pattern,
                "logical_2q": logical_2q,
                "transpiled_cz": _count_cz(tqc),
                "transpiled_depth": tqc.depth(),
                "n_qubits": n_qubits,
                "n_layers": n_layers,
            }
        )
    # sort into a monotonic ladder by transpiled cost
    rows.sort(key=lambda r: (r["transpiled_cz"], r["transpiled_depth"]))
    for level, r in enumerate(rows):
        r["level"] = level
    return rows


def load_config_from_frozen(
    models_dir: str | pathlib.Path = "trained_models",
) -> dict:
    """Pull n_qubits/n_layers/n_features from the best frozen model, if present."""
    models_dir = pathlib.Path(models_dir)
    best = None
    for jf in models_dir.glob("*_q*_*.json"):
        try:
            c = json.loads(jf.read_text())
        except Exception:
            continue
        if best is None or c.get("test_acc", -1) > best.get("test_acc", -1):
            best = c
    return best or {}


def write_csv(rows: list[dict], path: str | pathlib.Path = "routing_ladder.csv") -> None:
    path = pathlib.Path(path)
    fields = ["level", "pattern", "logical_2q", "transpiled_cz",
              "transpiled_depth", "n_qubits", "n_layers"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in fields})


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from-frozen", action="store_true",
                   help="take n_qubits/n_layers/n_features from best trained model")
    p.add_argument("--n-qubits", type=int, default=5)
    p.add_argument("--n-layers", type=int, default=2)
    p.add_argument("--n-features", type=int, default=8)
    p.add_argument("--out", default="routing_ladder.csv")
    args = p.parse_args()

    nq, nl, nf = args.n_qubits, args.n_layers, args.n_features
    if args.from_frozen:
        cfg = load_config_from_frozen()
        if cfg:
            nq = cfg.get("n_qubits", nq)
            nl = cfg.get("n_layers", nl)
            nf = cfg.get("n_features", nf)
            print(f"[from-frozen] using n_qubits={nq} n_layers={nl} n_features={nf}")

    rows = sweep(nq, nl, nf)
    write_csv(rows, args.out)

    print(f"\nrouting ladder (star topology, IQM basis {IQM_BASIS_GATES}):")
    print(f"{'lvl':>3} {'pattern':>12} {'logical_2q':>11} "
          f"{'transpiled_cz':>14} {'depth':>6}")
    print("-" * 52)
    for r in rows:
        print(f"{r['level']:>3} {r['pattern']:>12} {r['logical_2q']:>11} "
              f"{r['transpiled_cz']:>14} {r['transpiled_depth']:>6}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
