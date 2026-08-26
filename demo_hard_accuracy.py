"""Demonstrate ACCURACY RECOVERY on a harder two_curves (offset ~0.1) — sim, free.

Self-contained: does NOT touch the locked easy model. Trains per-pattern VQCs on a
harder task (points nearer the decision boundary -> small |<O>| margins that noise
can flip), then runs the calibrated-noise REM+ZNE pipeline and reports noiseless /
raw / ZNE accuracy. On the easy two_curves accuracy is saturated (~0.90) so ZNE
can't move it; on this harder task, noise degrades accuracy at high routing cost and
ZNE recovers it — the mechanism Month-1 saw on Banknote, now on two_curves(hard).

    python demo_hard_accuracy.py                       # star + all_to_all
    python demo_hard_accuracy.py --patterns star linear circular all_to_all --offset 0.1
"""

from __future__ import annotations

import os
# torch and qiskit-aer each ship an OpenMP runtime; loading both trips OMP Error
# #179. Set these BEFORE importing torch/aer to allow the duplicate and single-thread.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import csv
import pathlib

import numpy as np
import torch
from qiskit.quantum_info import SparsePauliOp, Statevector
from qiskit.primitives import StatevectorEstimator
from qiskit_machine_learning.connectors import TorchConnector
from qiskit_machine_learning.gradients import ParamShiftEstimatorGradient
from qiskit_machine_learning.neural_networks import EstimatorQNN
from qml_benchmarks.data import generate_two_curves
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

from ansatz import HardwareEfficientAnsatz
from metrics import accuracy, macro_f1
from noisy_sim import (
    DeviceCalibration,
    IQM_BASIS_GATES,
    execute_expectation,
    load_iqm_calibration,
    make_noisy_simulator,
    readout_observable,
)
from zne_dryrun import SCALE_FACTORS, extrapolate, fold_global, native_transpile

N_QUBITS, N_FEATURES, N_LAYERS = 5, 8, 3
DEGREE, NOISE, N_SAMPLES = 8, 0.01, 150
EPOCHS, LR, SEED = 60, 0.08, 42


def observable():
    terms = []
    for q in range(N_QUBITS):
        lab = ["I"] * N_QUBITS
        lab[N_QUBITS - 1 - q] = "Z"
        terms.append(("".join(lab), 1.0 / N_QUBITS))
    return SparsePauliOp.from_list(terms)


def build_qnn(pattern):
    vqc = HardwareEfficientAnsatz(N_QUBITS, N_LAYERS, num_features=N_FEATURES,
                                  entanglement=pattern)
    circ = vqc.build()
    est = StatevectorEstimator()
    qnn = EstimatorQNN(circuit=circ, observables=observable(),
                       input_params=vqc.feature_parameters(circ),
                       weight_params=vqc.weight_parameters(circ),
                       estimator=est, gradient=ParamShiftEstimatorGradient(est))
    return vqc, qnn


