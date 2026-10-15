import numpy as np, json, glob, sys
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator, Statevector, SparsePauliOp
from qiskit.synthesis import OneQubitEulerDecomposer
from ansatz import HardwareEfficientAnsatz
from zne_dryrun import native_transpile
from run_garnet_twirl import twirl_native
from qiskit.circuit.library import RGate, RZGate
dec = OneQubitEulerDecomposer("ZYZ")

def merge_prx(qc):
    """Merge every run of 1q gates between CZs into <=1 PRX; RZ commuted through CZ and dropped before Z-measurement."""
    n = qc.num_qubits; out = QuantumCircuit(n)
    pend = [np.eye(2, dtype=complex) for _ in range(n)]   # accumulated 1q unitary (time-ordered product)
    def flush(q):
        U = pend[q]
        th, ph, lam = dec.angles(U)            # U = Rz(ph) Ry(th) Rz(lam)
        if abs(np.sin(th/2)) > 1e-9:
            out.append(RGate(th, np.pi/2 - lam), [q])
        pend[q] = Operator(RZGate(ph + lam)).data   # carry Z rotation through the CZ
    for ins in qc.data:
        qs = [qc.find_bit(x).index for x in ins.qubits]
        if ins.operation.name in ("barrier",): continue
        if len(qs) == 1:
            pend[qs[0]] = Operator(ins.operation).data @ pend[qs[0]]
        elif ins.operation.name == "cz":
            for q in qs: flush(q)
            out.append(ins.operation, qs)
        else: raise ValueError(ins.operation.name)
    for q in range(n):  # final: emit R part, drop trailing RZ (diagonal, irrelevant for Z observables)
        flush(q)
    return out

def zexp(c):
    sv = Statevector.from_instruction(c); n=c.num_qubits
    return np.array([np.real(sv.expectation_value(SparsePauliOp("I"*(n-1-i)+"Z"+"I"*i))) for i in range(n)])

def cnt(c):
    ops = c.count_ops(); return ops.get("cz",0), ops.get("r",0), c.depth()

rng = np.random.default_rng(1); rows=[]
for pat in ["star","linear","circular","all_to_all"]:
    ans = HardwareEfficientAnsatz(5, 3, num_features=8, entanglement=pat)
    c = ans.build(); xp=ans.feature_parameters(c); wp=ans.weight_parameters(c)
    b = c.assign_parameters({**dict(zip(wp, rng.uniform(-np.pi,np.pi,len(wp)))), **dict(zip(xp, rng.uniform(-1,1,len(xp))))})
    off = native_transpile(b, 5)
    offm = merge_prx(off)
    tw_old = [twirl_native(off, rng) for _ in range(6)]
    tw_new = [merge_prx(t) for t in tw_old]
    z0 = zexp(off)
    dev_old = max(np.abs(zexp(t)-z0).max() for t in tw_old)
    dev_new = max(np.abs(zexp(t)-z0).max() for t in tw_new)
    rows.append(dict(pattern=pat, cz=cnt(off)[0], r_off=cnt(off)[1], depth_off=cnt(off)[2],
        r_off_merged=cnt(offm)[1], depth_off_merged=cnt(offm)[2],
        r_tw_old=np.mean([cnt(t)[1] for t in tw_old]), depth_tw_old=np.mean([cnt(t)[2] for t in tw_old]),
        r_tw_merged=np.mean([cnt(t)[1] for t in tw_new]), depth_tw_merged=np.mean([cnt(t)[2] for t in tw_new]),
        maxdev_ideal_old=dev_old, maxdev_ideal_merged=dev_new, z_off_merged_dev=np.abs(zexp(offm)-z0).max()))
import pandas as pd
d=pd.DataFrame(rows); print(d.round(3).to_string()); d.round(4).to_csv("../native_twirl_merge_check.csv", index=False)
