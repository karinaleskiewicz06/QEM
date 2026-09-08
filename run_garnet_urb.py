"""Two-qubit unitarity RB (URB) + standard RB — measure noise COHERENCE.

Coherence test needs BOTH:
  u  = unitarity  (URB, purity decay  p'(m)=A u^(m-1)+B)     -- how much purity survives
  p  = RB decay   (standard RB, survival S(m)=A' p^m + B')   -- fidelity per Clifford
Verdict: purely stochastic noise has u = p^2; coherent noise has u > p^2. The gap
(u - p^2) quantifies the coherent contribution. High coherent fraction => twirling
has a lot to remove (predicts twirl+CDR/ZNE benefit, hypothesis H3).

Estimator (Wallman arXiv:1503.07865; forest-benchmarking): shifted purity
p' = (sum over the 15 traceless 2q Paulis of <sigma>^2)/(d-1), d=4, via 9 local bases.

    python run_garnet_urb.py --sim                 # validate (pure depol vs pure coherent)
    python run_garnet_urb.py --sim --coh 0.3       # inject coherent -> u > p^2
    python run_garnet_urb.py --submit --pair 3 4   # real Garnet edge (valid coupling pair!)
"""
from __future__ import annotations

import argparse
import itertools
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import random_clifford, Clifford
from scipy.optimize import curve_fit

from topology import device_coupling_map

BASES = ["X", "Y", "Z"]


def _basis_change(qc, b, q):
    if b == "X":
        qc.h(q)
    elif b == "Y":
        qc.sdg(q); qc.h(q)


def _seq(cliffs):
    qc = QuantumCircuit(2)
    for cl in cliffs:
        qc.compose(cl.to_circuit(), inplace=True)
    return qc


def _expects(counts):
    tot = sum(counts.values()); zz = z0 = z1 = 0.0
    for b, c in counts.items():
        s = b.replace(" ", "").zfill(2); b1, b0 = int(s[0]), int(s[1])
        s0, s1 = 1 - 2 * b0, 1 - 2 * b1
        zz += s0 * s1 * c; z0 += s0 * c; z1 += s1 * c
    return zz / tot, z0 / tot, z1 / tot


def _survival(counts):
    tot = sum(counts.values())
    return counts.get("00", counts.get("0 0", 0)) / tot


def _shifted_purity(exp9):
    keys = list(itertools.product(BASES, repeat=2))
    two = [e[0] for e in exp9]
    q0 = {b: np.mean([exp9[i][1] for i, k in enumerate(keys) if k[0] == b]) for b in BASES}
    q1 = {b: np.mean([exp9[i][2] for i, k in enumerate(keys) if k[1] == b]) for b in BASES}
    return (sum(v * v for v in two) + sum(v * v for v in q0.values())
            + sum(v * v for v in q1.values())) / 3.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="garnet")
    ap.add_argument("--pair", type=int, nargs=2, default=[3, 4])
    ap.add_argument("--lengths", type=int, nargs="+", default=[1, 2, 4, 8, 16])
    ap.add_argument("--k-seqs", type=int, default=10)
    ap.add_argument("--shots", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--coh", type=float, default=0.0, help="[sim] inject pure coherent rz on cz")
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--sim", action="store_true")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    if args.submit:
        from iqm_resonance import get_backend, transpile_for_backend, run_circuits
        backend = get_backend(args.device)
        layout = list(args.pair)
        def tp(c): return transpile_for_backend(c, backend, initial_layout=layout)
        def ex(circs): return run_circuits(backend, circs, args.shots)
    else:
        sim = None
        if args.sim:
            import scipy.linalg as la
            from qiskit_aer import AerSimulator
            from qiskit_aer.noise import NoiseModel, depolarizing_error, coherent_unitary_error
            nm = NoiseModel()
            err = (coherent_unitary_error(la.expm(-1j * args.coh / 2 * np.diag([1., -1., -1., 1.])))
                   if args.coh else depolarizing_error(0.03, 2))
            nm.add_all_qubit_quantum_error(err, ["cz"])
            sim = AerSimulator(noise_model=nm)
        def tp(c): return transpile(c, basis_gates=["r", "cz"], coupling_map=[[0, 1], [1, 0]],
                                    optimization_level=1, seed_transpiler=args.seed)
        def ex(circs): return [sim.run(c, shots=args.shots).result().get_counts() for c in circs]

    if not (args.submit or args.sim):
        nc = len(args.lengths) * args.k_seqs * (9 + 1)  # URB 9 bases + RB 1
        print(f"[DRY-RUN] URB+RB pair {args.pair} | {nc} circuits x {args.shots} shots "
              f"~{nc*args.shots*0.0002 + np.ceil(nc/100)*0.33:.0f} cr")
        return

    print(f"URB+RB pair {args.pair} | coh={args.coh} | lengths {args.lengths} | K {args.k_seqs}")
    print(f"  {'m':>3} | {'purity p(m)':>12} | {'survival S(m)':>13}")
    ms, purs, survs = [], [], []
    for m in args.lengths:
        pu, sv = [], []
        for _ in range(args.k_seqs):
            cliffs = [random_clifford(2, seed=int(rng.integers(0, 2**31))) for _ in range(m)]
            seqc = _seq(cliffs)
            # URB: 9 basis-measured circuits (no inverse)
            ub = []
            for b0, b1 in itertools.product(BASES, repeat=2):
                c = seqc.copy(); _basis_change(c, b0, 0); _basis_change(c, b1, 1); c.measure_all()
                ub.append(tp(c))
            # RB: sequence + inverse Clifford, Z-measure survival
            rc = seqc.copy(); rc.compose(Clifford(seqc).adjoint().to_circuit(), inplace=True); rc.measure_all()
            counts = ex(ub + [tp(rc)])
            pu.append(_shifted_purity([_expects(ct) for ct in counts[:9]]))
            sv.append(_survival(counts[9]))
        ms.append(m); purs.append(float(np.mean(pu))); survs.append(float(np.mean(sv)))
        print(f"  {m:>3} | {purs[-1]:>12.4f} | {survs[-1]:>13.4f}")

    ms = np.array(ms, float)
    try:
        (Au, u, Bu), _ = curve_fit(lambda m, A, x, B: A * x ** (m - 1) + B, ms, purs,
                                   p0=[purs[0], 0.9, 0], bounds=([0, 0, -.1], [2, 1, .5]), maxfev=10000)
        (Ap, p, Bp), _ = curve_fit(lambda m, A, x, B: A * x ** m + B, ms, survs,
                                   p0=[survs[0], 0.95, 0.25], bounds=([0, 0, 0], [2, 1, 1]), maxfev=10000)
    except Exception as e:
        print(f"fit failed: {e}"); return
    print("-" * 52)
    print(f"  unitarity u = {u:.4f}   |   RB decay p = {p:.4f}   ->  p^2 = {p*p:.4f}")
    gap = u - p * p
    print(f"  u - p^2 = {gap:+.4f}  ->  {'COHERENT error present' if gap > 0.01 else 'noise ~ stochastic (incoherent)'}")
    if gap > 0.01:
        print(f"  coherent fraction (rough): ~{gap/(1-p*p):.2f} -> twirling should help; predicts twirl benefit (H3).")
    else:
        print("  little coherent error at the GATE level -> twirl+CDR benefit likely from CIRCUIT-level"
              " coherence (routing/idle/crosstalk), not the isolated CZ.")


if __name__ == "__main__":
    main()
