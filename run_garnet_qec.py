"""[[4,2,2]] detection on hardware (methodology §4/§7) — QEC-lite on a real device.

Option C (detection-wrapped mirror) on the 4-qubit code block, at increasing payload
cost, at optimal vs adverse code-block placement. Reports logical <O>-error and
survival (bare vs detected) + acceptance rate. Device-generic via --device.

The 4-qubit code-block placement is derived at runtime from the device's real
coupling map (calibrations/<device>.json, saved by pull_<device>.py) — run that
first. Measurements are inside the mirror circuit (data-qubit order).

    python run_garnet_qec.py --device garnet
    python run_garnet_qec.py --device emerald --layers 1 2 3
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib

import numpy as np

from iqm_resonance import get_backend, run_circuits, transpile_for_backend
from qec422 import (
    Z_LOGICAL1,
    build_detection_mirror,
    codespace_survival,
    logical_z_expval,
    postselect_z_parity,
)
from run_qec422 import random_clifford_payload
from shots_to_target import qec_effective_shots
from topology import derive_placements


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="garnet")
    ap.add_argument("--placements", nargs="+", default=["optimal", "adverse"])
    ap.add_argument("--layers", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-seeds", type=int, default=3,
                    help="average over this many random payloads per layer (robustness)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = args.out or f"{args.device}_qec422_results.csv"

    calpath = pathlib.Path("calibrations") / f"{args.device}.json"
    if not calpath.exists():
        raise SystemExit(f"missing {calpath}; run pull_{args.device}.py first (free metadata).")
    d = json.loads(calpath.read_text())
    cm, nq = d["coupling_map"], int(d["num_qubits"])
    code_placements = derive_placements(cm, nq, 4)  # 4 data qubits

    backend = get_backend(args.device)
    print(f"backend {backend.name} | [[4,2,2]] Option C | placements {args.placements} | "
          f"layers {args.layers} | {args.shots} shots")
    print(f"  code-block placements: {code_placements}")
    print(">>> note credit balance NOW <<<\n")

    rows = []
    for placement in args.placements:
        layout4 = code_placements[placement]
        circuits, index, n2q_of = [], {}, {}
        for layers in args.layers:
            idxs = []
            for s in range(args.n_seeds):  # several random payloads -> robust estimate
                payload = random_clifford_payload(layers, args.seed + 100 * layers + s)
                mirror = build_detection_mirror(payload, detect=True)  # measures 4 data qubits
                tqc = transpile_for_backend(mirror, backend, initial_layout=layout4)
                n2q_of[layers] = sum(1 for i in tqc.data if i.operation.name in ("cz", "cx"))
                idxs.append(len(circuits))
                circuits.append(tqc)
            index[layers] = idxs

        all_counts = run_circuits(backend, circuits, args.shots)  # <=100/job (Resonance cap)
        for layers in args.layers:
            eb, ed, bares, dets, accs = [], [], [], [], []
            for j in index[layers]:
                counts = all_counts[j]
                bares.append(codespace_survival(counts))
                kept, acc = postselect_z_parity(counts)
                dets.append(codespace_survival(kept)); accs.append(acc)
                eb.append(abs(1.0 - logical_z_expval(counts, Z_LOGICAL1)))
                ed.append(abs(1.0 - logical_z_expval(kept, Z_LOGICAL1)))
            acc_m = float(np.mean(accs))
            eff = int(qec_effective_shots(args.shots, acc_m)) if acc_m > 0 else -1
            rows.append({"device": args.device, "placement": placement, "layers": layers,
                         "transpiled_cz": n2q_of[layers],
                         "err_bare": round(float(np.mean(eb)), 4),
                         "err_detected": round(float(np.mean(ed)), 4),
                         "err_detected_std": round(float(np.std(ed)), 4),
                         "bare_survival": round(float(np.mean(bares)), 4),
                         "detected_survival": round(float(np.mean(dets)), 4),
                         "acceptance": round(acc_m, 4), "n_seeds": args.n_seeds,
                         "shots": args.shots, "effective_shots": eff})
            print(f"  {placement:>8} L{layers} | 2q={n2q_of[layers]:>3} | "
                  f"logicalErr {np.mean(eb):.3f}->{np.mean(ed):.3f} | "
                  f"surv {np.mean(bares):.3f}->{np.mean(dets):.3f} | acc {acc_m:.3f} (n={args.n_seeds})")

    rows.sort(key=lambda r: (r["placement"], r["transpiled_cz"]))
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out}\n>>> note credit balance AGAIN — difference = cost <<<")


if __name__ == "__main__":
    main()
