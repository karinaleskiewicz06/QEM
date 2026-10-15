"""Benchmark CDR / twirled-CDR variants on an ODRA-calibrated noisy simulator (shot-matched)."""
import sys, os, json, time, itertools
sys.path.insert(0, os.path.abspath("qem_m2"))
import numpy as np, pandas as pd
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Operator, Statevector, SparsePauliOp
from qiskit.circuit.library import RGate, RZGate, RZZGate
from qiskit.synthesis import OneQubitEulerDecomposer
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, thermal_relaxation_error, depolarizing_error, coherent_unitary_error, ReadoutError
from cdr import near_clifford_training_circuits, _rebuild, CLIFFORD_ANGLES, _snap_nearest
from ansatz import HardwareEfficientAnsatz
from zne_dryrun import IQM_BASIS_GATES
from topology import star_coupling_map
from run_garnet_twirl import twirl_native

THETA = float(sys.argv[1]); PHI = float(sys.argv[2]); OUT = sys.argv[3]
REPS = int(sys.argv[4]) if len(sys.argv) > 4 else 3
S, M, NTR, E = 8192, 6, 10, 8
# ODRA 23.07 calibration; index 0 = hub QB3, 1..4 = QB1, QB2, QB4, QB5
T1 = [24.40, 15.50, 15.83, 16.32, 19.92]; T2 = [9.35, 11.20, 8.59, 9.89, 10.25]
E10 = [0.0226, 0.0557, 0.0413, 0.0366, 0.0370]; E01 = [0.0057, 0.0034, 0.0047, 0.0061, 0.0061]
TPRX, TCZ, PDEP2 = 0.020, 0.060, 0.003   # us

def noise_model():
    nm = NoiseModel(basis_gates=["r", "cz"])
    for q in range(5):
        nm.add_quantum_error(thermal_relaxation_error(T1[q], T2[q], TPRX), "r", [q])
        nm.add_readout_error(ReadoutError([[1 - E01[q], E01[q]], [E10[q], 1 - E10[q]]]), [q])
    U = Operator(RZZGate(THETA)).compose(Operator(RZGate(PHI)).tensor(Operator(RZGate(PHI))))
    for q in range(1, 5):
        for a, b in [(0, q), (q, 0)]:
            th = thermal_relaxation_error(T1[b], T2[b], TCZ).tensor(thermal_relaxation_error(T1[a], T2[a], TCZ))
            err = depolarizing_error(PDEP2, 2).compose(th)
            if THETA or PHI:
                err = coherent_unitary_error(U).compose(err)
            nm.add_quantum_error(err, "cz", [a, b])
    return nm

dec = OneQubitEulerDecomposer("ZYZ")
def merge_prx(qc):
    n = qc.num_qubits; out = QuantumCircuit(n, qc.num_clbits)
    pend = [np.eye(2, dtype=complex) for _ in range(n)]
    def flush(q):
        th, ph, lam = dec.angles(pend[q])
        if abs(np.sin(th / 2)) > 1e-9: out.append(RGate(th, np.pi / 2 - lam), [q])
        pend[q] = Operator(RZGate(ph + lam)).data
    for ins in qc.data:
        qs = [qc.find_bit(x).index for x in ins.qubits]; nm_ = ins.operation.name
        if nm_ == "barrier": continue
        if nm_ == "measure":
            flush(qs[0]); out.append(ins.operation, qs, [qc.find_bit(c).index for c in ins.clbits]); continue
        if len(qs) == 1: pend[qs[0]] = Operator(ins.operation).data @ pend[qs[0]]
        elif nm_ == "cz":
            for q in qs: flush(q)
            out.append(ins.operation, qs)
        else: raise ValueError(nm_)
    return out

def tpile(c):
    c = c.copy(); c.measure_all()
    return transpile(c, basis_gates=IQM_BASIS_GATES, coupling_map=star_coupling_map(5),
                     initial_layout=[0, 1, 2, 3, 4], optimization_level=1, seed_transpiler=42)

def near_target_training(tgt, n, rng, sigma=np.pi / 4):
    out = [_rebuild(tgt, _snap_nearest)]
    def f(a):
        d = np.abs(((CLIFFORD_ANGLES - a % (2 * np.pi)) + np.pi) % (2 * np.pi) - np.pi)
        w = np.exp(-(d / sigma) ** 2); return float(rng.choice(CLIFFORD_ANGLES, p=w / w.sum()))
    for _ in range(n - 1): out.append(_rebuild(tgt, f))
    return out

