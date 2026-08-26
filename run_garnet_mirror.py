"""Mirror-fidelity on hardware (methodology §6/§7) — task-agnostic yardstick.

Per (placement, pattern): build U (the pattern's VQC), mirror it (U U†, ideal
|0...0>), transpile with the placement, submit, report survival P(|0...0>) vs
transpiled CZ. Measurements added before transpilation -> counts in logical order.
Batched one job per placement. Works on any Resonance device via --device.

    python run_garnet_mirror.py --device garnet
    python run_garnet_mirror.py --device emerald --patterns star all_to_all
"""

from __future__ import annotations

import argparse
import csv
import pathlib

import numpy as np

from ansatz import HardwareEfficientAnsatz
from iqm_resonance import get_backend, run_circuits, transpile_for_backend
from noisy_sim import load_frozen_model
from topology import hardware_placement

LADDER_PATTERNS = ["star", "linear", "circular", "all_to_all"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="garnet")
    ap.add_argument("--placements", nargs="+", default=["optimal", "adverse"])
    ap.add_argument("--patterns", nargs="+", default=LADDER_PATTERNS)
    ap.add_argument("--shots", type=int, default=4096)
    ap.add_argument("--n-inputs", type=int, default=3,
                    help="average survival over this many representative inputs (robustness)")
    ap.add_argument("--models-dir", default="trained_models",
                    help="model directory (trained_models_hard for the hard config)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = args.out or f"{args.device}_mirror_results.csv"

    _, _, cfg = load_frozen_model(models_dir=args.models_dir)
    n = cfg["n_qubits"]
    tag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
           f"{cfg['entanglement']}_{cfg['readout']}_L{cfg['n_layers']}")
    inputs = np.load(pathlib.Path(args.models_dir) / f"{tag}_reference.npz")["X_eval"][:args.n_inputs]
    star_weights = np.load(pathlib.Path(args.models_dir) / cfg["weights_file"])

    def weights_for(pattern):
        ptag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
                f"{pattern}_{cfg['readout']}_L{cfg['n_layers']}")
        wp = pathlib.Path(args.models_dir) / f"{ptag}_weights.npy"
        return np.load(wp) if wp.exists() else star_weights

    backend = get_backend(args.device)
    print(f"backend {backend.name} | mirror | placements {args.placements} | "
          f"patterns {args.patterns} | {args.shots} shots")
    print(">>> note credit balance NOW <<<\n")

    zero = "0" * n
    rows = []
    for placement in args.placements:
        layout = hardware_placement(args.device, placement)
        circuits, index, n2q_of = [], {}, {}
        for pattern in args.patterns:
            ans = HardwareEfficientAnsatz(n, cfg["n_layers"], num_features=cfg["n_features"],
                                          entanglement=pattern,
                                          entangling_gate=cfg.get("entangling_gate", "cx"))
            circ = ans.build()
            xparams = ans.feature_parameters(circ)
            wparams = ans.weight_parameters(circ)
            wmap = dict(zip(wparams, weights_for(pattern)))
            idxs = []
            for x in inputs:  # average over several inputs (robust fidelity)
                u = circ.assign_parameters({**wmap, **dict(zip(xparams, x))})
                mirror = u.copy()
                mirror.compose(u.inverse(), inplace=True)
                mirror.measure_all()
                tqc = transpile_for_backend(mirror, backend, initial_layout=layout)
                n2q_of[pattern] = sum(1 for i in tqc.data if i.operation.name in ("cz", "cx"))
                idxs.append(len(circuits))
                circuits.append(tqc)
            index[pattern] = idxs

        counts = run_circuits(backend, circuits, args.shots)  # <=100/job (Resonance cap)
        for pattern in args.patterns:
            survs = [counts[j].get(zero, 0) / args.shots for j in index[pattern]]
            n2q = n2q_of[pattern]
            rows.append({"device": args.device, "placement": placement, "pattern": pattern,
                         "mirror_cz": n2q,
                         "survival": round(float(np.mean(survs)), 4),
                         "survival_std": round(float(np.std(survs)), 4),
                         "n_inputs": len(inputs), "shots": args.shots})
            print(f"  {placement:>8} {pattern:>11} | mirror 2q={n2q:>3} | "
                  f"survival {np.mean(survs):.4f} +/- {np.std(survs):.4f} (n={len(inputs)})")

    rows.sort(key=lambda r: (r["placement"], r["mirror_cz"]))
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out}\n>>> note credit balance AGAIN — difference = cost <<<")


if __name__ == "__main__":
    main()
