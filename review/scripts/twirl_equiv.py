"""Czy twirl_native zachowuje rozkład pomiaru (nie tylko <O>)? Różnica U_tw U^† diagonalna?"""
import json, sys, pathlib, numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from check_skeleton_twirl import parse_qasm
from qiskit.quantum_info import Operator, Statevector
recs=[json.loads(l) for l in open(sys.argv[1] if len(sys.argv)>1 else 'runs/odra_campaign/w01A/counts.jsonl')]
off={(r['rung'],r['eval_index'],r['role'],r['train_index']):r for r in recs if r['kind']=='cdr' and r['arm']=='off_copies' and r['repeat_index']==0}
smp=[r for r in recs if r['kind']=='cdr' and r['arm']=='twirl_native' and r['train_set']=='near_target'][::17]
maxdp=0; diag=0; phases=[]
for r in smp:
    b=parse_qasm(off[(r['rung'],r['eval_index'],r['role'],r['train_index'])]['qasm3']); t=parse_qasm(r['qasm3'])
    pb=Statevector(b).probabilities(); pt=Statevector(t).probabilities()
    maxdp=max(maxdp,np.abs(pb-pt).max())
    M=Operator(t).data@Operator(b).data.conj().T
    off_d=np.abs(M-np.diag(np.diag(M))).max()
    diag+= off_d<1e-9
print(f"próbka {len(smp)}: max|Δp| rozkładu = {maxdp:.2e}; U_tw U^† diagonalne: {diag}/{len(smp)}")
