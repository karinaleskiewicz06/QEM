"""Twirling x {raw, ZNE, CDR} under a coherent error — sim scoping (free).

Answers: does circuit twirling help CDR the way it helps ZNE? Hypothesis: CDR's
linear fit (ideal ~ a*noisy + b) also assumes well-behaved noise; a coherent error
can break the linearity (low r2), and twirling (coherent->stochastic) should
restore it. We twirl the CDR TRAINING circuits too (so training noise matches the
twirled target). Reports err AND the CDR fit r2 (the tell).

    python twirl_cdr_scope.py --coh 0.15 --p2q 0.005 --n-twirl 8 --n-train 12 --n-x 3
"""
from __future__ import annotations

import argparse
import numpy as np
import pathlib
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector, Pauli, Clifford

from ansatz import HardwareEfficientAnsatz
from noisy_sim import DeviceCalibration, IQM_BASIS_GATES, make_noisy_simulator, load_frozen_model, readout_observable
from cdr import near_clifford_training_circuits, clifford_ideal_expval, fit_cdr, apply_cdr
from zne_dryrun import SCALE_FACTORS, extrapolate, fold_global
from topology import star_coupling_map

PAULIS = ["I", "X", "Y", "Z"]


def modify(bound, coh, tw):
    n = bound.num_qubits
    qc = QuantumCircuit(n, n)
    for ins in bound.data:
        qi = [bound.find_bit(q).index for q in ins.qubits]
        if ins.operation.name in ("cx", "cz") and len(qi) == 2:
            if tw is not None:
                A = Pauli("".join(tw.choice(PAULIS, size=2)))
                cxc = QuantumCircuit(2); cxc.append(ins.operation, [0, 1])
                B = A.evolve(Clifford(cxc), frame="s")
                qc.append(A.to_instruction(), qi); qc.append(ins.operation, qi)
                if coh: qc.rz(coh, qi[0]); qc.rz(coh, qi[1])
                qc.append(B.to_instruction(), qi)
            else:
                qc.append(ins.operation, qi)
                if coh: qc.rz(coh, qi[0]); qc.rz(coh, qi[1])
        else:
            qc.append(ins.operation, qi)
    qc.measure(range(n), range(n))
    return qc


def expval(counts, n):
    tot = sum(counts.values()); acc = 0.0
    for b, c in counts.items():
        s = b.replace(" ", "").zfill(n)
        acc += np.mean([1 - 2 * int(s[n - 1 - q]) for q in range(n)]) * c
    return acc / tot


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--coh", type=float, default=0.15)
    ap.add_argument("--p2q", type=float, default=0.005)
    ap.add_argument("--n-twirl", type=int, default=8)
    ap.add_argument("--n-train", type=int, default=12)
    ap.add_argument("--n-x", type=int, default=3)
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    _, _, cfg = load_frozen_model(models_dir="trained_models_hard")
    n = cfg["n_qubits"]; md = pathlib.Path("trained_models_hard")
    tag = f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_star_{cfg['readout']}_L{cfg['n_layers']}"
    X = np.load(md / f"{tag}_reference.npz")["X_eval"][: args.n_x]
    weights = np.load(md / cfg["weights_file"])
    ans = HardwareEfficientAnsatz(n, cfg["n_layers"], num_features=cfg["n_features"],
                                  entanglement="star", entangling_gate=cfg.get("entangling_gate", "cx"))
    circ = ans.build(); xp = ans.feature_parameters(circ); wp = ans.weight_parameters(circ)
    circ_w = circ.assign_parameters(dict(zip(wp, weights)))
    obs_op = readout_observable(n, cfg["readout"])
    sim = make_noisy_simulator(DeviceCalibration(num_qubits=n, coupling_map=star_coupling_map(n, 0), p_2q=args.p2q))
    rng = np.random.default_rng(args.seed)

    def ev(bound, twirl, fold=1):
        reps = args.n_twirl if twirl else 1
        vals = []
        for _ in range(reps):
            c = modify(bound, args.coh, rng if twirl else None)
            if fold > 1:
                c.remove_final_measurements(inplace=True); c = fold_global(c, fold); c.measure_all()
            c = transpile(c, basis_gates=IQM_BASIS_GATES, coupling_map=star_coupling_map(n, 0),
                          optimization_level=1, seed_transpiler=args.seed)
            vals.append(expval(sim.run(c, shots=args.shots).result().get_counts(), n))
        return float(np.mean(vals))

    err = {k: [] for k in ("raw", "zne_ut", "zne_tw", "cdr_ut", "cdr_tw")}
    r2s = {"ut": [], "tw": []}
    for x in X:
        target = circ_w.assign_parameters(dict(zip(xp, x)))
        ideal = float(np.real(Statevector.from_instruction(target).expectation_value(obs_op)))
        # raw + ZNE
        err["raw"].append(abs(ideal - ev(target, False, 1)))
        err["zne_ut"].append(abs(ideal - extrapolate(SCALE_FACTORS, [ev(target, False, s) for s in SCALE_FACTORS], "richardson")))
        err["zne_tw"].append(abs(ideal - extrapolate(SCALE_FACTORS, [ev(target, True, s) for s in SCALE_FACTORS], "richardson")))
        # CDR (untwirled + twirled) — training circuits share structure/routing
        train = near_clifford_training_circuits(target, n_train=args.n_train, seed=args.seed)
        ideal_v = [clifford_ideal_expval(t, obs_op) for t in train]
        for tag2, twirl in (("ut", False), ("tw", True)):
            noisy_v = [ev(t, twirl, 1) for t in train]
            a, b, r2 = fit_cdr(noisy_v, ideal_v)
            corrected = apply_cdr(ev(target, twirl, 1), a, b)
            err[f"cdr_{tag2}"].append(abs(ideal - corrected)); r2s[tag2].append(r2)

    print(f"coh={args.coh} p2q={args.p2q} | {args.n_twirl} twirls | n_train {args.n_train} | {args.n_x} x-pts")
    print(f"  {'method':>10}{'untwirled':>12}{'twirled':>12}")
    print(f"  {'raw':>10}{np.mean(err['raw']):>12.4f}{'—':>12}")
    print(f"  {'+ZNE':>10}{np.mean(err['zne_ut']):>12.4f}{np.mean(err['zne_tw']):>12.4f}")
    print(f"  {'+CDR':>10}{np.mean(err['cdr_ut']):>12.4f}{np.mean(err['cdr_tw']):>12.4f}")
    print(f"  {'CDR r2':>10}{np.mean(r2s['ut']):>12.3f}{np.mean(r2s['tw']):>12.3f}")
    print("-" * 46)
    print("Twirl helps CDR IFF cdr_tw < cdr_ut AND/OR r2 improves (linear fit restored).")


if __name__ == "__main__":
    main()
