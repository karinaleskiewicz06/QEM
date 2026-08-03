"""Noiseless VQC depth sweep for the ODRA / Month-1 locked experiment.

Locked parameters (plan.md §6 + dataset_specification.md):
  - n_qubits = 5          Tier-A ODRA star
  - n_features = 8        re-uploading (d > n); needs L*n >= d coverage
  - entanglement = star   native baseline; routing varies at inference
  - readout = mean-Z
  - optimizer = Adam + parameter-shift (hardware-compatible grads)
  - dataset = two_curves (real qml_benchmarks), degree=8, offset=0.3
  - seed = 42

Sweeps DEPTHS = [2, 3, 4, 5] (all L needed for degree=8 Fourier capacity /
model selection). After EACH depth:
  - appends a row to trained_models/depth_sweep_results.csv
  - saves weights + config JSON for that L

Usage:
  python train_vqc.py
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

# ---- LOCKED experiment settings ------------------------------------------
N_QUBITS, N_FEATURES = 5, 8
DEPTHS = [2, 3, 4, 5]                 # all depths needed for degree=8 capacity
ENTANGLEMENT = "star"
READOUT = "mean"
N_SAMPLES, DEGREE, OFFSET, NOISE = 150, 8, 0.3, 0.01
EPOCHS, LR, SEED = 60, 0.08, 42
# --------------------------------------------------------------------------

OUT_DIR = pathlib.Path("trained_models")
CSV_PATH = OUT_DIR / "depth_sweep_results.csv"
CSV_FIELDS = [
    "n_layers", "num_weights", "logical_2q_gates",
    "train_acc", "test_acc", "final_loss", "epochs", "seconds",
    "n_qubits", "n_features", "degree", "offset", "noise",
    "entanglement", "readout", "optimizer", "lr", "seed",
    "weights_file", "config_file", "tag",
]


def tag_for(L: int) -> str:
    return (
        f"two_curves_d{N_FEATURES}_q{N_QUBITS}_deg{DEGREE}_"
        f"{ENTANGLEMENT}_{READOUT}_L{L}"
    )


def build_qnn(n_layers: int):
    vqc = HardwareEfficientAnsatz(
        N_QUBITS, n_layers, num_features=N_FEATURES, entanglement=ENTANGLEMENT
    )
    circ = vqc.build()
    if READOUT == "hub":
        obs = SparsePauliOp.from_list([("I" * (N_QUBITS - 1) + "Z", 1.0)])
    elif READOUT == "mean":
        terms = []
        for q in range(N_QUBITS):
            label = ["I"] * N_QUBITS
            label[N_QUBITS - 1 - q] = "Z"
            terms.append(("".join(label), 1.0 / N_QUBITS))
        obs = SparsePauliOp.from_list(terms)
    else:
        raise ValueError(f"unknown READOUT {READOUT!r}")
    est = StatevectorEstimator()  # noiseless; no QEM
    qnn = EstimatorQNN(
        circuit=circ,
        observables=obs,
        input_params=vqc.feature_parameters(circ),
        weight_params=vqc.weight_parameters(circ),
        estimator=est,
        gradient=ParamShiftEstimatorGradient(est),
    )
    return vqc, qnn


def train(qnn, n_weights, Xtr_t, ytr_t):
    w0 = 0.1 * np.random.default_rng(SEED).standard_normal(n_weights)
    model = TorchConnector(qnn, initial_weights=w0)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = torch.nn.MSELoss()
    history = []
    for epoch in range(EPOCHS):
        optimizer.zero_grad()
        loss = loss_fn(model(Xtr_t), ytr_t)
        loss.backward()
        optimizer.step()
        history.append(loss.item())
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"    epoch {epoch + 1:>3}/{EPOCHS}  loss={history[-1]:.4f}", flush=True)
    return model.weight.detach().numpy(), history


def accuracy(qnn, w, Xs, ys) -> float:
    return float(np.mean(np.sign(qnn.forward(Xs, w).ravel()) == ys))


def append_csv(row: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    new_file = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new_file:
            w.writeheader()
        w.writerow({k: row[k] for k in CSV_FIELDS})


def save_depth(L: int, vqc, w, tr: float, te: float, history, seconds: float) -> dict:
    tag = tag_for(L)
    weights_file = f"{tag}_weights.npy"
    config_file = f"{tag}.json"
    np.save(OUT_DIR / weights_file, w)
    config = {
        "dataset": "two_curves",
        "generator": "qml_benchmarks.data.generate_two_curves",
        "n_samples": N_SAMPLES,
        "n_features": N_FEATURES,
        "degree": DEGREE,
        "offset": OFFSET,
        "noise": NOISE,
        "feature_range": [-float(np.pi), float(np.pi)],
        "n_qubits": N_QUBITS,
        "n_layers": L,
        "entanglement": ENTANGLEMENT,
        "entangling_gate": "cx",
        "readout": READOUT,
        "observable": (
            "Z on hub qubit 0" if READOUT == "hub" else "(1/n) sum_i Z_i (mean-Z)"
        ),
        "num_weights": int(vqc.num_weights),
        "logical_2q_gates": int(vqc.num_entangling_gates),
        "train_acc": float(tr),
        "test_acc": float(te),
        "final_loss": float(history[-1]),
        "optimizer": f"Adam(lr={LR})+parameter-shift",
        "epochs": EPOCHS,
        "seed": SEED,
        "weights_file": weights_file,
        "seconds": seconds,
        "note": (
            "Noiseless trained model. Rebuild with HardwareEfficientAnsatz and bind "
            "weights in weight_parameters() order. Apply DD/REM/folding/ZNE at "
            "inference only — do NOT retrain."
        ),
    }
    with (OUT_DIR / config_file).open("w") as f:
        json.dump(config, f, indent=2)

    row = {
        "n_layers": L,
        "num_weights": vqc.num_weights,
        "logical_2q_gates": vqc.num_entangling_gates,
        "train_acc": round(tr, 6),
        "test_acc": round(te, 6),
        "final_loss": round(history[-1], 6),
        "epochs": EPOCHS,
        "seconds": round(seconds, 1),
        "n_qubits": N_QUBITS,
        "n_features": N_FEATURES,
        "degree": DEGREE,
        "offset": OFFSET,
        "noise": NOISE,
        "entanglement": ENTANGLEMENT,
        "readout": READOUT,
        "optimizer": "Adam+parameter-shift",
        "lr": LR,
        "seed": SEED,
        "weights_file": weights_file,
        "config_file": config_file,
        "tag": tag,
    }
    append_csv(row)
    return config


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    # Fresh CSV for this sweep (keeps history under a timestamped backup if present)
    if CSV_PATH.exists():
        bak = OUT_DIR / f"depth_sweep_results_prev_{int(time.time())}.csv"
        CSV_PATH.rename(bak)
        print(f"previous CSV moved -> {bak}")

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    X, y = generate_two_curves(
        N_SAMPLES, N_FEATURES, degree=DEGREE, offset=OFFSET, noise=NOISE
    )
    y = y.astype(float)
    X = MinMaxScaler((-np.pi, np.pi)).fit_transform(X)
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.3, random_state=SEED, stratify=y
    )
    Xtr_t = torch.tensor(Xtr, dtype=torch.float32)
    ytr_t = torch.tensor(ytr, dtype=torch.float32).view(-1, 1)

    print("=" * 64)
    print("LOCKED noiseless VQC depth sweep")
    print(
        f"  two_curves n={N_SAMPLES} d={N_FEATURES} degree={DEGREE} "
        f"offset={OFFSET} noise={NOISE}"
    )
    print(
        f"  qubits={N_QUBITS} entanglement={ENTANGLEMENT} readout={READOUT}"
    )
    print(
        f"  Adam(lr={LR})+param-shift  epochs={EPOCHS}  seed={SEED}"
    )
    print(f"  DEPTHS={DEPTHS}  (re-uploading: L*n >= d requires L>={int(np.ceil(N_FEATURES/N_QUBITS))})")
    print("=" * 64)

    results = []
    for L in DEPTHS:
        print(f"\n>>> training L={L} ...", flush=True)
        t0 = time.time()
        vqc, qnn = build_qnn(L)
        w, history = train(qnn, vqc.num_weights, Xtr_t, ytr_t)
        tr = accuracy(qnn, w, Xtr, ytr)
        te = accuracy(qnn, w, Xte, yte)
        seconds = time.time() - t0
        cfg = save_depth(L, vqc, w, tr, te, history, seconds)
        results.append((L, tr, te, vqc.num_entangling_gates, seconds))
        print(
            f"<<< L={L} done in {seconds/60:.1f} min | "
            f"train={tr:.3f} test={te:.3f} | "
            f"saved {cfg['weights_file']} + CSV row",
            flush=True,
        )

    # Lock best: highest test acc, tie-break fewer 2q gates
    best_L = max(results, key=lambda r: (r[2], -r[3]))[0]
    lock_path = OUT_DIR / "LOCKED.json"
    lock = {
        "locked_tag": tag_for(best_L),
        "n_layers": best_L,
        "selection_rule": "max test_acc, tie-break fewer logical_2q_gates",
        "results": [
            {"L": L, "train_acc": tr, "test_acc": te, "logical_2q": ng, "seconds": s}
            for L, tr, te, ng, s in results
        ],
        "csv": str(CSV_PATH),
        "pass_criterion": "test_acc >= 0.90",
        "passed": bool(next(r[2] for r in results if r[0] == best_L) >= 0.90),
    }
    lock_path.write_text(json.dumps(lock, indent=2))

    print("\n" + "=" * 64)
    print(f"{'L':>3} {'train':>7} {'test':>7} {'2q':>4} {'min':>6}")
    for L, tr, te, ng, s in results:
        flag = "  <- LOCKED" if L == best_L else ""
        print(f"{L:>3} {tr:>7.3f} {te:>7.3f} {ng:>4} {s/60:>6.1f}{flag}")
    print(f"\nCSV -> {CSV_PATH}")
    print(f"lock pointer -> {lock_path}  (tag={tag_for(best_L)})")
    print("=" * 64)


if __name__ == "__main__":
    main()
