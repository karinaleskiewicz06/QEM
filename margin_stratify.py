"""Margin-stratified accuracy: is accuracy recovery gated by distance-to-boundary?

Free simulator experiment. The hypothesis (methodology): accuracy responds to
mitigation ONLY for points whose ideal margin |<O>_ideal| is small enough that
noise flips their sign. Aggregate accuracy hides this because it pools near- and
far-boundary points; far points are saturated (never flip) and wash out the signal.

This script pools per-point (|<O>_ideal|, y, sign(raw), sign(+ZNE)) over the given
high-cost patterns, bins by |<O>_ideal| (near / mid / far terciles), and reports
accuracy noiseless / raw / +ZNE PER BIN. If the mechanism holds, the near bin shows
acc_raw << acc_zne (recovery), the far bin shows both saturated.

    python margin_stratify.py                                  # all_to_all, offset 0.1
    python margin_stratify.py --patterns all_to_all circular --eval-size 120
"""

from __future__ import annotations

import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import csv
import pathlib

import numpy as np
import torch
from qiskit.quantum_info import Statevector
from qiskit.primitives import StatevectorEstimator
from qiskit_machine_learning.connectors import TorchConnector
from qiskit_machine_learning.gradients import ParamShiftEstimatorGradient
from qiskit_machine_learning.neural_networks import EstimatorQNN
from qml_benchmarks.data import generate_two_curves
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

from ansatz import HardwareEfficientAnsatz
from metrics import accuracy
from noisy_sim import (
    DeviceCalibration,
    execute_expectation,
    load_iqm_calibration,
    make_noisy_simulator,
    readout_observable,
)  # readout_observable: "mean" -> (1/n)ΣZ, "hub" -> single Z on qubit 0
from zne_dryrun import SCALE_FACTORS, extrapolate, fold_global, native_transpile

N_QUBITS, N_FEATURES, N_LAYERS = 5, 8, 3
DEGREE, NOISE, N_SAMPLES = 8, 0.01, 300
EPOCHS, LR, SEED = 60, 0.08, 42


def build_qnn(pattern, obs):
    vqc = HardwareEfficientAnsatz(N_QUBITS, N_LAYERS, num_features=N_FEATURES,
                                  entanglement=pattern)
    circ = vqc.build()
    est = StatevectorEstimator()
    qnn = EstimatorQNN(circuit=circ, observables=obs,
                       input_params=vqc.feature_parameters(circ),
                       weight_params=vqc.weight_parameters(circ),
                       estimator=est, gradient=ParamShiftEstimatorGradient(est))
    return vqc, qnn


