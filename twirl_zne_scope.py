"""Circuit twirling + ZNE on the real VQC — sim scoping (free).

Twirling (randomized compiling) converts COHERENT errors into stochastic ones by
wrapping each 2q gate with random Paulis that cancel logically. This should:
 (1) reduce the bias a coherent (systematic) error puts on <O>, and
 (2) make ZNE reliable again (ZNE assumes well-behaved / Pauli noise).

We model a coherent error as a systematic over-rotation rz(coh) on both qubits
after each CX (a realistic miscalibration), plus a small stochastic depolarizing
baseline. Compare four arms:  {untwirled, twirled} x {raw, ZNE}.

Twirl of a gate G: pick random Pauli A on its qubits, apply A before G and
B = G A G^dag after G (Clifford-computed). Ideal is unchanged (B G A = G); the
error gets Pauli-twirled when averaged over random A.

Sanity: noiseless twirled <O> == ideal (twirling preserves the logical circuit).

    python twirl_zne_scope.py --coh 0.15 --p2q 0.005 --n-twirl 16
"""
from __future__ import annotations

import argparse
import numpy as np
import pathlib
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector, Pauli, Clifford

from ansatz import HardwareEfficientAnsatz
from noisy_sim import (
    DeviceCalibration, IQM_BASIS_GATES, make_noisy_simulator, load_frozen_model,
    readout_observable,
)
from zne_dryrun import SCALE_FACTORS, extrapolate, fold_global
from topology import star_coupling_map

PAULIS = ["I", "X", "Y", "Z"]


def _apply_pauli(qc, lab, qubits):
    for ch, q in zip(lab, qubits):
        if ch == "X": qc.x(q)
        elif ch == "Y": qc.y(q)
        elif ch == "Z": qc.z(q)


def build(circ_w, x, xparams, *, coh, twirl_rng):
    """Rebuild feature-bound VQC; add coherent rz(coh) after each CX; if twirl_rng
    given, wrap each CX with a random Pauli twirl (A before, B=CX A CX^dag after)."""
    src = circ_w.assign_parameters({p: v for p, v in zip(xparams, x)})
    n = src.num_qubits
    qc = QuantumCircuit(n, n)
    for ins in src.data:
        qi = [src.find_bit(q).index for q in ins.qubits]
        if ins.operation.name in ("cx", "cz") and len(qi) == 2:
            if twirl_rng is not None:
                A = Pauli("".join(twirl_rng.choice(PAULIS, size=2)))  # qubit0 = rightmost char
                cxc = QuantumCircuit(2); cxc.append(ins.operation, [0, 1])
                B = A.evolve(Clifford(cxc), frame="s")   # CX A CX^dag
                qc.append(A.to_instruction(), qi)        # A: its qubit0 -> qi[0]
                qc.append(ins.operation, qi)
                if coh:  # coherent error rides on the physical gate
                    qc.rz(coh, qi[0]); qc.rz(coh, qi[1])
                qc.append(B.to_instruction(), qi)
            else:
                qc.append(ins.operation, qi)
                if coh:
                    qc.rz(coh, qi[0]); qc.rz(coh, qi[1])
        else:
            qc.append(ins.operation, qi)
    qc.measure(range(n), range(n))
    return qc


