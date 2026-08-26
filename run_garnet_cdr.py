"""CDR on hardware (methodology §3/§7) — QEM method #2 on a real device.

Per (placement, pattern): build near-Clifford training circuits (structure of the
level) + eval circuits, submit batched to the device, compute noisy <O> (with REM),
fit ideal ~ a*noisy + b on the training pairs, apply to eval. Reports err_raw ->
err_cdr, accuracy, F1, fit r2, effective shots. Device-generic via --device.

Budget note: cost scales with n_train — keep it small on hardware (40 default; 200
would be ~5x). REM is free (classical, same counts).

    python run_garnet_cdr.py --device garnet --n-train 40
    python run_garnet_cdr.py --device emerald --n-train 30 --patterns star all_to_all
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib

import numpy as np
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from cdr import apply_cdr, clifford_ideal_expval, fit_cdr, near_clifford_training_circuits
from iqm_resonance import get_backend, run_circuits, transpile_for_backend
from metrics import accuracy, macro_f1
from noisy_sim import (
    load_frozen_model,
    logical_final_wires,
    observable_coeffs,
    perqubit_z_from_counts,
    rem_correct_z,
)
from shots_to_target import cdr_effective_shots
from topology import hardware_placement

LADDER_PATTERNS = ["star", "linear", "circular", "all_to_all"]


def _noisy_ev(counts, coeffs, n, p_ro_log):
    zq = perqubit_z_from_counts(counts, n)
    if p_ro_log is not None:
        zq = rem_correct_z(zq, p_ro_log)
    return float(np.dot(coeffs, zq))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="garnet")
    ap.add_argument("--placements", nargs="+", default=["optimal", "adverse"])
    ap.add_argument("--patterns", nargs="+", default=["star", "all_to_all"])
    ap.add_argument("--n-train", type=int, default=40)
    ap.add_argument("--eval-points", type=int, default=15)
    ap.add_argument("--shots", type=int, default=2048)
    ap.add_argument("--models-dir", default="trained_models",
                    help="model directory (trained_models_hard for the hard config)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = args.out or f"{args.device}_cdr_results.csv"

    _, observable, cfg = load_frozen_model(models_dir=args.models_dir)
    n = cfg["n_qubits"]
    tag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
           f"{cfg['entanglement']}_{cfg['readout']}_L{cfg['n_layers']}")
    ref = np.load(pathlib.Path(args.models_dir) / f"{tag}_reference.npz")
    X_eval, y_eval = ref["X_eval"][:args.eval_points], ref["y_eval"][:args.eval_points]
    star_weights = np.load(pathlib.Path(args.models_dir) / cfg["weights_file"])
    coeffs = observable_coeffs(observable, n)
    x_mean = X_eval.mean(axis=0)

    p_ro = None
    calpath = pathlib.Path("calibrations") / f"{args.device}.json"
    if calpath.exists():
        d = json.loads(calpath.read_text())
        p_ro = np.asarray(d["p_ro"], float) if "p_ro" in d else None
    print(f"REM: {'ON' if p_ro is not None else 'OFF'}")

    def weights_for(pattern):
        ptag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
                f"{pattern}_{cfg['readout']}_L{cfg['n_layers']}")
        wp = pathlib.Path(args.models_dir) / f"{ptag}_weights.npy"
        return np.load(wp) if wp.exists() else star_weights

    backend = get_backend(args.device)
    print(f"backend {backend.name} | CDR | placements {args.placements} | "
          f"patterns {args.patterns} | n_train {args.n_train} | {len(X_eval)} pts | "
          f"{args.shots} shots")
    print(">>> note credit balance NOW <<<\n")

    rows = []
    for placement in args.placements:
        layout = hardware_placement(args.device, placement)
        for pattern in args.patterns:
            ans = HardwareEfficientAnsatz(n, cfg["n_layers"], num_features=cfg["n_features"],
                                          entanglement=pattern,
                                          entangling_gate=cfg.get("entangling_gate", "cx"))
            circ = ans.build()
            xparams = ans.feature_parameters(circ)
            wparams = ans.weight_parameters(circ)
            circ_w = circ.assign_parameters(dict(zip(wparams, weights_for(pattern))))

            # training circuits (near-Clifford) + their exact ideals
            anchor = circ_w.assign_parameters(dict(zip(xparams, x_mean)))
            train = near_clifford_training_circuits(anchor, n_train=args.n_train, seed=42)
            ideal_train = [clifford_ideal_expval(tc, observable) for tc in train]
            # eval circuits + exact ideals
            eval_circs, ideal_eval = [], []
            for x in X_eval:
                b = circ_w.assign_parameters(dict(zip(xparams, x)))
                eval_circs.append(b)
                ideal_eval.append(float(np.real(
                    Statevector.from_instruction(b).expectation_value(observable))))

            # transpile all (measure before transpile -> logical-order counts), batch
            batch = []
            for c in train + eval_circs:
                cm = c.copy()
                cm.measure_all()
                batch.append(transpile_for_backend(cm, backend, initial_layout=layout))
            n2q = sum(1 for i in batch[0].data if i.operation.name in ("cz", "cx"))
            p_ro_log = (np.asarray([p_ro[w] for w in logical_final_wires(batch[0], n)])
                        if p_ro is not None else None)

            counts = run_circuits(backend, batch, args.shots)  # <=100/job (Resonance cap)

            noisy_train = [_noisy_ev(counts[j], coeffs, n, p_ro_log) for j in range(len(train))]
            a, b, r2 = fit_cdr(noisy_train, ideal_train)

            err_raw, err_cdr, pred_raw, pred_cdr = [], [], [], []
            for e, (ideal, _c) in enumerate(zip(ideal_eval, eval_circs)):
                raw = _noisy_ev(counts[len(train) + e], coeffs, n, p_ro_log)
                cdr_val = apply_cdr(raw, a, b)
                err_raw.append(abs(raw - ideal)); pred_raw.append(np.sign(raw))
                err_cdr.append(abs(cdr_val - ideal)); pred_cdr.append(np.sign(cdr_val))

            row = {
                "device": args.device, "placement": placement, "pattern": pattern,
                "transpiled_cz": n2q, "rem": p_ro is not None,
                "err_raw": round(float(np.mean(err_raw)), 4),
                "err_cdr": round(float(np.mean(err_cdr)), 4),
                "acc_raw": round(accuracy(y_eval, pred_raw), 4),
                "acc_cdr": round(accuracy(y_eval, pred_cdr), 4),
                "f1_raw": round(macro_f1(y_eval, pred_raw), 4),
                "f1_cdr": round(macro_f1(y_eval, pred_cdr), 4),
                "cdr_a": round(a, 4), "cdr_b": round(b, 4), "cdr_r2": round(r2, 4),
                "n_train": args.n_train, "shots": args.shots,
                "effective_shots": int(cdr_effective_shots(args.shots, args.n_train)),
            }
            rows.append(row)
            print(f"  {placement:>8} {pattern:>11} | 2q={n2q:>3} | "
                  f"err {row['err_raw']:.3f}->{row['err_cdr']:.3f} | "
                  f"acc {row['acc_raw']:.2f}->{row['acc_cdr']:.2f} | r2={r2:.2f}")

    rows.sort(key=lambda r: (r["placement"], r["transpiled_cz"]))
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out}\n>>> note credit balance AGAIN — difference = cost <<<")


if __name__ == "__main__":
    main()