ZOPS = [SparsePauliOp("I" * (4 - i) + "Z" + "I" * i) for i in range(5)]
def ideal_z(c): sv = Statevector.from_instruction(c); return np.array([np.real(sv.expectation_value(o)) for o in ZOPS])
def z_from_counts(cnt):
    tot = sum(cnt.values()); z = np.zeros(5)
    for b, v in cnt.items():
        s = b.replace(" ", "")
        for i in range(5): z[i] += (1 - 2 * int(s[-1 - i])) * v
    return z / tot
def z_from_memory_blocks(mem, M):
    arr = np.array([[1 - 2 * int(s.replace(" ", "")[-1 - i]) for i in range(5)] for s in mem], float)
    return np.array([b.mean(0) for b in np.array_split(arr, M)])   # (M,5)

def fit(xs, ys, vx, eiv):
    xs, ys = np.asarray(xs), np.asarray(ys)
    vxx = np.var(xs, ddof=1); cxy = np.cov(xs, ys, ddof=1)[0, 1]
    den = vxx - (np.mean(vx) if eiv else 0.0)
    if eiv and den < 0.25 * vxx: den = 0.25 * vxx          # guard: at most 4x de-attenuation
    a = cxy / den if den > 1e-12 else 0.0; b = ys.mean() - a * xs.mean(); return a, b


REP0 = int(sys.argv[5]) if len(sys.argv) > 5 else 0
sim = AerSimulator(method="density_matrix", noise_model=noise_model())
rows = []; t0 = time.time(); NBIG = NTR * M
models = "qem_m2/trained_models_hard"
def ols_eiv(xs, ys, vx, eiv): return fit(xs, ys, vx, eiv)
for pat in ["star", "linear", "circular", "all_to_all"]:
    w = np.load(f"{models}/two_curves_d8_q5_deg8_{pat}_mean_L3_weights.npy")
    ans = HardwareEfficientAnsatz(5, 3, num_features=8, entanglement=pat); c = ans.build()
    cw = c.assign_parameters(dict(zip(ans.weight_parameters(c), w))); xp = ans.feature_parameters(cw)
    for rep in range(REP0, REP0 + REPS):
        rng = np.random.default_rng(1000 * rep + 7)
        X = rng.uniform(-np.pi, np.pi, (E, 8))
        targets = [cw.assign_parameters(dict(zip(xp, x))) for x in X]
        sharedbig = near_clifford_training_circuits(targets[0], n_train=NBIG + 1, seed=42 + rep)[1:]
        logical, fam = {}, {}
        for e, tg in enumerate(targets):
            logical[("tgt", e)] = tg
            nb = near_target_training(tg, NBIG, np.random.default_rng(10_000 * rep + 100 * e + 1))
            for k in range(NBIG):
                logical[("shared", e, k)] = sharedbig[k] if k else _rebuild(tg, _snap_nearest)
                logical[("near", e, k)] = nb[k]
        keys = list(logical); ideals = {k: ideal_z(logical[k]).mean() for k in keys}
        base = {k: tpile(logical[k]) for k in keys}
        ncz = sum(1 for i in base[("tgt", 0)].data if i.operation.name == "cz")
        tg_keys=[("tgt", e) for e in range(E)]; big=[k for k in keys if k[0] != "tgt"]
        res = sim.run([merge_prx(base[k]) for k in tg_keys], shots=S * M, seed_simulator=int(rng.integers(1 << 30))).result()
        tz = {k: z_from_counts(res.get_counts(i)).mean() for i, k in enumerate(tg_keys)}
        res = sim.run([merge_prx(base[k]) for k in big], shots=S, seed_simulator=int(rng.integers(1 << 30))).result()
        sp = {k: z_from_counts(res.get_counts(i)).mean() for i, k in enumerate(big)}
        for e in range(E):
            idt = ideals[("tgt", e)]
            for ts in ["shared", "near"]:
                tkb = [(ts, e, k) for k in range(NBIG)]
                for eiv in (False, True):
                    a_, b_ = fit([sp[k] for k in tkb], [ideals[k] for k in tkb], [(1 - sp[k] ** 2) / (5 * S) for k in tkb], eiv)
                    rows.append(dict(theta=THETA, pattern=pat, cz=ncz, rep=rep, target=e, arm="OFF_spread", train=ts, eiv=eiv,
                                     err=abs(a_ * tz[("tgt", e)] + b_ - idt), err_raw=abs(tz[("tgt", e)] - idt), a=a_, b=b_))
        print(f"{pat} rep{rep} cz={ncz} done {time.time()-t0:.0f}s", flush=True)
        pd.DataFrame(rows).to_csv(OUT, index=False)
print("DONE", OUT)
