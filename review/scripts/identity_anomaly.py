"""Zad. 5: anomalia foldingu 'identity' (<O> dryfuje do +1 na sprzęcie).

Odbudowuje obwody ZNE nocy A dokładnie ścieżką kampanii (frozen -> compile_native ->
fold_native), sprawdza zgodność z qasm3 z counts.jsonl, a potem symuluje je w Aer
(sim/device_model, kalibracja w01A_start) w kilku ablacjach:

  full        -- pełny model (T1, T2, idle ALAP, depol dopasowany do RB, readout)
  noT1        -- T1 -> nieskończoność (T2 bez zmian), reszta jak full
  noidle      -- bez relaksacji w czasie bezczynności (tylko szum bramek)
  noT1_noidle -- oba wyłączone
  depol_only  -- T1,T2 -> nieskończoność: tylko depolaryzacja + readout

Wyłącznie symulacja offline.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import sys
import warnings

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import os  # noqa: E402

os.chdir(REPO)
warnings.filterwarnings("ignore")

from qiskit.quantum_info import Statevector  # noqa: E402

from campaign.eval_points import load as load_points  # noqa: E402
from campaign.odra_window import N_QUBITS, frozen  # noqa: E402
from noisy_sim import perqubit_z_from_counts, readout_observable  # noqa: E402
from qem.compile import compile_native  # noqa: E402
from qem.folding import fold_native  # noqa: E402
from qem.identity_insertion import scheduled_duration  # noqa: E402
from sim.device_model import build_noise_model, load_calibration  # noqa: E402
from campaign.odra_window import _seed  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from check_skeleton_twirl import parse_qasm  # noqa: E402

CAL = "calibrations/odra_raw_w01A_start.json"
SHOTS = 32768


def gate_list(qc):
    return [(i.operation.name, tuple(qc.find_bit(q).index for q in i.qubits),
             tuple(round(float(p), 8) for p in i.operation.params))
            for i in qc.data if i.operation.name in ("r", "cz")]


def main():
    recs = {}
    for l in open("runs/odra_campaign/w01A/counts.jsonl"):
        r = json.loads(l)
        if r["kind"] == "zne":
            recs[r["circuit_id"]] = r
    pts = {p["eval_index"]: p for p in load_points()}
    eixs = sorted({r["eval_index"] for r in recs.values()})
    obs = readout_observable(N_QUBITS, "mean")
    cal = load_calibration(CAL)
    print("T1 [us]:", np.round(cal.t1 * 1e6, 1), "T2* [us]:", np.round(cal.t2 * 1e6, 1),
          "T2e [us]:", np.round(cal.t2_echo * 1e6, 1), "t_cz", cal.t_cz, "t_prx", cal.t_prx)
    print("readout e01:", np.round(cal.e01, 4), "e10:", np.round(cal.e10, 4))
    big = 1e3
    models = {
        "full": build_noise_model(cal),
        "noT1": build_noise_model(dataclasses.replace(cal, t1=cal.t1 * 0 + big)),
        "noidle": build_noise_model(cal, with_idle=False),
        "noT1_noidle": build_noise_model(dataclasses.replace(cal, t1=cal.t1 * 0 + big),
                                         with_idle=False),
        "depol_only": build_noise_model(dataclasses.replace(
            cal, t1=cal.t1 * 0 + big, t2=cal.t2 * 0 + big, t2_echo=cal.t2_echo * 0 + big)),
        "dd": build_noise_model(cal, dd=True),
    }
    out = {}
    for rung in ("star", "circular"):
        cw, xp = frozen(rung)
        circs, keys, mism = [], [], 0
        hw = {}
        for eix in eixs:
            logical = cw.assign_parameters(dict(zip(xp, pts[eix]["x"])))
            nat = compile_native(logical).circuit
            for v in ("genuine", "identity", "garbage"):
                for s in (1, 3, 5):
                    if s == 1 and v != "genuine":
                        continue
                    cid = f"{rung}/zne/{v}/p{eix:02d}/lam{s}"
                    c = fold_native(nat, s, v, measure=True,
                                    seed=_seed(42, "w01A", cid))
                    rec = recs[cid]
                    if gate_list(c) != gate_list(parse_qasm(rec["qasm3"])):
                        mism += 1
                    circs.append(c)
                    keys.append((v, s, eix))
                    hw[(v, s, eix)] = rec["expval"]
        print(f"\n{rung}: odbudowane obwody vs qasm3 z rekordów: niezgodnych {mism}/{len(circs)}")
        # czasy (ASAP, jak w kampanii) per wariant
        for v, s in (("genuine", 3), ("identity", 3), ("garbage", 3),
                     ("genuine", 5), ("identity", 5)):
            c = circs[keys.index((v, s, eixs[0]))]
            ops = c.count_ops()
            print(f"  {v:8s} lam{s}: n_cz={ops.get('cz', 0)} n_r={ops.get('r', 0)} "
                  f"dur_ASAP={scheduled_duration(c) * 1e6:.2f} us")
        res = {"hardware": hw}
        for name, dev in models.items():
            counts = dev.run(circs, SHOTS, seed=1234)
            res[name] = {k: float(np.mean(perqubit_z_from_counts(cn, N_QUBITS)))
                         for k, cn in zip(keys, counts)}
        out[rung] = res
        print(f"  mean <O> over 8 points (λ=1 | genuine λ3, λ5 | identity λ3, λ5 | garbage λ3, λ5);"
              f" ideal mean = {np.mean([recs[f'{rung}/zne/genuine/p{e:02d}/lam1']['ideal'] for e in eixs]):.3f}")
        for name, d in res.items():
            m = lambda v, s: np.mean([d[(v, s, e)] for e in eixs])  # noqa: E731
            print(f"  {name:12s} {m('genuine', 1):+.3f} | {m('genuine', 3):+.3f} {m('genuine', 5):+.3f}"
                  f" | {m('identity', 3):+.3f} {m('identity', 5):+.3f}"
                  f" | {m('garbage', 3):+.3f} {m('garbage', 5):+.3f}")
        # per-qubit: czy dryf identity jest na liściach (bezczynnych) czy na hubie?
        dev = models["full"]
        sel = [i for i, k in enumerate(keys) if k[1] == 5 and k[0] in ("identity", "genuine")]
        cnt = dev.run([circs[i] for i in sel], SHOTS, seed=99)
        zq = {}
        for i, cn in zip(sel, cnt):
            zq.setdefault(keys[i][0], []).append(perqubit_z_from_counts(cn, N_QUBITS))
        hwq = {}
        for v in ("identity", "genuine"):
            hwq[v] = np.mean([perqubit_z_from_counts(recs[f"{rung}/zne/{v}/p{e:02d}/lam5"]["counts"], N_QUBITS)
                              for e in eixs], axis=0)
        ideal_q = np.mean([Statevector(circs[keys.index(("genuine", 1, e))].remove_final_measurements(inplace=False))
                           .probabilities_dict() and _zq(circs[keys.index(("genuine", 1, e))]) for e in eixs], axis=0)
        print("  per-kubit <Z_q> λ5 (hub=q0): ideal", np.round(ideal_q, 3))
        for v in ("genuine", "identity"):
            print(f"    {v:8s} sim full {np.round(np.mean(zq[v], axis=0), 3)}  hw {np.round(hwq[v], 3)}")
    json.dump({r: {m: {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in d.items()} for m, d in res.items()}
               for r, res in out.items()},
              open(pathlib.Path(__file__).resolve().parent / "tmp" / "identity_anomaly.json", "w"),
              indent=1)


def _zq(c):
    sv = Statevector(c.remove_final_measurements(inplace=False))
    p = sv.probabilities()
    idx = np.arange(len(p))
    return np.array([p @ (1 - 2 * ((idx >> q) & 1)) for q in range(N_QUBITS)])


if __name__ == "__main__":
    main()
