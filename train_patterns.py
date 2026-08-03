"""Per-entanglement-pattern training at the locked depth (methodological upgrade).

For the routing/ZNE study each routing level must be a REAL classifier, not the
star weights borrowed onto another connectivity. This trains one VQC per
entanglement pattern at the locked (n=5, L=3) settings, on the identical
two_curves data/split/seed as the locked model, and saves per-pattern weights +
config so zne_dryrun.py can use the correct classifier at every routing level.

Matched expressivity: num_weights is pattern-independent, so all levels have the
same trainable capacity (plan.md §8: native vs non-native at matched expressivity).

Usage: python train_patterns.py
"""

from __future__ import annotations

import csv
import json
import pathlib
import time

import numpy as np
import torch
from qml_benchmarks.data import generate_two_curves
from qiskit.primitives import StatevectorEstimator
from qiskit.quantum_info import SparsePauliOp
from qiskit_machine_learning.connectors import TorchConnector
from qiskit_machine_learning.gradients import ParamShiftEstimatorGradient
from qiskit_machine_learning.neural_networks import EstimatorQNN
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

from ansatz import HardwareEfficientAnsatz

# ---- LOCKED settings (must match train_vqc.py / the frozen reference) ----
N_QUBITS, N_FEATURES, N_LAYERS = 5, 8, 3
PATTERNS = ["star", "linear", "circular", "all_to_all"]
READOUT = "mean"
N_SAMPLES, DEGREE, OFFSET, NOISE = 150, 8, 0.3, 0.01
EPOCHS, LR, SEED = 60, 0.08, 42
# --------------------------------------------------------------------------

OUT_DIR = pathlib.Path("trained_models")
CSV_PATH = OUT_DIR / "pattern_sweep_results.csv"
CSV_FIELDS = [
    "pattern", "n_layers", "num_weights", "logical_2q_gates",
    "train_acc", "test_acc", "final_loss", "seconds",
    "n_qubits", "n_features", "degree", "offset", "seed",
    "weights_file", "config_file", "tag",
]


def observable():
    terms = []
    for q in range(N_QUBITS):
        label = ["I"] * N_QUBITS
        label[N_QUBITS - 1 - q] = "Z"
        terms.append(("".join(label), 1.0 / N_QUBITS))
    return SparsePauliOp.from_list(terms)


def build_qnn(pattern: str):
    vqc = HardwareEfficientAnsatz(
        N_QUBITS, N_LAYERS, num_features=N_FEATURES, entanglement=pattern
    )
    circ = vqc.build()
    est = StatevectorEstimator()
    qnn = EstimatorQNN(
        circuit=circ, observables=observable(),
        input_params=vqc.feature_parameters(circ),
        weight_params=vqc.weight_parameters(circ),
        estimator=est, gradient=ParamShiftEstimatorGradient(est),
    )
    return vqc, qnn


def train(qnn, n_weights, Xtr_t, ytr_t):
    w0 = 0.1 * np.random.default_rng(SEED).standard_normal(n_weights)
    model = TorchConnector(qnn, initial_weights=w0)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = torch.nn.MSELoss()
    hist = []
    for e in range(EPOCHS):
        opt.zero_grad()
        loss = loss_fn(model(Xtr_t), ytr_t)
        loss.backward()
        opt.step()
        hist.append(loss.item())
        if (e + 1) % 20 == 0 or e == 0:
            print(f"    epoch {e+1:>3}/{EPOCHS} loss={hist[-1]:.4f}", flush=True)
    return model.weight.detach().numpy(), hist


def acc(qnn, w, Xs, ys):
    return float(np.mean(np.sign(qnn.forward(Xs, w).ravel()) == ys))


def main():
    OUT_DIR.mkdir(exist_ok=True)
    if CSV_PATH.exists():
        CSV_PATH.rename(OUT_DIR / f"pattern_sweep_results_prev_{int(time.time())}.csv")

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    X, y = generate_two_curves(N_SAMPLES, N_FEATURES, degree=DEGREE,
                               offset=OFFSET, noise=NOISE)
    y = y.astype(float)
    X = MinMaxScaler((-np.pi, np.pi)).fit_transform(X)
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.3, random_state=SEED, stratify=y
    )
    Xtr_t = torch.tensor(Xtr, dtype=torch.float32)
    ytr_t = torch.tensor(ytr, dtype=torch.float32).view(-1, 1)

    print("=" * 60)
    print(f"per-pattern training  L={N_LAYERS}  patterns={PATTERNS}")
    print(f"two_curves d={N_FEATURES} degree={DEGREE} offset={OFFSET} seed={SEED}")
    print("=" * 60)

    results = []
    for pattern in PATTERNS:
        print(f"\n>>> pattern={pattern}", flush=True)
        t0 = time.time()
        vqc, qnn = build_qnn(pattern)
        w, hist = train(qnn, vqc.num_weights, Xtr_t, ytr_t)
        tr, te = acc(qnn, w, Xtr, ytr), acc(qnn, w, Xte, yte)
        secs = time.time() - t0

        tag = f"two_curves_d{N_FEATURES}_q{N_QUBITS}_deg{DEGREE}_{pattern}_{READOUT}_L{N_LAYERS}"
        wfile = f"{tag}_weights.npy"
        np.save(OUT_DIR / wfile, w)
        cfg = {
            "dataset": "two_curves", "n_samples": N_SAMPLES,
            "n_features": N_FEATURES, "degree": DEGREE, "offset": OFFSET,
            "noise": NOISE, "feature_range": [-float(np.pi), float(np.pi)],
            "n_qubits": N_QUBITS, "n_layers": N_LAYERS, "entanglement": pattern,
            "entangling_gate": "cx", "readout": READOUT,
            "observable": "(1/n) sum_i Z_i (mean-Z)",
            "num_weights": int(vqc.num_weights),
            "logical_2q_gates": int(vqc.num_entangling_gates),
            "train_acc": tr, "test_acc": te, "final_loss": float(hist[-1]),
            "optimizer": f"Adam(lr={LR})+parameter-shift", "epochs": EPOCHS,
            "seed": SEED, "weights_file": wfile,
        }
        (OUT_DIR / f"{tag}.json").write_text(json.dumps(cfg, indent=2))

        row = {
            "pattern": pattern, "n_layers": N_LAYERS,
            "num_weights": vqc.num_weights,
            "logical_2q_gates": vqc.num_entangling_gates,
            "train_acc": round(tr, 6), "test_acc": round(te, 6),
            "final_loss": round(hist[-1], 6), "seconds": round(secs, 1),
            "n_qubits": N_QUBITS, "n_features": N_FEATURES, "degree": DEGREE,
            "offset": OFFSET, "seed": SEED, "weights_file": wfile,
            "config_file": f"{tag}.json", "tag": tag,
        }
        new = not CSV_PATH.exists()
        with CSV_PATH.open("a", newline="") as f:
            wcsv = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if new:
                wcsv.writeheader()
            wcsv.writerow(row)
        results.append((pattern, vqc.num_entangling_gates, tr, te, secs))
        print(f"<<< {pattern}: 2q={vqc.num_entangling_gates} "
              f"train={tr:.3f} test={te:.3f} ({secs/60:.1f} min) -> {wfile}",
              flush=True)

    print("\n" + "=" * 60)
    print(f"{'pattern':>11} {'2q':>4} {'train':>7} {'test':>7} {'min':>6}")
    for p, ng, tr, te, s in results:
        print(f"{p:>11} {ng:>4} {tr:>7.3f} {te:>7.3f} {s/60:>6.1f}")
    print(f"\nCSV -> {CSV_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
