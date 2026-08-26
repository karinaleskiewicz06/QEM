"""CDR over the routing ladder — QEM method #2 runner (methodology_month_2.md §3).

Mirrors ``zne_dryrun.py`` but the mitigator is Clifford Data Regression instead of
ZNE. Per routing level (entangling pattern), on a chosen device+placement:

  1. build ``n_train`` near-Clifford training circuits with the level's structure,
  2. run them noisy (REM applied), pair with their exact ideal ⟨O⟩,
  3. fit ``ideal ≈ a·noisy + b``,
  4. apply (a,b) to every eval point's raw noisy ⟨O⟩,
  5. report err_raw -> err_cdr and accuracy, plus the fit r2 and effective shots.

Primary metric = mean |⟨O⟩ − ⟨O⟩_ideal| vs the frozen noiseless reference. Cost is
reported as effective shots (shots × (n_train+1)) so CDR is comparable to ZNE and
[[4,2,2]] on the shots-to-target axis.

Usage (sim; no credentials):
  python run_cdr.py --device odra   --quick
  python run_cdr.py --device odra   --n-train 100
  python run_cdr.py --device garnet --placement optimal --calibration <lattice.json>
  python run_cdr.py --device garnet --placement adverse --n-train 100
  python run_cdr.py --device odra   --dry-run          # build only, run nothing
Hardware (--submit) routes to the qiskit-iqm Resonance adapter (methodology §7).
"""

from __future__ import annotations

import argparse
import csv
import pathlib

import numpy as np
from qiskit import transpile
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from cdr import (
    apply_cdr,
    clifford_ideal_expval,
    fit_cdr,
    near_clifford_training_circuits,
)
from noisy_sim import (
    DeviceCalibration,
    IQM_BASIS_GATES,
    execute_expectation,
    load_frozen_model,
    load_iqm_calibration,
    make_noisy_simulator,
    synthesize_lattice_calibration,
)
from metrics import accuracy, macro_f1
from shots_to_target import cdr_effective_shots
from topology import device_coupling_map, placement

LADDER_PATTERNS = ["star", "linear", "circular", "all_to_all"]
OUT_CSV = "cdr_results.csv"


def _calibration_for(device: str, path: str) -> DeviceCalibration:
    if path:
        return load_iqm_calibration(path)
    if device in ("odra", "star"):
        return DeviceCalibration()
    return synthesize_lattice_calibration(device)


