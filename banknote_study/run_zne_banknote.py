"""ZNE accuracy comparison for the 3 banknote ansatze (simulator / odra / star).

Runs the KN-Axion trained VQCs through the ODRA-calibrated NOISY SIMULATOR and
measures how accuracy (and the raw expectation-value error) changes across the
mitigation ladder:

    ideal (noiseless statevector)  ->  raw (noisy, no mitigation)
    ->  +DD+REM  ->  +DD+REM+ZNE (Richardson/linear/exp over folds [1,3,5])

The three ansatze form a hardware-cost ladder on the star (transpiled CZ):
    star (native+star) < odra (native ring) < simulator (CRX/CRY ring).

The headline question: does QEM recover the noiseless accuracy of the
topology-naive "simulator" ansatz on ODRA-like noise, and does the recovery
degrade as routing cost grows?

No hardware / token needed -- everything runs on the Aer noise model, so this is
safe to run while a hardware job is in flight. Reuses the exact same pipeline
primitives (`noisy_sim`, `zne_dryrun`) as the two_curves study for consistency.

Usage (run from the QEM project root):
    python banknote_study/run_zne_banknote.py --n-samples 50
    python banknote_study/run_zne_banknote.py --ansatze star odra --depth 4 --fold 1
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys

import numpy as np

# --- make the QEM pipeline and the upstream qbanknote package importable ---
QEM_ROOT = pathlib.Path(__file__).resolve().parents[1]
UPSTREAM = QEM_ROOT / "banknote_study" / "upstream"
sys.path.insert(0, str(QEM_ROOT))
sys.path.insert(0, str(UPSTREAM / "src"))

import torch  # noqa: E402
from qiskit import QuantumCircuit  # noqa: E402
from qiskit.circuit import ParameterVector  # noqa: E402
from qiskit.quantum_info import SparsePauliOp  # noqa: E402

from qbanknote.ansatzes import odra_ansatz, simulator_ansatz, star_ansatz  # noqa: E402
from noisy_sim import (  # noqa: E402
    load_iqm_calibration,
    make_noisy_simulator,
    execute_expectation,
)
from zne_dryrun import SCALE_FACTORS, exact_ev, extrapolate, fold_global, native_transpile  # noqa: E402

ANSATZ_FNS = {"simulator": simulator_ansatz, "odra": odra_ansatz, "star": star_ansatz}
MODEL_DIRNAME = {"simulator": "Simulator", "odra": "Odra", "star": "Star"}
# Readout qubit is ansatz-specific: the star model concentrates signal at its hub
# (QB2) and was trained/measured there; odra/simulator use qubit 0. Verified by
# reproducing the noiseless accuracy (~0.84/0.83/0.83) against the KN-Axion paper.
READOUT_QUBIT = {"simulator": 0, "odra": 0, "star": 2}


def build_full_circuit(ansatz_name: str, n_qubits: int, depth: int) -> tuple[QuantumCircuit, list, list]:
    """Ry angle-encoding feature map + ansatz. Return (circuit, x_params, w_params)."""
    ansatz = ANSATZ_FNS[ansatz_name](n_qubits, depth)
    fm = QuantumCircuit(n_qubits)
    x = ParameterVector("x", n_qubits)
    for i in range(n_qubits):
        fm.ry(x[i], i)
    full = fm.compose(ansatz)
    # weight order MUST match qbanknote's HybridModel: list(ansatz.parameters)
    return full, list(x), list(ansatz.parameters)


def load_weights(ansatz_name: str, depth: int, fold: int, epoch: int) -> np.ndarray:
    """Extract the trainable weight vector from a KN-Axion .pth checkpoint."""
    model = MODEL_DIRNAME[ansatz_name]
    path = (UPSTREAM / "cross_validation" / "Models" / "Weights" / f"depth {depth}"
            / model / f"fold_{fold}" / f"{model}_fold_{fold}_depth_{depth}_epoch_{epoch}_weights.pth")
    if not path.exists():
        raise FileNotFoundError(path)
    sd = torch.load(path, map_location="cpu", weights_only=False)
    for key in ("quantum_layer._weights", "quantum_layer.weight", "_weights"):
        if key in sd:
            return np.asarray(sd[key].detach().cpu().numpy(), dtype=float)
    raise KeyError(f"no weight tensor in {path} (keys: {list(sd.keys())})")


def zobs(n: int, q: int) -> SparsePauliOp:
    """Single-qubit Z observable on wire ``q`` (Qiskit little-endian labels)."""
    return SparsePauliOp.from_list([("I" * (n - 1 - q) + "Z" + "I" * q, 1.0)])


def load_eval_subset(fold: int, n_samples: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Test set of a fold. ``n_samples <= 0`` (or >= fold size) returns the FULL fold.

    The full fold keeps the natural class imbalance (fold 1: 153/-1 vs 122/+1, i.e. a
    0.556 majority-class floor), which is the KN-Axion paper's evaluation set and the
    only setting in which macro-F1 can expose majority-class collapse. A balanced
    subset instead forces a 0.5 floor and makes F1 collapse to accuracy.
    """
    csv_path = UPSTREAM / "cross_validation" / "Data" / f"fold_{fold}" / "test_data.csv"
    rows = list(csv.DictReader(open(csv_path)))
    X = np.array([[float(r[str(i)]) for i in range(5)] for r in rows])
    y = np.array([float(r["target"]) for r in rows])  # labels in {-1, +1}
    if n_samples <= 0 or n_samples >= len(y):
        return X, y
    rng = np.random.default_rng(seed)
    idx = []
    per_class = n_samples // 2
    for cls in (-1.0, 1.0):
        pool = np.where(y == cls)[0]
        rng.shuffle(pool)
        idx.extend(pool[:per_class].tolist())
    rng.shuffle(idx)
    idx = np.array(idx[:n_samples])
    return X[idx], y[idx]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ansatze", nargs="+", default=["star", "odra", "simulator"],
                    choices=list(ANSATZ_FNS))
    ap.add_argument("--depth", type=int, default=4, choices=(2, 4, 6))
    ap.add_argument("--fold", type=int, default=1, choices=(1, 2, 3, 4, 5))
    ap.add_argument("--epoch", type=int, default=30, choices=(20, 30))
    ap.add_argument("--n-samples", type=int, default=50,
                    help="balanced test-set subset size (accuracy resolution ~1/n)")
    ap.add_argument("--shots", type=int, default=4096)
    ap.add_argument("--calibration", default="calibrations/odra.json")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="banknote_study/banknote_zne_results.csv")
    args = ap.parse_args()

    n = 5
    cal = load_iqm_calibration(str(QEM_ROOT / args.calibration))
    X_eval, y_eval = load_eval_subset(args.fold, args.n_samples, args.seed)
    sim_raw = make_noisy_simulator(cal, dd=False)   # DD off (for the raw rung)
    sim_dd = make_noisy_simulator(cal, dd=True)     # DD on  (for +DD+REM and ZNE)

    print("=" * 78)
    print(f"Banknote ZNE accuracy | depth={args.depth} fold={args.fold} epoch={args.epoch} "
          f"| n={len(X_eval)} shots={args.shots}")
    print(f"calibration: {args.calibration}  (DD modelled as T2*->T2echo in sim)")
    print("=" * 78)

    rows = []
    for name in args.ansatze:
        full, xparams, wparams = build_full_circuit(name, n, args.depth)
        weights = load_weights(name, args.depth, args.fold, args.epoch)
        if len(weights) != len(wparams):
            raise ValueError(f"{name}: {len(weights)} weights != {len(wparams)} params")
        circ_w = full.assign_parameters(dict(zip(wparams, weights)))
        mq = READOUT_QUBIT[name]
        obs_logical = zobs(n, mq)  # for the exact (untranspiled) reference

        # transpiled CZ (routing cost) at this configuration
        probe = native_transpile(circ_w.assign_parameters({p: 0.0 for p in xparams}), n)
        n2q = sum(1 for i in probe.data if i.operation.name == "cz")

        ideal_ev, raw_ev, ddrem_ev, zne_ev = [], [], [], []
        for x in X_eval:
            bound = circ_w.assign_parameters(dict(zip(xparams, x)))
            ideal_ev.append(exact_ev(bound, obs_logical))
            native = native_transpile(bound, n)
            # transpile with a coupling map permutes qubits: the noisy path reads
            # PHYSICAL wires, so the readout observable must sit on the wire that
            # holds logical `mq` after routing (critical for the star hub=2 ansatz;
            # a no-op for odra/simulator where logical 0 -> physical 0).
            fil = native.layout.final_index_layout()
            obs_phys = zobs(n, fil[mq])
            # raw: DD off, no REM, scale 1
            raw_ev.append(execute_expectation(
                fold_global(native, 1), obs_phys, sim_raw, shots=args.shots,
                cal=cal, apply_idle_schedule=True, pre_transpiled=True, rem=False))
            # DD+REM at each fold scale, then extrapolate for ZNE
            vals = [execute_expectation(
                fold_global(native, s), obs_phys, sim_dd, shots=args.shots,
                cal=cal, apply_idle_schedule=True, pre_transpiled=True, rem=True)
                for s in SCALE_FACTORS]
            ddrem_ev.append(vals[0])
            zne_ev.append(extrapolate(SCALE_FACTORS, vals, "richardson"))

        ideal_ev = np.array(ideal_ev); raw_ev = np.array(raw_ev)
        ddrem_ev = np.array(ddrem_ev); zne_ev = np.array(zne_ev)

        def acc(ev):
            return float(np.mean(np.sign(ev) == y_eval))

        def mae(ev):
            return float(np.mean(np.abs(ev - ideal_ev)))

        row = {
            "ansatz": name, "readout_qubit": mq, "transpiled_cz": n2q,
            "depth": args.depth,
            "fold": args.fold, "n_samples": len(X_eval), "shots": args.shots,
            "acc_ideal": round(acc(ideal_ev), 4),
            "acc_raw": round(acc(raw_ev), 4),
            "acc_ddrem": round(acc(ddrem_ev), 4),
            "acc_zne": round(acc(zne_ev), 4),
            "everr_raw": round(mae(raw_ev), 4),
            "everr_ddrem": round(mae(ddrem_ev), 4),
            "everr_zne": round(mae(zne_ev), 4),
        }
        rows.append(row)
        print(f"  {name:>10} | 2q={n2q:>3} | acc ideal={row['acc_ideal']:.2f} "
              f"raw={row['acc_raw']:.2f} +DD+REM={row['acc_ddrem']:.2f} "
              f"+ZNE={row['acc_zne']:.2f} | <O>err raw={row['everr_raw']:.3f} "
              f"-> ZNE={row['everr_zne']:.3f}")

    out_path = QEM_ROOT / args.out
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