def train(qnn, n_weights, Xtr_t, ytr_t):
    w0 = 0.1 * np.random.default_rng(SEED).standard_normal(n_weights)
    model = TorchConnector(qnn, initial_weights=w0)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = torch.nn.MSELoss()
    for e in range(EPOCHS):
        opt.zero_grad()
        loss = loss_fn(model(Xtr_t), ytr_t)
        loss.backward()
        opt.step()
    return model.weight.detach().numpy()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--patterns", nargs="+", default=["star", "all_to_all"])
    ap.add_argument("--offset", type=float, default=0.1, help="smaller = harder (nearer boundary)")
    ap.add_argument("--shots", type=int, default=4096)
    ap.add_argument("--eval-size", type=int, default=30)
    ap.add_argument("--calibration", default="calibrations/odra.json")
    ap.add_argument("--out", default="hard_accuracy_results.csv")
    args = ap.parse_args()

    torch.manual_seed(SEED); np.random.seed(SEED)
    X, y = generate_two_curves(N_SAMPLES, N_FEATURES, degree=DEGREE,
                               offset=args.offset, noise=NOISE)
    y = y.astype(float)
    X = MinMaxScaler((-np.pi, np.pi)).fit_transform(X)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=SEED, stratify=y)

    # frozen stratified eval subset
    rng = np.random.default_rng(SEED)
    idx = np.arange(len(Xte))
    pos, neg = idx[yte > 0], idx[yte < 0]
    k = min(args.eval_size, len(Xte)) // 2
    sel = np.concatenate([rng.choice(pos, min(k, len(pos)), replace=False),
                          rng.choice(neg, min(args.eval_size - k, len(neg)), replace=False)])
    sel.sort()
    X_eval, y_eval = Xte[sel], yte[sel]

    obs = readout_observable(N_QUBITS, "mean")
    cal = (load_iqm_calibration(args.calibration)
           if pathlib.Path(args.calibration).exists() else DeviceCalibration())
    sim = make_noisy_simulator(cal, dd=False)

    print(f"two_curves HARD: degree {DEGREE}, offset {args.offset} | eval {len(X_eval)} pts | "
          f"shots {args.shots} | patterns {args.patterns}")
    print("  metric = accuracy: noiseless -> raw(noisy) -> +ZNE  (recovery at high cost)\n")

    Xtr_t = torch.tensor(Xtr, dtype=torch.float32)
    ytr_t = torch.tensor(ytr, dtype=torch.float32).view(-1, 1)

    rows = []
    for pattern in args.patterns:
        vqc, qnn = build_qnn(pattern)
        w = train(qnn, vqc.num_weights, Xtr_t, ytr_t)
        circ = vqc.build()
        xparams = vqc.feature_parameters(circ)
        wparams = vqc.weight_parameters(circ)
        circ_w = circ.assign_parameters(dict(zip(wparams, w)))

        # noiseless ideal + margin; noisy raw + ZNE per point
        ev_ideal, raw_ev, zne_ev = [], [], []
        n2q = None
        for x in X_eval:
            bound = circ_w.assign_parameters(dict(zip(xparams, x)))
            ev_ideal.append(float(np.real(Statevector.from_instruction(bound).expectation_value(obs))))
            native = native_transpile(bound, N_QUBITS)
            if n2q is None:
                n2q = sum(1 for i in native.data if i.operation.name == "cz")
            vals = [execute_expectation(fold_global(native, s), obs, sim, shots=args.shots,
                                        cal=cal, apply_idle_schedule=True,
                                        pre_transpiled=True, rem=True) for s in SCALE_FACTORS]
            raw_ev.append(vals[0])
            zne_ev.append(extrapolate(SCALE_FACTORS, vals, "richardson"))

        ev_ideal = np.asarray(ev_ideal)
        acc_ideal = accuracy(y_eval, np.sign(ev_ideal))
        acc_raw = accuracy(y_eval, np.sign(raw_ev))
        acc_zne = accuracy(y_eval, np.sign(zne_ev))
        margin = float(np.mean(np.abs(ev_ideal)))
        rows.append({"pattern": pattern, "transpiled_cz": n2q,
                     "mean_abs_margin": round(margin, 3),
                     "acc_ideal": round(acc_ideal, 3), "acc_raw": round(acc_raw, 3),
                     "acc_zne": round(acc_zne, 3),
                     "f1_raw": round(macro_f1(y_eval, np.sign(raw_ev)), 3),
                     "f1_zne": round(macro_f1(y_eval, np.sign(zne_ev)), 3),
                     "offset": args.offset, "shots": args.shots})
        print(f"  {pattern:>11} | 2q={n2q:>3} | margin {margin:.3f} | "
              f"acc ideal {acc_ideal:.2f} -> raw {acc_raw:.2f} -> ZNE {acc_zne:.2f}")

    rows.sort(key=lambda r: r["transpiled_cz"])
    with open(args.out, "w", newline="") as f:
        wcsv = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wcsv.writeheader()
        wcsv.writerows(rows)
    print(f"\nwrote {args.out}")
    print("Recovery = acc_zne > acc_raw (toward acc_ideal), appearing at high CZ where "
          "noise flips small-margin points — the regime easy two_curves can't reach.")


if __name__ == "__main__":
    main()
