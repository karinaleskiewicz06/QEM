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
        small = [k for k in keys if k[0] == "tgt" or k[2] < NTR]
        # OFF: small sets, M*S shots split into M blocks
        res = sim.run([merge_prx(base[k]) for k in small], shots=S * M, memory=True, seed_simulator=int(rng.integers(1 << 30))).result()
        off = {k: z_from_memory_blocks(res.get_memory(i), M).mean(1) for i, k in enumerate(small)}
        # ON_indep / ON_matched on small sets (M frames each)
        on = {}
        for mode in ["indep", "matched"]:
            circs, idx = [], []
            for k in small:
                if mode == "matched" and k[0] == "near": continue
                for m in range(M):
                    r_ = np.random.default_rng(rng.integers(1 << 30)) if mode == "indep" else np.random.default_rng(777_000 * rep + 1000 * k[1] + m)
                    circs.append(merge_prx(twirl_native(base[k], r_))); idx.append((k, m))
            res = sim.run(circs, shots=S, seed_simulator=int(rng.integers(1 << 30))).result()
            Z = {}
            for i, (k, m) in enumerate(idx): Z.setdefault(k, []).append(z_from_counts(res.get_counts(i)).mean())
            on[mode] = {k: np.array(v) for k, v in Z.items()}
        # ON_spread: NBIG training circuits x 1 independent frame, S shots; target reuses ON_indep target frames
        big = [k for k in keys if k[0] != "tgt"]
        circs = [merge_prx(twirl_native(base[k], np.random.default_rng(rng.integers(1 << 30)))) for k in big]
        res = sim.run(circs, shots=S, seed_simulator=int(rng.integers(1 << 30))).result()
        spread = {k: z_from_counts(res.get_counts(i)).mean() for i, k in enumerate(big)}
        def emit(arm, ts, e, xs, ys, vx, xt, idt, raw):
            for eiv in (False, True):
                a, b = fit(xs, ys, vx, eiv)
                rows.append(dict(theta=THETA, pattern=pat, cz=ncz, rep=rep, target=e, arm=arm, train=ts, eiv=eiv,
                                 err=abs(a * xt + b - idt), err_raw=raw, a=a, b=b))
        for e in range(E):
            idt = ideals[("tgt", e)]; raw = abs(off[("tgt", e)].mean() - idt)
            for ts in ["shared", "near"]:
                tk = [(ts, e, k) for k in range(NTR)]; ys = [ideals[k] for k in tk]
                emit("OFF", ts, e, [off[k].mean() for k in tk], ys, [np.var(off[k], ddof=1) / M for k in tk], off[("tgt", e)].mean(), idt, raw)
                emit("ON_indep", ts, e, [on["indep"][k].mean() for k in tk], ys, [np.var(on["indep"][k], ddof=1) / M for k in tk], on["indep"][("tgt", e)].mean(), idt, raw)
                if ts == "shared":
                    emit("ON_matched", ts, e, [on["matched"][k].mean() for k in tk], ys, [np.var(on["matched"][k], ddof=1) / M for k in tk], on["matched"][("tgt", e)].mean(), idt, raw)
                tkb = [(ts, e, k) for k in range(NBIG)]
                vt = np.var(on["indep"][("tgt", e)], ddof=1)          # between-frame variance proxy
                vx = [(1 - spread[k] ** 2) / (5 * S) + vt for k in tkb]  # crude shot (mean-Z) + frame variance
                emit("ON_spread", ts, e, [spread[k] for k in tkb], [ideals[k] for k in tkb], vx, on["indep"][("tgt", e)].mean(), idt, raw)
        print(f"{pat} rep{rep} cz={ncz} done {time.time()-t0:.0f}s", flush=True)
        pd.DataFrame(rows).to_csv(OUT, index=False)
print("DONE", OUT)