def _transpiled_cz(circ, cal, layout) -> int:
    tq = transpile(circ, basis_gates=IQM_BASIS_GATES, coupling_map=cal.coupling_map,
                   initial_layout=layout, optimization_level=1, seed_transpiler=42)
    return sum(1 for i in tq.data if i.operation.name == "cz")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="odra", help="odra/star, garnet, emerald")
    ap.add_argument("--placement", default="optimal", help="optimal or adverse")
    ap.add_argument("--n-train", type=int, default=100, help="near-Clifford training circuits")
    ap.add_argument("--shots", type=int, default=4096)
    ap.add_argument("--quick", action="store_true", help="small: 2 patterns, 6 pts, n_train 20")
    ap.add_argument("--calibration", default="", help="calibration JSON (else placeholder)")
    ap.add_argument("--no-rem", dest="rem", action="store_false")
    ap.set_defaults(rem=True)
    ap.add_argument("--dry-run", action="store_true", help="build circuits, run nothing")
    ap.add_argument("--submit", action="store_true", help="run on real hardware (qiskit-iqm)")
    ap.add_argument("--models-dir", default="trained_models",
                    help="model directory (trained_models_hard for the hard config)")
    ap.add_argument("--out", default=OUT_CSV)
    args = ap.parse_args()

    if args.submit:
        raise SystemExit(
            "hardware submit for CDR routes through iqm_resonance (methodology §7); "
            "run the sim path (no --submit) until the Resonance adapter is wired for your env."
        )

    _, observable, cfg = load_frozen_model(models_dir=args.models_dir)
    n = cfg["n_qubits"]
    tag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
           f"{cfg['entanglement']}_{cfg['readout']}_L{cfg['n_layers']}")
    ref = np.load(pathlib.Path(args.models_dir) / f"{tag}_reference.npz")
    X_eval, y_eval = ref["X_eval"], ref["y_eval"]
    star_weights = np.load(pathlib.Path(args.models_dir) / cfg["weights_file"])

    def weights_for(pattern):
        ptag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
                f"{pattern}_{cfg['readout']}_L{cfg['n_layers']}")
        wp = pathlib.Path(args.models_dir) / f"{ptag}_weights.npy"
        return (np.load(wp), True) if wp.exists() else (star_weights, False)

    n_train = 20 if args.quick else args.n_train
    patterns = ["star", "all_to_all"] if args.quick else LADDER_PATTERNS
    if args.quick:
        X_eval, y_eval = X_eval[:6], y_eval[:6]

    cal = _calibration_for(args.device, args.calibration)
    layout = None if cal.num_qubits == n else placement(args.device, n, args.placement)
    sim = make_noisy_simulator(cal)

    print(f"CDR | model {tag} | device {args.device} placement {args.placement}")
    print(f"  eval {len(X_eval)} pts | patterns {patterns} | n_train {n_train} | "
          f"shots {args.shots} | REM {'on' if args.rem else 'off'}")
    if layout is not None:
        print(f"  initial_layout ({args.placement}): {layout}")
    if args.dry_run:
        print("  [dry-run] building circuits, executing nothing.\n")

    x_mean = X_eval.mean(axis=0)
    rows = []
    for pattern in patterns:
        weights, per_pattern = weights_for(pattern)
        ans = HardwareEfficientAnsatz(n, cfg["n_layers"], num_features=cfg["n_features"],
                                      entanglement=pattern,
                                      entangling_gate=cfg.get("entangling_gate", "cx"))
        circ = ans.build()
        xparams = ans.feature_parameters(circ)
        wparams = ans.weight_parameters(circ)
        circ_w = circ.assign_parameters(dict(zip(wparams, weights)))

        # training set: bind a representative feature vector, then near-Clifford variants
        train_anchor = circ_w.assign_parameters(dict(zip(xparams, x_mean)))
        train_circuits = near_clifford_training_circuits(train_anchor, n_train=n_train, seed=42)
        n2q = _transpiled_cz(train_anchor, cal, layout)

        if args.dry_run:
            print(f"  {pattern:>11} | 2q={n2q:>3} | "
                  f"{len(train_circuits)} training circuits built, "
                  f"{len(X_eval)} eval circuits ready")
            rows.append({"device": args.device, "placement": args.placement,
                         "pattern": pattern, "transpiled_cz": n2q, "n_train": n_train,
                         "built": True})
            continue

        # fit CDR on the training set
        noisy_train, ideal_train = [], []
        for tc in train_circuits:
            ideal_train.append(clifford_ideal_expval(tc, observable))
            noisy_train.append(execute_expectation(
                tc, observable, sim, shots=args.shots, cal=cal,
                initial_layout=layout, apply_idle_schedule=True, rem=args.rem))
        a, b, r2 = fit_cdr(noisy_train, ideal_train)

        # apply to eval points
        err_raw, err_cdr, pred_raw, pred_cdr = [], [], [], []
        for x in X_eval:
            bound = circ_w.assign_parameters(dict(zip(xparams, x)))
            ideal = float(np.real(Statevector.from_instruction(bound).expectation_value(observable)))
            raw = execute_expectation(bound, observable, sim, shots=args.shots, cal=cal,
                                      initial_layout=layout, apply_idle_schedule=True, rem=args.rem)
            cdr_val = apply_cdr(raw, a, b)
            err_raw.append(abs(raw - ideal))
            err_cdr.append(abs(cdr_val - ideal))
            pred_raw.append(np.sign(raw))
            pred_cdr.append(np.sign(cdr_val))

        row = {
            "device": args.device, "placement": args.placement, "pattern": pattern,
            "transpiled_cz": n2q, "per_pattern_weights": per_pattern,
            "err_raw": round(float(np.mean(err_raw)), 4),
            "err_cdr": round(float(np.mean(err_cdr)), 4),
            "acc_raw": round(accuracy(y_eval, pred_raw), 4),
            "acc_cdr": round(accuracy(y_eval, pred_cdr), 4),
            "f1_raw": round(macro_f1(y_eval, pred_raw), 4),
            "f1_cdr": round(macro_f1(y_eval, pred_cdr), 4),
            "cdr_a": round(a, 4), "cdr_b": round(b, 4), "cdr_r2": round(r2, 4),
            "n_train": n_train, "shots": args.shots,
            "effective_shots": int(cdr_effective_shots(args.shots, n_train)),
        }
        rows.append(row)
        print(f"  {pattern:>11} | 2q={n2q:>3} | err {row['err_raw']:.3f}->{row['err_cdr']:.3f} "
              f"| acc {row['acc_raw']:.2f}->{row['acc_cdr']:.2f} "
              f"| F1 {row['f1_raw']:.2f}->{row['f1_cdr']:.2f} | r2={r2:.2f}")

    if rows:
        rows.sort(key=lambda r: r["transpiled_cz"])
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
