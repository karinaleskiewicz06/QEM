"""Train + freeze the HARD two_curves model (offset 0.1) into trained_models_hard/.

'Everything on hard': a coherent, harder task where accuracy responds to mitigation.
Separate directory so the locked easy model is untouched; runners point here with
--models-dir trained_models_hard. Larger sample count so the frozen eval subset has
100 points (accuracy is high-variance -> needs many points to be solid in sim).

Reuses train_patterns primitives. Free (simulator). ~tens of minutes for 4 patterns.

    python train_hard.py
"""

from __future__ import annotations

import os
# torch + aer each ship OpenMP; set before importing either (OMP Error #179).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import json
import pathlib

import numpy as np
import torch
from qiskit import transpile
from qiskit.quantum_info import Statevector
from qml_benchmarks.data import generate_two_curves
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

from train_patterns import (
    DEGREE, N_FEATURES, N_LAYERS, N_QUBITS, NOISE, PATTERNS, READOUT, SEED,
    acc, build_qnn, observable, train,
)
from noisy_sim import IQM_BASIS_GATES, observable_coeffs, readout_observable, star_coupling_map

OFFSET = 0.1          # harder: points nearer the decision boundary
N_SAMPLES = 300       # -> ~120 test points, enough for a 100-point eval subset
TEST_SIZE = 0.4
EVAL_SIZE = 100
OUT = pathlib.Path("trained_models_hard")


def balanced_interleaved(idx_pos, idx_neg, m, rng):
    """Pick m points, class-balanced AND interleaved so any prefix stays ~balanced."""
    k = m // 2
    p = rng.choice(idx_pos, size=min(k, len(idx_pos)), replace=False)
    q = rng.choice(idx_neg, size=min(m - k, len(idx_neg)), replace=False)
    out = []
    for i in range(max(len(p), len(q))):
        if i < len(p):
            out.append(p[i])
        if i < len(q):
            out.append(q[i])
    return np.asarray(out)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    X, y = generate_two_curves(N_SAMPLES, N_FEATURES, degree=DEGREE, offset=OFFSET, noise=NOISE)
    y = y.astype(float)
    X = MinMaxScaler((-np.pi, np.pi)).fit_transform(X)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=TEST_SIZE, random_state=SEED, stratify=y)
    Xtr_t = torch.tensor(Xtr, dtype=torch.float32)
    ytr_t = torch.tensor(ytr, dtype=torch.float32).view(-1, 1)

    print(f"HARD two_curves: degree {DEGREE}, offset {OFFSET}, N={N_SAMPLES} "
          f"-> {len(Xte)} test pts | training {len(PATTERNS)} patterns\n")

    star_tag = None
    for pattern in PATTERNS:
        vqc, qnn = build_qnn(pattern)
        w, _ = train(qnn, vqc.num_weights, Xtr_t, ytr_t)  # train() returns (weights, history)
        tr, te = acc(qnn, w, Xtr, ytr), acc(qnn, w, Xte, yte)
        tag = f"two_curves_d{N_FEATURES}_q{N_QUBITS}_deg{DEGREE}_{pattern}_{READOUT}_L{N_LAYERS}"
        if pattern == "star":
            star_tag = tag
        np.save(OUT / f"{tag}_weights.npy", w)
        cfg = {
            "dataset": "two_curves", "n_samples": N_SAMPLES, "n_features": N_FEATURES,
            "degree": DEGREE, "offset": OFFSET, "noise": NOISE,
            "feature_range": [-float(np.pi), float(np.pi)],
            "n_qubits": N_QUBITS, "n_layers": N_LAYERS, "entanglement": pattern,
            "entangling_gate": "cx", "readout": READOUT,
            "observable": "(1/n) sum_i Z_i (mean-Z)",
            "num_weights": int(vqc.num_weights),
            "logical_2q_gates": int(vqc.num_entangling_gates),
            "train_acc": tr, "test_acc": te, "seed": SEED,
            "weights_file": f"{tag}_weights.npy",
        }
        (OUT / f"{tag}.json").write_text(json.dumps(cfg, indent=2))
        print(f"  {pattern:>11}: train {tr:.3f}  test {te:.3f}  -> {tag}_weights.npy")

    (OUT / "LOCKED.json").write_text(json.dumps({"locked_tag": star_tag}, indent=2))

    # ---- freeze reference (shared eval subset; ideal recomputed per pattern by runners) ----
    from noisy_sim import load_frozen_model
    circ, obs, cfg = load_frozen_model(models_dir=str(OUT))  # star (locked) model
    n = cfg["n_qubits"]
    rng = np.random.default_rng(SEED)
    idx = np.arange(len(Xte))
    sel = balanced_interleaved(idx[yte > 0], idx[yte < 0], min(EVAL_SIZE, len(Xte)), rng)
    X_eval, y_eval = Xte[sel], yte[sel]

    xparams = sorted(circ.parameters, key=lambda p: int(p.name[2:-1]))
    coeffs = observable_coeffs(obs, n)
    ev_ideal = np.zeros(len(X_eval))
    coupling = star_coupling_map(n)
    max_gap = 0.0
    for i, x in enumerate(X_eval):
        bound = circ.assign_parameters(dict(zip(xparams, x)))
        ev_ideal[i] = float(np.real(Statevector.from_instruction(bound).expectation_value(obs)))
        tqc = transpile(bound, basis_gates=IQM_BASIS_GATES, coupling_map=coupling, optimization_level=1)
        max_gap = max(max_gap, abs(ev_ideal[i] - float(np.real(
            Statevector.from_instruction(tqc).expectation_value(obs)))))
    preds = np.where(ev_ideal >= 0.0, 1.0, -1.0)
    acc_ideal = float(np.mean(preds == y_eval))

    np.savez(OUT / f"{star_tag}_reference.npz",
             eval_indices=sel, X_eval=X_eval, y_eval=y_eval, ev_ideal=ev_ideal,
             preds=preds, obs_coeffs=coeffs, threshold=0.0)
    (OUT / f"{star_tag}_reference.json").write_text(json.dumps({
        "tag": star_tag, "eval_subset_size": int(len(sel)),
        "noiseless_acc_on_subset": acc_ideal,
        "mean_abs_margin": float(np.mean(np.abs(ev_ideal))),
        "min_abs_margin": float(np.min(np.abs(ev_ideal))),
        "cx_cz_equivalence_max_gap": float(max_gap),
        "note": "HARD (offset 0.1) reference; balanced-interleaved so any prefix stays balanced.",
    }, indent=2))
    print(f"\nfrozen reference: {len(sel)} eval pts | noiseless acc {acc_ideal:.3f} | "
          f"mean margin {np.mean(np.abs(ev_ideal)):.3f}")
    print(f"saved -> {OUT}/  (point runners at it with --models-dir {OUT})")


if __name__ == "__main__":
    main()