def train(qnn, n_weights, Xtr_t, ytr_t):
    w0 = 0.1 * np.random.default_rng(SEED).standard_normal(n_weights)
    model = TorchConnector(qnn, initial_weights=w0)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = torch.nn.MSELoss()
    for _ in range(EPOCHS):
        opt.zero_grad()
        loss = loss_fn(model(Xtr_t), ytr_t)
        loss.backward()
        opt.step()
    return model.weight.detach().numpy()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--patterns", nargs="+", default=["all_to_all"],
                    help="high-cost patterns to pool (more noise -> more flips)")
    ap.add_argument("--offset", type=float, default=0.1)
    ap.add_argument("--shots", type=int, default=4096)
    ap.add_argument("--eval-size", type=int, default=120)
    ap.add_argument("--observable", choices=["mean", "hub"], default="mean",
                    help="mean=(1/n)ΣZ (compressed margins); hub=single Z on q0 (full [-1,1] range)")
    ap.add_argument("--calibration", default="calibrations/odra.json")
    ap.add_argument("--out", default="margin_stratify_results.csv")
    args = ap.parse_args()

    torch.manual_seed(SEED); np.random.seed(SEED)
    X, y = generate_two_curves(N_SAMPLES, N_FEATURES, degree=DEGREE,
                               offset=args.offset, noise=NOISE)
    y = y.astype(float)
    X = MinMaxScaler((-np.pi, np.pi)).fit_transform(X)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=SEED, stratify=y)

    rng = np.random.default_rng(SEED)
    idx = np.arange(len(Xte))
    pos, neg = idx[yte > 0], idx[yte < 0]
    k = min(args.eval_size, len(Xte)) // 2
    sel = np.concatenate([rng.choice(pos, min(k, len(pos)), replace=False),
                          rng.choice(neg, min(args.eval_size - k, len(neg)), replace=False)])
    sel.sort()
    X_eval, y_eval = Xte[sel], yte[sel]

    obs = readout_observable(N_QUBITS, args.observable)
    cal = (load_iqm_calibration(args.calibration)
           if pathlib.Path(args.calibration).exists() else DeviceCalibration())
    sim = make_noisy_simulator(cal, dd=False)

    print(f"margin stratification | obs={args.observable} | offset {args.offset} | "
          f"eval {len(X_eval)} pts x {len(args.patterns)} pattern(s) | shots {args.shots}")
    print("  pooling per-point (|<O>_ideal|, y, sign raw, sign +ZNE) across patterns\n")

    Xtr_t = torch.tensor(Xtr, dtype=torch.float32)
    ytr_t = torch.tensor(ytr, dtype=torch.float32).view(-1, 1)

    # pooled per-point records across patterns
    P_margin, P_y, P_sraw, P_szne = [], [], [], []
    for pattern in args.patterns:
        vqc, qnn = build_qnn(pattern, obs)
        w = train(qnn, vqc.num_weights, Xtr_t, ytr_t)
        circ = vqc.build()
        xparams = vqc.feature_parameters(circ)
        wparams = vqc.weight_parameters(circ)
        circ_w = circ.assign_parameters(dict(zip(wparams, w)))
        n2q = None
        for x, yy in zip(X_eval, y_eval):
            bound = circ_w.assign_parameters(dict(zip(xparams, x)))
            ideal = float(np.real(Statevector.from_instruction(bound).expectation_value(obs)))
            native = native_transpile(bound, N_QUBITS)
            if n2q is None:
                n2q = sum(1 for i in native.data if i.operation.name == "cz")
            vals = [execute_expectation(fold_global(native, s), obs, sim, shots=args.shots,
                                        cal=cal, apply_idle_schedule=True,
                                        pre_transpiled=True, rem=True) for s in SCALE_FACTORS]
            P_margin.append(abs(ideal)); P_y.append(yy)
            P_sraw.append(np.sign(vals[0]))
            P_szne.append(np.sign(extrapolate(SCALE_FACTORS, vals, "richardson")))
        print(f"  {pattern:>11} | 2q={n2q:>3} | {len(X_eval)} pts done")

    P_margin = np.asarray(P_margin); P_y = np.asarray(P_y)
    P_sraw = np.asarray(P_sraw); P_szne = np.asarray(P_szne)

    # tercile bins by ideal margin
    q1, q2 = np.quantile(P_margin, [1 / 3, 2 / 3])
    bins = [("near", P_margin <= q1),
            ("mid", (P_margin > q1) & (P_margin <= q2)),
            ("far", P_margin > q2)]

    print(f"\n  margin terciles: near<= {q1:.3f} < mid <= {q2:.3f} < far")
    print("  bin  |  n | <|margin|> | acc_raw -> acc_ZNE | recovery")
    rows = []
    for name, m in bins:
        n = int(m.sum())
        if n == 0:
            continue
        acc_raw = accuracy(P_y[m], P_sraw[m])
        acc_zne = accuracy(P_y[m], P_szne[m])
        rows.append({"bin": name, "n": n,
                     "mean_abs_margin": round(float(P_margin[m].mean()), 4),
                     "acc_raw": round(acc_raw, 4), "acc_zne": round(acc_zne, 4),
                     "recovery": round(acc_zne - acc_raw, 4),
                     "observable": args.observable,
                     "offset": args.offset, "shots": args.shots,
                     "patterns": "+".join(args.patterns)})
        print(f"  {name:>4} | {n:>2} |   {P_margin[m].mean():.3f}    | "
              f"{acc_raw:.3f} -> {acc_zne:.3f}    | {acc_zne - acc_raw:+.3f}")

    with open(args.out, "w", newline="") as f:
        wcsv = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wcsv.writeheader()
        wcsv.writerows(rows)
    print(f"\nwrote {args.out}")
    print("Mechanism confirmed if: near bin recovery > 0 (ZNE un-flips), far bin ~0 (saturated).")


if __name__ == "__main__":
    main()