def expval(counts, n, obs_diag):
    tot = sum(counts.values()); acc = 0.0
    for b, c in counts.items():
        s = b.replace(" ", "").zfill(n)
        z = [1 - 2 * int(s[n - 1 - q]) for q in range(n)]
        acc += obs_diag(z) * c
    return acc / tot


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--coh", type=float, default=0.15, help="coherent over-rotation per CX (rad)")
    ap.add_argument("--p2q", type=float, default=0.005, help="stochastic depolarizing baseline")
    ap.add_argument("--n-twirl", type=int, default=16)
    ap.add_argument("--n-x", type=int, default=6)
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    _, _, cfg = load_frozen_model(models_dir="trained_models_hard")
    n = cfg["n_qubits"]; md = pathlib.Path("trained_models_hard")
    tag = f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_star_{cfg['readout']}_L{cfg['n_layers']}"
    ref = np.load(md / f"{tag}_reference.npz"); X = ref["X_eval"][: args.n_x]
    weights = np.load(md / cfg["weights_file"])
    ans = HardwareEfficientAnsatz(n, cfg["n_layers"], num_features=cfg["n_features"],
                                  entanglement="star", entangling_gate=cfg.get("entangling_gate", "cx"))
    circ = ans.build(); xp = ans.feature_parameters(circ); wp = ans.weight_parameters(circ)
    circ_w = circ.assign_parameters(dict(zip(wp, weights)))
    obs_op = readout_observable(n, cfg["readout"])
    mean_z = lambda z: float(np.mean(z))  # readout=mean

    sim = make_noisy_simulator(DeviceCalibration(num_qubits=n, coupling_map=star_coupling_map(n, 0),
                                                 p_2q=args.p2q))
    rng = np.random.default_rng(args.seed)

    def run_arm(x, twirl, fold):
        vals = []
        reps = args.n_twirl if twirl else 1
        for _ in range(reps):
            tw = rng if twirl else None
            c = build(circ_w, x, xp, coh=args.coh, twirl_rng=tw)
            if fold > 1:
                c.remove_final_measurements(inplace=True)
                c = fold_global(c, fold); c.measure_all()
            c = transpile(c, basis_gates=IQM_BASIS_GATES, coupling_map=star_coupling_map(n, 0),
                          optimization_level=1, seed_transpiler=args.seed)
            vals.append(expval(sim.run(c, shots=args.shots).result().get_counts(), n, mean_z))
        return float(np.mean(vals))

    # sanity: noiseless twirled == ideal
    from qiskit.quantum_info import Statevector as SV
    sv_ideal = []
    for x in X:
        sv_ideal.append(float(np.real(SV.from_instruction(
            circ_w.assign_parameters(dict(zip(xp, x)))).expectation_value(obs_op))))
    # noiseless twirled check on x0
    c0 = build(circ_w, X[0], xp, coh=0.0, twirl_rng=rng); c0.remove_final_measurements(inplace=True)
    tw_ideal = float(np.real(SV.from_instruction(c0).expectation_value(obs_op)))
    print(f"SANITY noiseless twirled <O> vs ideal (x0): {tw_ideal:+.4f} vs {sv_ideal[0]:+.4f} "
          f"-> {'OK' if abs(tw_ideal - sv_ideal[0]) < 1e-6 else 'FAIL'}")

    print(f"\nCoherent over-rotation coh={args.coh} rad/CX | p2q={args.p2q} | {args.n_twirl} twirls | "
          f"{args.n_x} x-pts")
    err = {k: [] for k in ("raw_ut", "raw_tw", "zne_ut", "zne_tw")}
    for x, ideal in zip(X, sv_ideal):
        err["raw_ut"].append(abs(ideal - run_arm(x, False, 1)))
        err["raw_tw"].append(abs(ideal - run_arm(x, True, 1)))
        z_ut = [run_arm(x, False, s) for s in SCALE_FACTORS]
        z_tw = [run_arm(x, True, s) for s in SCALE_FACTORS]
        err["zne_ut"].append(abs(ideal - extrapolate(SCALE_FACTORS, z_ut, "richardson")))
        err["zne_tw"].append(abs(ideal - extrapolate(SCALE_FACTORS, z_tw, "richardson")))
    print(f"  {'':>12}{'untwirled':>12}{'twirled':>12}")
    print(f"  {'raw':>12}{np.mean(err['raw_ut']):>12.4f}{np.mean(err['raw_tw']):>12.4f}")
    print(f"  {'+ZNE':>12}{np.mean(err['zne_ut']):>12.4f}{np.mean(err['zne_tw']):>12.4f}")
    print("-" * 48)
    print("Twirling helps IFF twirled < untwirled (coherent error tamed) AND zne_tw is the best.")


if __name__ == "__main__":
    main()
