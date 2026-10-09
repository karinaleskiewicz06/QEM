"""Variant 1 (Pauli Check Sandwiching) on the REAL VQC — sim scoping, free.

Wrap each Clifford entangling block of the trained VQC with a Pauli check on one
ancilla: L = Z^⊗n (realised as CZ(anc, q_i)) before and after the block. Because
the star entangler is Clifford and L commutes with it, the ancilla returns to |+>
with no error; an X-type error inside the entangler anticommutes with L and flips
the ancilla -> X-measurement = 1 -> that shot is flagged and discarded.

Runs the true non-Clifford VQC (rotations physical) — no encoding, no magic states.

Sanity gate (noiseless): acceptance ~1.0 and <O> ~ ideal, else the check is wrong.

    python pcs_vqc_scope.py --p2q 0.01
"""
from __future__ import annotations

import argparse
import numpy as np
from qiskit import QuantumCircuit, transpile

from noisy_sim import (
    DeviceCalibration, IQM_BASIS_GATES, make_noisy_simulator, load_frozen_model,
)
from topology import star_coupling_map


def build_checked(bound: QuantumCircuit, x: np.ndarray) -> QuantumCircuit:
    """Rebuild the feature-bound VQC with a Pauli check (ancilla) around each
    consecutive block of 2q entangling gates. Returns a circuit with n_data+1
    qubits; ancilla is the last qubit; measures data (Z) + ancilla (X)."""
    n = bound.num_qubits
    anc = n
    xparams = sorted(bound.parameters, key=lambda p: p.name)
    circ = bound.assign_parameters({p: v for p, v in zip(xparams, x)})

    qc = QuantumCircuit(n + 1, n + 1)
    qc.h(anc)  # ancilla |+>

    data = list(circ.data)
    i = 0
    while i < len(data):
        ins = data[i]
        qidx = [circ.find_bit(q).index for q in ins.qubits]
        if len(qidx) == 2:  # start of an entangling block
            # left check: CZ(anc, each data qubit)
            for q in range(n):
                qc.cz(anc, q)
            # emit the whole consecutive 2q block
            while i < len(data):
                ins2 = data[i]
                q2 = [circ.find_bit(q).index for q in ins2.qubits]
                if len(q2) != 2:
                    break
                qc.append(ins2.operation, [qc.qubits[k] for k in q2])
                i += 1
            # right check: CZ(anc, each data qubit)
            for q in range(n):
                qc.cz(anc, q)
        else:
            qc.append(ins.operation, [qc.qubits[k] for k in qidx])
            i += 1

    qc.h(anc)  # measure ancilla in X
    qc.measure(range(n + 1), range(n + 1))
    return qc


def mean_z_and_acc(counts: dict, n: int) -> tuple[float, float, float]:
    """Return (meanZ_raw, meanZ_postselected, acceptance). Bit order: LSB=q0,
    ancilla = qubit n. Post-select ancilla bit == 0 (X-outcome |+> = pass)."""
    tot = sum(counts.values())
    num_raw = num_ps = den_ps = 0.0
    for b, c in counts.items():
        s = b.replace(" ", "").zfill(n + 1)
        anc = int(s[0])  # MSB = qubit n = ancilla
        mz = np.mean([1.0 - 2.0 * int(s[n - q]) for q in range(n)])  # s[n-q] = qubit q
        num_raw += mz * c
        if anc == 0:
            num_ps += mz * c; den_ps += c
    return num_raw / tot, (num_ps / den_ps if den_ps else 0.0), (den_ps / tot)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--p2q", type=float, default=0.01)
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--n-x", type=int, default=6, help="feature points to average |O| over")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    bound, obs, cfg = load_frozen_model("trained_models_hard")
    n = cfg["n_qubits"]
    ref = np.load(f"trained_models_hard/{cfg['tag']}_reference.npz") if "tag" in cfg else None
    # feature points: from frozen eval set if available, else random in [-pi,pi]
    try:
        X = np.load(f"trained_models_hard/{cfg.get('tag','')}_reference.npz")["X_eval"]
    except Exception:
        X = np.random.default_rng(args.seed).uniform(-np.pi, np.pi, size=(args.n_x, 8))
    X = X[: args.n_x]

    def run(p2q):
        cal = DeviceCalibration(num_qubits=n + 1, coupling_map=star_coupling_map(n + 1, 0), p_2q=p2q)
        sim = make_noisy_simulator(cal)
        raws, pss, accs, ideals = [], [], [], []
        for x in X:
            checked = build_checked(bound, x)
            native = transpile(checked, basis_gates=IQM_BASIS_GATES, coupling_map=cal.coupling_map,
                               optimization_level=1, seed_transpiler=args.seed)
            counts = sim.run(native, shots=args.shots).result().get_counts()
            mz_raw, mz_ps, acc = mean_z_and_acc(counts, n)
            raws.append(mz_raw); pss.append(mz_ps); accs.append(acc)
        return np.array(raws), np.array(pss), np.array(accs)

    # ideal <O> per x (noiseless statevector, no ancilla) for the error metric
    from qiskit.quantum_info import Statevector
    ideals = []
    xparams = sorted(bound.parameters, key=lambda p: p.name)
    for x in X:
        c = bound.assign_parameters({p: v for p, v in zip(xparams, x)})
        ideals.append(float(np.real(Statevector.from_instruction(c).expectation_value(obs))))
    ideals = np.array(ideals)

    print("SANITY (p2q=0): expect acceptance~1.0 and meanZ_ps ~ ideal")
    r0, p0, a0 = run(0.0)
    print(f"  acceptance mean {a0.mean():.3f} | |meanZ_ps - ideal| mean {np.mean(np.abs(p0-ideals)):.3f}")

    print(f"\nNOISY (p2q={args.p2q}) | mean over {len(X)} feature points")
    r, p, a = run(args.p2q)
    err_raw = np.mean(np.abs(r - ideals))
    err_check = np.mean(np.abs(p - ideals))
    print(f"  ⟨O⟩-error  raw {err_raw:.4f}  ->  check+PS {err_check:.4f}   "
          f"({'better' if err_check < err_raw else 'WORSE'})")
    print(f"  acceptance mean {a.mean():.3f} (min {a.min():.3f})")
    print("-" * 60)
    print("If sanity OK and check+PS < raw -> Variant 1 works on the real VQC.")
    print("Next: add ZNE folding around the checked entangler -> the honest det+zne.")


if __name__ == "__main__":
    main()
