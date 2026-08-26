"""Garnet hardware runner — optimal-vs-adverse mapping ladder with ZNE (methodology §7).

Submits the routing ladder to real Garnet via IQM Resonance, per placement, with
unitary-folding ZNE. Two modes:
  * gonogo : 2 patterns x 2 placements x 5 eval points x 3 scales, 1000 shots  (~cheap)
  * full   : 4 patterns x 2 placements x 15 eval points x 3 scales, 4096 shots

Circuits are FOLDED at the logical level, measured (clbit i <- logical qubit i, so
counts are in logical order and survive routing), then transpiled against the live
backend with the placement's initial_layout, and BATCHED into one job per
(placement, pattern) to amortise any per-job cost. Primary metric = mean
|<O> - <O>_ideal| vs the frozen noiseless reference; accuracy/F1 secondary.

REM is OFF for now (needs Garnet readout calibration); raw already includes readout
error. Run in YOUR terminal (IQM_RESONANCE_URL + IQM_TOKEN set). This SUBMITS to
hardware and spends credits — start with --mode gonogo.

    python run_garnet.py --mode gonogo
    python run_garnet.py --mode full --placements optimal adverse
"""

from __future__ import annotations

import argparse
import csv
import pathlib

import numpy as np
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from iqm_resonance import get_backend, run_circuits, transpile_for_backend
from metrics import accuracy, macro_f1
from noisy_sim import (
    load_frozen_model,
    logical_final_wires,
    observable_coeffs,
    perqubit_z_from_counts,
    rem_correct_z,
)
from topology import hardware_placement
from zne_dryrun import SCALE_FACTORS, extrapolate, fold_global

