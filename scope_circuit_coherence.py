"""Circuit-level coherence probe (sim scoping) — the RIGHT predictor for twirl+CDR.

Gate-level URB missed the coherence that drives twirl+CDR (it lives in the ROUTED
circuit: SWAPs, idle, crosstalk). This probes it directly: a task-agnostic random
Clifford MIRROR (U U^dag, ideal |0..0>) at increasing routing cost, twirl ON vs OFF.
The twirl GAP in survival = coherent error the twirl removed = circuit-level coherent
fraction. On hardware this is cheap (Z-basis only) and is the quantity that predicts
whether twirl+CDR helps.

    python scope_circuit_coherence.py --coh 0.15
"""
from __future__ import annotations
import argparse, numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import random_clifford, Clifford
from run_garnet_twirl import twirl_native
from noisy_sim import IQM_BASIS_GATES
from topology import star_coupling_map

def survival(counts, n):
    tot=sum(counts.values()); return counts.get("0"*n, counts.get(" ".join("0"*n),0))/tot

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--n",type=int,default=5); ap.add_argument("--layers",type=int,nargs="+",default=[1,2,3,4])
    ap.add_argument("--coh",type=float,default=0.15); ap.add_argument("--n-twirl",type=int,default=8)
    ap.add_argument("--shots",type=int,default=4096); ap.add_argument("--seed",type=int,default=42)
    a=ap.parse_args(); n=a.n; rng=np.random.default_rng(a.seed)
    import scipy.linalg as la
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel, depolarizing_error, coherent_unitary_error
    nm=NoiseModel(); err=depolarizing_error(0.01,2)
    if a.coh: err=err.compose(coherent_unitary_error(la.expm(-1j*a.coh/2*np.diag([1.,-1,-1,1]))))
    nm.add_all_qubit_quantum_error(err,["cz"]); sim=AerSimulator(noise_model=nm)
    print(f"circuit-level coherence probe | n={n} coh={a.coh} | mirror survival, twirl OFF vs ON")
    print(f"  {'cz':>4} | {'surv OFF':>9} {'surv ON':>9} | {'gap(ON-OFF)':>11}")
    for L in a.layers:
        U=QuantumCircuit(n)
        for _ in range(L):
            for q in range(0,n-1,2): U.compose(random_clifford(2,seed=int(rng.integers(0,2**31))).to_circuit(),[q,q+1],inplace=True)
            for q in range(1,n-1,2): U.compose(random_clifford(2,seed=int(rng.integers(0,2**31))).to_circuit(),[q,q+1],inplace=True)
        mir=U.compose(Clifford(U).adjoint().to_circuit())  # U U^dag -> |0..0>
        base=transpile(mir,basis_gates=IQM_BASIS_GATES,coupling_map=star_coupling_map(n,0),optimization_level=1,seed_transpiler=42)
        cz=sum(1 for i in base.data if i.operation.name=="cz")
        b=base.copy(); b.measure_all()
        s_off=survival(sim.run(b,shots=a.shots).result().get_counts(),n)
        svals=[]
        for _ in range(a.n_twirl):
            tw=twirl_native(base,rng); tw.measure_all()
            svals.append(survival(sim.run(tw,shots=a.shots).result().get_counts(),n))
        s_on=float(np.mean(svals))
        print(f"  {cz:>4} | {s_off:>9.3f} {s_on:>9.3f} | {s_on-s_off:>+11.3f}")
    print("  gap>0 rosnący z CZ = coherent error akumuluje sie z routingiem (to napedza twirl+CDR).")

if __name__=="__main__": main()
