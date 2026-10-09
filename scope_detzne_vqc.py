"""FULL det+ZNE on the real VQC — simulator closure (free).

Four arms on the true trained classifier across the routing ladder (4 patterns):
  raw       : no check, scale 1
  check     : Pauli-check + post-selection, scale 1        (Variant-1 detection alone)
  zne       : Richardson over folded entangler, no check   (ZNE alone)
  check+zne : both                                          (the composition)

Folding is ENTANGLER-LOCAL (fold the Clifford entangler = the routing-noise source):
E -> E (E^dag E)^k. The Pauli check L=Z^n commutes with E and E^dag, so it stays
valid under folding. Post-selection = ancilla X-measurement == 0.

Sanity: pure statevector (check, no noise) MUST give P(anc=0)=1.0 per pattern.

    python scope_detzne_vqc.py --p2q 0.01 --n-x 6
"""
from __future__ import annotations

import argparse
import csv
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from noisy_sim import (
    DeviceCalibration, IQM_BASIS_GATES, make_noisy_simulator, load_frozen_model,
    readout_observable,
)
from zne_dryrun import SCALE_FACTORS, extrapolate
from shots_to_target import zne_effective_shots
from topology import star_coupling_map
import pathlib

LADDER = ["star", "linear", "circular", "all_to_all"]


