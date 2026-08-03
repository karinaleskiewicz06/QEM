"""Freeze the noiseless ground-truth reference for the locked VQC (methodological anchor).

Before any noise / ZNE work we must fix, once and for all:
  * the exact noiseless expectation value <O>_ideal per evaluation point,
  * the evaluation subset (seeded, stratified) reused across ALL routing levels
    and mitigation methods,
  * the decision threshold (sign(<O>)), frozen from the noiseless model.

We also VERIFY that transpiling the CX-trained circuit to the IQM native basis
{r, cz} leaves <O> unchanged (logical equivalence), so the reference is valid
for what actually runs on ODRA.

Output: trained_models/<tag>_reference.npz  + _reference.json (summary).
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
from qiskit import transpile
from qiskit.quantum_info import Statevector
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from qml_benchmarks.data import generate_two_curves

from noisy_sim import (
    IQM_BASIS_GATES,
    load_frozen_model,
    observable_coeffs,
    readout_observable,
    star_coupling_map,
)

EVAL_SUBSET_SIZE = 30   # frozen, stratified subset used for every noise condition
EVAL_SEED = 42


def exact_expectation(bound_circuit, observable) -> float:
    """Exact <O> for a fully-bound circuit via statevector (no shots, no noise)."""
    sv = Statevector.from_instruction(bound_circuit)
    return float(np.real(sv.expectation_value(observable)))


def main() -> None:
    circ, observable, cfg = load_frozen_model()  # locked (highest test acc) model
    tag = f"two_curves_d{cfg['n_features']}_q{cfg['n_qubits']}_deg{cfg['degree']}_" \
          f"{cfg['entanglement']}_{cfg['readout']}_L{cfg['n_layers']}"
    n = cfg["n_qubits"]
    print(f"locked model: {tag}  (test_acc={cfg['test_acc']:.3f}, L={cfg['n_layers']})")

    # --- reproduce the EXACT dataset + split used in training -----------------
    np.random.seed(cfg["seed"])
    X, y = generate_two_curves(
        cfg["n_samples"], cfg["n_features"],
        degree=cfg["degree"], offset=cfg["offset"], noise=cfg["noise"],
    )
    y = y.astype(float)
    X = MinMaxScaler(tuple(cfg["feature_range"])).fit_transform(X)
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.3, random_state=cfg["seed"], stratify=y
    )

    # --- frozen stratified evaluation subset ----------------------------------
    m = min(EVAL_SUBSET_SIZE, len(Xte))
    idx_all = np.arange(len(Xte))
    # stratified pick: balanced across classes, deterministic
    rng = np.random.default_rng(EVAL_SEED)
    pos = idx_all[yte > 0]
    neg = idx_all[yte < 0]
    k = m // 2
    sel = np.concatenate([
        rng.choice(pos, size=min(k, len(pos)), replace=False),
        rng.choice(neg, size=min(m - k, len(neg)), replace=False),
    ])
    sel.sort()
    X_eval, y_eval = Xte[sel], yte[sel]
    print(f"frozen eval subset: {len(sel)} points "
          f"({int((y_eval > 0).sum())}+ / {int((y_eval < 0).sum())}-)")

    # --- feature parameters (bind per point) ----------------------------------
    xparams = sorted(circ.parameters, key=lambda p: int(p.name[2:-1]))
    coeffs = observable_coeffs(observable, n)

    # --- exact noiseless <O> + CX->{r,cz} equivalence check -------------------
    ev_ideal = np.zeros(len(X_eval))
    ev_transpiled = np.zeros(len(X_eval))
    coupling = star_coupling_map(n)
    for i, x in enumerate(X_eval):
        bound = circ.assign_parameters(dict(zip(xparams, x)))
        ev_ideal[i] = exact_expectation(bound, observable)
        tqc = transpile(bound, basis_gates=IQM_BASIS_GATES,
                        coupling_map=coupling, optimization_level=1)
        ev_transpiled[i] = exact_expectation(tqc, observable)

    max_gap = float(np.max(np.abs(ev_ideal - ev_transpiled)))
    equiv = max_gap < 1e-9
    print(f"CX -> {{r,cz}} equivalence: max |Δ<O>| = {max_gap:.2e} "
          f"-> {'OK (identical)' if equiv else 'MISMATCH!'}")

    # --- frozen decision rule + noiseless accuracy on the subset --------------
    threshold = 0.0
    preds = np.where(ev_ideal >= threshold, 1.0, -1.0)
    acc_eval = float(np.mean(preds == y_eval))
    print(f"noiseless accuracy on frozen subset: {acc_eval:.3f}  (threshold={threshold})")
    print(f"|<O>| margin: min={np.min(np.abs(ev_ideal)):.3f} "
          f"mean={np.mean(np.abs(ev_ideal)):.3f}  "
          f"(small margins flip first under noise)")

    # --- save reference -------------------------------------------------------
    out_dir = pathlib.Path("trained_models")
    npz_path = out_dir / f"{tag}_reference.npz"
    np.savez(
        npz_path,
        eval_indices=sel,
        X_eval=X_eval,
        y_eval=y_eval,
        ev_ideal=ev_ideal,
        ev_transpiled=ev_transpiled,
        preds=preds,
        obs_coeffs=coeffs,
        threshold=threshold,
    )
    summary = {
        "tag": tag,
        "n_qubits": n,
        "n_layers": cfg["n_layers"],
        "readout": cfg["readout"],
        "observable": cfg["observable"],
        "decision_rule": "sign(<O> - threshold), threshold=0.0 (FROZEN)",
        "eval_subset_size": len(sel),
        "eval_seed": EVAL_SEED,
        "eval_indices": sel.tolist(),
        "noiseless_acc_on_subset": acc_eval,
        "cx_cz_equivalence_max_gap": max_gap,
        "cx_cz_equivalent": equiv,
        "mean_abs_margin": float(np.mean(np.abs(ev_ideal))),
        "min_abs_margin": float(np.min(np.abs(ev_ideal))),
        "reference_npz": npz_path.name,
        "note": (
            "Ground-truth for ZNE. Primary metric = mean |<O>_mitigated - ev_ideal|. "
            "Reuse eval_indices + threshold for EVERY routing level / mitigation "
            "method. ev_ideal is exact (statevector, noiseless)."
        ),
    }
    (out_dir / f"{tag}_reference.json").write_text(json.dumps(summary, indent=2))
    print(f"\nsaved -> {npz_path}")
    print(f"        {out_dir / (tag + '_reference.json')}")


if __name__ == "__main__":
    main()
