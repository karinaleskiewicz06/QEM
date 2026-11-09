"""Train the same classifier architecture on two other datasets (simulation only).

Generality check for the decision analysis: one LINEAR task (qml_benchmarks
linearly_separable) and one NON-LINEAR task (hidden_manifold_model), 8 features, same
ansatz, same mean-Z readout, same training settings as the two_curves models
(train_patterns: 5 qubits, L3, 60 epochs Adam). Patterns star / circular / all_to_all
(12 / 39 / 57 CZ). Each dataset gets a frozen 100-point eval set (class balanced).

    python -m paper_analysis.train_other linear
    python -m paper_analysis.train_other manifold
"""
from __future__ import annotations

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import json  # noqa: E402
import pathlib  # noqa: E402
import sys  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from qml_benchmarks.data import generate_hidden_manifold_model, generate_linearly_separable  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.preprocessing import MinMaxScaler  # noqa: E402

from train_patterns import N_FEATURES, N_LAYERS, N_QUBITS, SEED, acc, build_qnn, train  # noqa: E402

PATTERNS = ["star", "circular", "all_to_all"]
N_SAMPLES, TEST_SIZE, EVAL = 300, 0.4, 100
OUT = REPO / "trained_models_other"


def data(name):
    np.random.seed(SEED)
    if name == "linear":
        X, y = generate_linearly_separable(N_SAMPLES, N_FEATURES, margin=0.02)
    elif name == "manifold":
        X, y = generate_hidden_manifold_model(N_SAMPLES, N_FEATURES, manifold_dimension=3)
    else:
        raise SystemExit(f"unknown dataset {name!r}; expected linear or manifold")
    y = np.where(np.asarray(y, float) > 0, 1.0, -1.0)
    return MinMaxScaler((-np.pi, np.pi)).fit_transform(X), y


def main(name):
    out = OUT / name
    out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(SEED)
    X, y = data(name)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=TEST_SIZE, random_state=SEED, stratify=y)
    rng = np.random.default_rng(SEED)
    pos, neg = np.flatnonzero(yte > 0), np.flatnonzero(yte < 0)
    k = min(EVAL // 2, len(pos), len(neg))
    sel = np.concatenate([rng.choice(pos, k, replace=False), rng.choice(neg, k, replace=False)])
    np.savez(out / "reference.npz", X_eval=Xte[sel], y_eval=yte[sel])
    summary = {}
    for pattern in PATTERNS:
        vqc, qnn = build_qnn(pattern)
        w, hist = train(qnn, vqc.num_weights,
                        torch.tensor(Xtr, dtype=torch.float32),
                        torch.tensor(ytr, dtype=torch.float32).view(-1, 1))
        tr, te = acc(qnn, w, Xtr, ytr), acc(qnn, w, Xte, yte)
        np.save(out / f"{pattern}_L{N_LAYERS}_weights.npy", w)
        summary[pattern] = {"train_acc": tr, "test_acc": te, "final_loss": hist[-1]}
        print(f"{name} {pattern}: train {tr:.3f} test {te:.3f}", flush=True)
    (out / "models.json").write_text(json.dumps({
        "dataset": name, "n_samples": N_SAMPLES, "n_features": N_FEATURES, "n_qubits": N_QUBITS,
        "n_layers": N_LAYERS, "seed": SEED, "eval_points": int(len(sel)), "models": summary},
        indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