def build_variant(circ_w: QuantumCircuit, x, xparams, n: int, *, check: bool, scale: int):
    """Rebuild the feature-bound VQC; fold each entangler block to `scale`; optionally
    wrap each block with a Pauli check (L=Z^n via CZ) on one ancilla. Returns measured circuit."""
    src = circ_w.assign_parameters({p: v for p, v in zip(xparams, x)})
    anc = n
    w = n + 1 if check else n
    qc = QuantumCircuit(w, w)
    if check:
        qc.h(anc)
    data = list(src.data)
    i = 0
    while i < len(data):
        qidx = [src.find_bit(q).index for q in data[i].qubits]
        if len(qidx) == 2:  # entangler block
            block = []
            while i < len(data):
                q2 = [src.find_bit(q).index for q in data[i].qubits]
                if len(q2) != 2:
                    break
                block.append((data[i].operation, q2)); i += 1
            if check:
                for q in range(n):
                    qc.cz(anc, q)
            # fold: E (E^dag E)^k, E^dag = reversed self-inverse 2q gates
            def emit(seq):
                for op, q2 in seq:
                    qc.append(op, [qc.qubits[k] for k in q2])
            emit(block)
            for _ in range((scale - 1) // 2):
                emit(list(reversed(block))); emit(block)
            if check:
                for q in range(n):
                    qc.cz(anc, q)
        else:
            qc.append(data[i].operation, [qc.qubits[k] for k in qidx]); i += 1
    if check:
        qc.h(anc)
    qc.measure(range(w), range(w))
    return qc


def mean_z(counts, n, *, postselect):
    tot = sum(counts.values()); num = den = 0.0
    for b, c in counts.items():
        s = b.replace(" ", "").zfill(n + 1 if postselect else n)
        if postselect and int(s[0]) != 0:   # ancilla = MSB; 0 = pass
            continue
        off = 1 if postselect else 0
        mz = np.mean([1.0 - 2.0 * int(s[len(s) - 1 - q]) for q in range(n)])
        num += mz * c; den += c
    acc = den / tot
    return (num / den if den else 0.0), acc


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--p2q", type=float, default=0.01)
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--n-x", type=int, default=6)
    ap.add_argument("--models-dir", default="trained_models_hard")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="scope_detzne_vqc_results.csv")
    args = ap.parse_args()

    _, obs, cfg = load_frozen_model(models_dir=args.models_dir)
    n = cfg["n_qubits"]
    md = pathlib.Path(args.models_dir)
    tag0 = f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_star_{cfg['readout']}_L{cfg['n_layers']}"
    ref = np.load(md / f"{tag0}_reference.npz")
    X = ref["X_eval"][: args.n_x]
    star_w = np.load(md / cfg["weights_file"])

    cal_check = make_noisy_simulator(
        DeviceCalibration(num_qubits=n + 1, coupling_map=star_coupling_map(n + 1, 0), p_2q=args.p2q))
    cal_plain = make_noisy_simulator(
        DeviceCalibration(num_qubits=n, coupling_map=star_coupling_map(n, 0), p_2q=args.p2q))

    print(f"FULL det+ZNE on real VQC | p2q={args.p2q} | {args.n_x} x-pts | scales {list(SCALE_FACTORS)}")
    print(f"{'pattern':>11} {'cz':>3} | {'raw':>6} {'check':>6} {'zne':>6} {'chk+zne':>7} | "
          f"{'acc':>5} | {'sane?':>5}")
    rows = []
    for pat in LADDER:
        wp = md / f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_{pat}_{cfg['readout']}_L{cfg['n_layers']}_weights.npy"
        weights = np.load(wp) if wp.exists() else star_w
        ans = HardwareEfficientAnsatz(n, cfg["n_layers"], num_features=cfg["n_features"],
                                      entanglement=pat, entangling_gate=cfg.get("entangling_gate", "cx"))
        circ = ans.build()
        xparams = ans.feature_parameters(circ); wparams = ans.weight_parameters(circ)
        circ_w = circ.assign_parameters(dict(zip(wparams, weights)))
        obs_op = readout_observable(n, cfg["readout"])

        # sanity: statevector, check on, no measure, no noise -> P(anc=0)=1
        v = build_variant(circ_w, X[0], xparams, n, check=True, scale=1)
        v.remove_final_measurements(inplace=True)
        sane = abs(1.0 - float(Statevector.from_instruction(v).probabilities([n])[0])) < 1e-6

        e_raw, e_chk, e_zne, e_cz, accs = [], [], [], [], []
        n2q = None
        for x in X:
            ideal = float(np.real(Statevector.from_instruction(
                circ_w.assign_parameters(dict(zip(xparams, x)))).expectation_value(obs_op)))
            # raw + zne (no check)
            zvals = []
            for s in SCALE_FACTORS:
                cq = transpile(build_variant(circ_w, x, xparams, n, check=False, scale=s),
                               basis_gates=IQM_BASIS_GATES, coupling_map=star_coupling_map(n, 0),
                               optimization_level=1, seed_transpiler=args.seed)
                if n2q is None and s == 1:
                    n2q = sum(1 for g in cq.data if g.operation.name == "cz")
                mz, _ = mean_z(cal_plain.run(cq, shots=args.shots).result().get_counts(), n, postselect=False)
                zvals.append(mz)
            e_raw.append(abs(ideal - zvals[0]))
            e_zne.append(abs(ideal - extrapolate(SCALE_FACTORS, zvals, "richardson")))
            # check + check+zne
            zvals_ps, acc_s = [], []
            for s in SCALE_FACTORS:
                cq = transpile(build_variant(circ_w, x, xparams, n, check=True, scale=s),
                               basis_gates=IQM_BASIS_GATES, coupling_map=star_coupling_map(n + 1, 0),
                               optimization_level=1, seed_transpiler=args.seed)
                mz, acc = mean_z(cal_check.run(cq, shots=args.shots).result().get_counts(), n, postselect=True)
                zvals_ps.append(mz); acc_s.append(acc)
            e_chk.append(abs(ideal - zvals_ps[0]))
            e_cz.append(abs(ideal - extrapolate(SCALE_FACTORS, zvals_ps, "richardson")))
            accs.append(float(np.mean(acc_s)))
        row = dict(pattern=pat, cz=n2q,
                   err_raw=round(np.mean(e_raw), 4), err_check=round(np.mean(e_chk), 4),
                   err_zne=round(np.mean(e_zne), 4), err_checkzne=round(np.mean(e_cz), 4),
                   acceptance=round(np.mean(accs), 4), sane=sane)
        rows.append(row)
        print(f"{pat:>11} {n2q:>3} | {row['err_raw']:>6.3f} {row['err_check']:>6.3f} "
              f"{row['err_zne']:>6.3f} {row['err_checkzne']:>7.3f} | {row['acceptance']:>5.2f} | "
              f"{'OK' if sane else 'FAIL':>5}")

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print("-" * 70)
    print(f"wrote {args.out}")
    best = min(rows, key=lambda r: r["err_checkzne"])
    print("check+zne is the intended winner where err_checkzne < err_zne AND acceptance not too low.")


if __name__ == "__main__":
    main()
