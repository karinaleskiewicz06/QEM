"""Zad. 3-4: szkielety CZ, odtworzenie ramek twirlu, wartości idealne z qasm3.

Tylko symulacja offline (Statevector); nic nie wysyła na sprzęt.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import re
import sys

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator, SparsePauliOp, Statevector

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

N = 5
OBS = SparsePauliOp.from_sparse_list([("Z", [q], 1 / N) for q in range(N)], N)


def parse_qasm(text: str) -> QuantumCircuit:
    """Minimalny parser: r(theta, phi) $q; cz $a, $b; barrier; pomiary pomijane."""
    qc = QuantumCircuit(N)
    env = {"pi": math.pi}
    for line in text.splitlines():
        line = line.strip()
        line = re.sub(r"q\[(\d+)\]", r"$\1", line)
        m = re.match(r"r\((.+),\s*(.+)\)\s+\$(\d+);", line)
        if m:
            qc.r(eval(m.group(1), {}, env), eval(m.group(2), {}, env), int(m.group(3)))
            continue
        m = re.match(r"cz\s+\$(\d+),\s*\$(\d+);", line)
        if m:
            qc.cz(int(m.group(1)), int(m.group(2)))
            continue
        if line.startswith("delay"):
            raise RuntimeError("delay")
    return qc


def skel(qc):
    return tuple(tuple(sorted(qc.find_bit(q).index for q in i.qubits))
                 for i in qc.data if i.operation.name == "cz")


def main(run_dir="runs/odra_campaign/w01A"):
    run_dir = REPO / run_dir
    recs = [json.loads(l) for l in (run_dir / "counts.jsonl").open() if l.strip()]
    # --- szkielety: pole rekordu vs przeliczenie z cz_skeleton
    tgt_skel = {}
    for r in recs:
        if r["kind"] == "cdr" and r["role"] == "target":
            tgt_skel.setdefault((r["rung"], r["arm"], r["train_set"], r["eval_index"]), set()).add(
                tuple(map(tuple, r["cz_skeleton"])))
    print("różne szkielety targetu w obrębie bloku:",
          collections.Counter(len(v) for v in tgt_skel.values()))
    stats = collections.Counter()
    for r in recs:
        if r["kind"] != "cdr":
            continue
        key = (r["rung"], r["arm"], r["train_set"], r["eval_index"])
        me = tuple(map(tuple, r["cz_skeleton"])) in tgt_skel[key]
        stats[(r["rung"], r["arm"], r["train_set"], r["role"], r["skeleton_matches_target"], me)] += 1
    for k, v in sorted(stats.items(), key=str):
        print("  ", k, v)
    # szkielet z qasm3 vs pole cz_skeleton (próbka co 25. rekord)
    bad = 0
    for r in recs[::25]:
        if skel(parse_qasm(r["qasm3"])) != tuple(map(tuple, r["cz_skeleton"])):
            bad += 1
    print("qasm3 vs cz_skeleton niezgodne (próbka):", bad, "/", len(recs[::25]))

    # --- ideal targetu z qasm3 (Statevector) vs pole ideal
    d_ideal = 0.0
    n_t = 0
    for r in recs:
        if r["kind"] == "cdr" and r["role"] == "target" and r["repeat_index"] == 0:
            sv = Statevector(parse_qasm(r["qasm3"]))
            d_ideal = max(d_ideal, abs(float(np.real(sv.expectation_value(OBS))) - r["ideal"]))
            n_t += 1
    print(f"ideal targetu z qasm3 (n={n_t}, wszystkie ramienia): max |Δ| = {d_ideal:.2e}")
    # ideal treningu (próbka) z qasm3
    d_tr = 0.0
    tr = [r for r in recs if r["kind"] == "cdr" and r["role"] == "train"][::37]
    for r in tr:
        sv = Statevector(parse_qasm(r["qasm3"]))
        d_tr = max(d_tr, abs(float(np.real(sv.expectation_value(OBS))) - r["ideal"]))
    print(f"ideal treningu z qasm3 (próbka n={len(tr)}): max |Δ| = {d_tr:.2e}")
    # ZNE: wszystkie warianty/skale mają ideal == genuine (operator) -> sprawdź na qasm3
    d_z = collections.defaultdict(float)
    for r in recs:
        if r["kind"] == "zne":
            sv = Statevector(parse_qasm(r["qasm3"]))
            d_z[(r["variant"], r["scale"])] = max(
                d_z[(r["variant"], r["scale"])],
                abs(float(np.real(sv.expectation_value(OBS))) - r["ideal"]))
    print("ZNE: max |<O>_ideal(qasm) - ideal| per (wariant, skala):",
          {k: f"{v:.2e}" for k, v in sorted(d_z.items())})

    # --- odtworzenie ramek natywnego twirlu: rebuild_from_frame(untwirled, frame) == qasm3
    from qem.twirl import rebuild_from_frame
    # nie-twirlowany odpowiednik: rekord off_copies tego samego (rung, punkt, train_index)
    # dla near_target (ten sam zbiór treningowy, deterministyczny seed) albo target.
    off = {}
    for r in recs:
        if r["kind"] == "cdr" and r["arm"] == "off_copies" and r["repeat_index"] == 0:
            off[(r["rung"], r["eval_index"], r["role"], r["train_index"])] = r
    n_ok = n_bad = n_unit = 0
    sample = [r for r in recs if r["kind"] == "cdr" and r["arm"] == "twirl_native"
              and r["train_set"] == "near_target"][::11]
    for r in sample:
        base = off.get((r["rung"], r["eval_index"], r["role"], r["train_index"]))
        if base is None:
            continue
        nat = parse_qasm(base["qasm3"])
        rebuilt = rebuild_from_frame(nat, r["frame"])
        executed = parse_qasm(r["qasm3"])
        same = [(i.operation.name, tuple(rebuilt.find_bit(q).index for q in i.qubits),
                 tuple(round(float(p), 9) for p in i.operation.params)) for i in rebuilt.data]
        ex = [(i.operation.name, tuple(executed.find_bit(q).index for q in i.qubits),
               tuple(round(float(p), 9) for p in i.operation.params)) for i in executed.data]
        if same == ex:
            n_ok += 1
        else:
            n_bad += 1
            if Operator(rebuilt).equiv(Operator(executed)):
                n_unit += 1
    print(f"twirl_native rebuild_from_frame: identyczne bramka-w-bramkę {n_ok}, "
          f"różne {n_bad} (z czego równoważne unitarnie {n_unit}); próbka {len(sample)}")
    # unitarna równoważność twirlowany vs nietwirlowany (próbka)
    n_eq = 0
    smp = sample[::6]
    for r in smp:
        base = off[(r["rung"], r["eval_index"], r["role"], r["train_index"])]
        if Operator(parse_qasm(base["qasm3"])).equiv(Operator(parse_qasm(r["qasm3"]))):
            n_eq += 1
    print(f"twirl_native ≡ off_copies (Operator.equiv, z dokładnością do fazy): {n_eq}/{len(smp)}")
    # twirl_logical: <O>_ideal twirlowanego obwodu == ideal
    tl = [r for r in recs if r["kind"] == "cdr" and r["arm"] == "twirl_logical"][::13]
    d = max(abs(float(np.real(Statevector(parse_qasm(r["qasm3"])).expectation_value(OBS))) - r["ideal"])
            for r in tl)
    print(f"twirl_logical: max |ideal(qasm) - ideal| (próbka {len(tl)}) = {d:.2e}")


if __name__ == "__main__":
    main(*sys.argv[1:])