LADDER_PATTERNS = ["star", "linear", "circular", "all_to_all"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=["gonogo", "full"], default="gonogo")
    ap.add_argument("--placements", nargs="+", default=["optimal", "adverse"])
    ap.add_argument("--patterns", nargs="+", default=None)
    ap.add_argument("--shots", type=int, default=None)
    ap.add_argument("--eval-points", type=int, default=None)
    ap.add_argument("--device", default="garnet")
    ap.add_argument("--models-dir", default="trained_models",
                    help="model directory (trained_models_hard for the hard config)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    gonogo = args.mode == "gonogo"
    patterns = args.patterns or (["star", "all_to_all"] if gonogo else LADDER_PATTERNS)
    shots = args.shots or (1000 if gonogo else 4096)
    n_eval = args.eval_points or (5 if gonogo else 15)
    out = args.out or f"garnet_{args.mode}_results.csv"

    _, observable, cfg = load_frozen_model(models_dir=args.models_dir)
    n = cfg["n_qubits"]
    tag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
           f"{cfg['entanglement']}_{cfg['readout']}_L{cfg['n_layers']}")
    ref = np.load(pathlib.Path(args.models_dir) / f"{tag}_reference.npz")
    X_eval, y_eval = ref["X_eval"][:n_eval], ref["y_eval"][:n_eval]
    star_weights = np.load(pathlib.Path(args.models_dir) / cfg["weights_file"])
    coeffs = observable_coeffs(observable, n)

    # Readout errors for REM — classical post-processing on the SAME counts, so the
    # raw/+REM ablation costs zero extra shots. Pulled free by pull_garnet.py into
    # calibrations/<device>.json.
    p_ro = None
    calpath = pathlib.Path("calibrations") / f"{args.device}.json"
    if calpath.exists():
        import json
        d = json.loads(calpath.read_text())
        if "p_ro" in d:
            p_ro = np.asarray(d["p_ro"], float)
    print(f"REM: {'ON (readout cal loaded)' if p_ro is not None else 'OFF (no readout cal)'}")

    def weights_for(pattern):
        ptag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
                f"{pattern}_{cfg['readout']}_L{cfg['n_layers']}")
        wp = pathlib.Path(args.models_dir) / f"{ptag}_weights.npy"
        return np.load(wp) if wp.exists() else star_weights

    backend = get_backend(args.device)
    print(f"backend {backend.name} | mode {args.mode} | patterns {patterns} | "
          f"placements {args.placements} | {n_eval} pts | {shots} shots | scales {SCALE_FACTORS}")
    print(f">>> note your credit balance NOW <<<\n")

    rows = []
    for placement in args.placements:
        layout = hardware_placement(args.device, placement)
        for pattern in patterns:
            weights = weights_for(pattern)
            ans = HardwareEfficientAnsatz(n, cfg["n_layers"], num_features=cfg["n_features"],
                                          entanglement=pattern,
                                          entangling_gate=cfg.get("entangling_gate", "cx"))
            circ = ans.build()
            xparams = ans.feature_parameters(circ)
            wparams = ans.weight_parameters(circ)
            circ_w = circ.assign_parameters(dict(zip(wparams, weights)))

            # build folded+measured circuits for every (eval point, scale); one job
            batch, ideals = [], []
            for x in X_eval:
                bound = circ_w.assign_parameters(dict(zip(xparams, x)))
                ideals.append(float(np.real(
                    Statevector.from_instruction(bound).expectation_value(observable))))
                for s in SCALE_FACTORS:
                    folded = fold_global(bound, s)     # logical-level fold (barriers inside)
                    folded.measure_all()
                    batch.append(transpile_for_backend(folded, backend, initial_layout=layout))

            n2q = sum(1 for i in batch[0].data if i.operation.name in ("cz", "cx"))
            # chunked into <=100-circuit jobs (IQM Resonance job cap)
            counts_list = run_circuits(backend, batch, shots)

            # REM maps counts on LOGICAL wires; readout error follows each logical
            # qubit to its FINAL physical wire after routing.
            final_wires = logical_final_wires(batch[0], n)
            p_ro_log = (np.asarray([p_ro[w] for w in final_wires])
                        if p_ro is not None else None)

            # process: per eval point, 3 scale counts -> raw / +REM / +ZNE ablation.
            # raw and +REM come from the SAME counts (REM is classical) -> free ablation.
            err_raw, err_rem, err_zne = [], [], []
            pred_raw, pred_rem, pred_zne = [], [], []
            k = 0
            for ideal in ideals:
                raw_vals, rem_vals = [], []
                for _s in SCALE_FACTORS:
                    zq = perqubit_z_from_counts(counts_list[k], n)
                    k += 1
                    raw_vals.append(float(np.dot(coeffs, zq)))
                    rem_vals.append(float(np.dot(coeffs, rem_correct_z(zq, p_ro_log)))
                                    if p_ro_log is not None else raw_vals[-1])
                raw, rem = raw_vals[0], rem_vals[0]
                zne = extrapolate(SCALE_FACTORS, rem_vals, "richardson")  # REM then ZNE
                err_raw.append(abs(raw - ideal)); pred_raw.append(np.sign(raw))
                err_rem.append(abs(rem - ideal)); pred_rem.append(np.sign(rem))
                err_zne.append(abs(zne - ideal)); pred_zne.append(np.sign(zne))

            row = {
                "device": args.device, "placement": placement, "pattern": pattern,
                "transpiled_cz": n2q, "rem": p_ro is not None,
                "err_raw": round(float(np.mean(err_raw)), 4),
                "err_rem": round(float(np.mean(err_rem)), 4),
                "err_zne": round(float(np.mean(err_zne)), 4),
                # spread across eval points (within-window heterogeneity; the drift
                # band across calibration windows is the separate, primary uncertainty)
                "err_raw_std": round(float(np.std(err_raw)), 4),
                "err_zne_std": round(float(np.std(err_zne)), 4),
                "acc_raw": round(accuracy(y_eval, pred_raw), 4),
                "acc_rem": round(accuracy(y_eval, pred_rem), 4),
                "acc_zne": round(accuracy(y_eval, pred_zne), 4),
                "f1_raw": round(macro_f1(y_eval, pred_raw), 4),
                "f1_zne": round(macro_f1(y_eval, pred_zne), 4),
                "n_points": n_eval, "shots": shots,
            }
            rows.append(row)
            print(f"  {placement:>8} {pattern:>11} | 2q={n2q:>3} | "
                  f"err raw {row['err_raw']:.3f} -> +REM {row['err_rem']:.3f} -> "
                  f"+ZNE {row['err_zne']:.3f} | acc {row['acc_raw']:.2f}->{row['acc_zne']:.2f}")

    rows.sort(key=lambda r: (r["placement"], r["transpiled_cz"]))
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out}")
    print(">>> note your credit balance AGAIN — difference = campaign cost <<<")


if __name__ == "__main__":
    main()
