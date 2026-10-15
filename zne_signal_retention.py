"""Diagnostyka artefaktu ZNE: retencja sygnału na skalach składania (Köster & Mauerer, arXiv:2607.09360).

Ich wynik: gdy <O> kolapsuje do podłogi obserwabla (0 dla mean-Z) przy wzmocnionym szumie,
ekstrapolacja Richardsona degeneruje się do przeskalowania jednego pomiaru i raportuje POZORNĄ
poprawę. Diagnostyka: udział sygnału, który przeżywa na największej skali,
    R = |<O>(lambda_max)| / |<O>(lambda=1)| .
R bliskie zeru => ekstrapolacja nie ma z czego ekstrapolować => liczby ZNE są niewiarygodne.

Ten skrypt liczy R w SYMULACJI (za darmo) dla punktów drabiny routingu, tak by ustalić, czy reżim
sprzętowy kampanii w ogóle wpada w strefę zagrożenia. Raportuje też <O> na każdej skali i wynik
ekstrapolacji, żeby pokazać, czy Richardson wychodzi poza zakres fizyczny [-1, 1].

    python zne_signal_retention.py --points optimal:star optimal:all_to_all adverse:all_to_all

P3: R zostaje kolumną, ale przestaje być regułą decyzyjną. Gdy sygnał znika już przy
lambda=1, R jest ilorazem dwóch wielkości na podłodze i niczego nie rozstrzyga. Obok R
raportowane są retencja znormalizowana |<O>(1)|/|O_ideal| oraz SNR = |<O>(lambda_max)|/SE.
Progi dla nich ustala symulacja przed kampanią (sim/calibrate_wneg_null.py), nie ten
skrypt. Dawny werdykt (R<0.15 / R<0.30): --legacy-verdict.
"""
from __future__ import annotations

import argparse
import csv
import pathlib

import numpy as np
from qiskit import transpile
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from noisy_sim import (
    load_frozen_model, readout_observable, observable_coeffs, perqubit_z_from_counts,
    make_noisy_simulator, DeviceCalibration, IQM_BASIS_GATES,
)
from zne_dryrun import SCALE_FACTORS, extrapolate, fold_global
from qem.zne import expval_se, retention_normalized
from topology import device_coupling_map, hardware_placement


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="garnet")
    ap.add_argument("--points", nargs="+",
                    default=["optimal:star", "optimal:all_to_all", "adverse:all_to_all"])
    ap.add_argument("--models-dir", default="trained_models_hard")
    ap.add_argument("--eval-points", type=int, default=4)
    ap.add_argument("--shots", type=int, default=1024)
    ap.add_argument("--p2q", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=42)
    # nowe wyniki do results_sim/: zne_signal_retention.csv w katalogu glownym to archiwum
    ap.add_argument("--out", default="results_sim/zne_signal_retention.csv")
    ap.add_argument("--legacy-verdict", action="store_true",
                    help="dopisz dawny werdykt z progow R<0.15 / R<0.30")
    args = ap.parse_args()

    _, observable, cfg = load_frozen_model(models_dir=args.models_dir)
    n = cfg["n_qubits"]
    md = pathlib.Path(args.models_dir)
    tag = f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_star_{cfg['readout']}_L{cfg['n_layers']}"
    X = np.load(md / f"{tag}_reference.npz")["X_eval"][: args.eval_points]
    coeffs = observable_coeffs(observable, n)
    obs_op = readout_observable(n, cfg["readout"])

    cmap = device_coupling_map(args.device)
    ndev = max(max(e) for e in cmap) + 1
    sim = make_noisy_simulator(DeviceCalibration(num_qubits=ndev, coupling_map=cmap, p_2q=args.p2q))

    rows = []
    print(f"{args.device} | p_2q={args.p2q} | shots={args.shots} | skale {SCALE_FACTORS}\n")
    for spec in args.points:
        placement, pattern = spec.split(":")
        layout = hardware_placement(args.device, placement)
        ptag = f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_{pattern}_{cfg['readout']}_L{cfg['n_layers']}"
        wp_path = md / f"{ptag}_weights.npy"
        weights = np.load(wp_path) if wp_path.exists() else np.load(md / cfg["weights_file"])
        ans = HardwareEfficientAnsatz(n, cfg["n_layers"], num_features=cfg["n_features"],
                                      entanglement=pattern, entangling_gate=cfg.get("entangling_gate", "cx"))
        c = ans.build()
        xp, wpar = ans.feature_parameters(c), ans.weight_parameters(c)
        circ_w = c.assign_parameters(dict(zip(wpar, weights)))

        per_scale = {s: [] for s in SCALE_FACTORS}
        ideals, extraps, ses = [], [], []
        n2q = None
        for x in X:
            target = circ_w.assign_parameters(dict(zip(xp, x)))
            ideals.append(float(np.real(Statevector.from_instruction(target).expectation_value(obs_op))))
            vals = []
            for s in SCALE_FACTORS:
                cc = fold_global(target.copy(), s) if s > 1 else target.copy()
                cc.measure_all()
                tc = transpile(cc, basis_gates=IQM_BASIS_GATES, coupling_map=cmap,
                               initial_layout=layout, optimization_level=1, seed_transpiler=args.seed)
                if n2q is None and s == 1:
                    n2q = sum(1 for i in tc.data if i.operation.name in ("cz", "cx"))
                counts = sim.run(tc, shots=args.shots).result().get_counts()
                v = float(np.dot(coeffs, perqubit_z_from_counts(counts, n)))
                vals.append(v); per_scale[s].append(v)
                if s == max(SCALE_FACTORS):
                    ses.append(expval_se(counts, coeffs))
            extraps.append(extrapolate(SCALE_FACTORS, vals, "richardson"))

        m = {s: float(np.mean(np.abs(per_scale[s]))) for s in SCALE_FACTORS}
        smax = max(SCALE_FACTORS)
        R = m[smax] / m[1] if m[1] > 0 else float("nan")
        mi = float(np.mean(np.abs(ideals)))
        n_unphys = sum(1 for e in extraps if abs(e) > 1.0)
        err_raw = float(np.mean([abs(i - v) for i, v in zip(ideals, per_scale[1])]))
        err_zne = float(np.mean([abs(i - e) for i, e in zip(ideals, extraps)]))
        ret_norm = float(np.nanmean([retention_normalized(v, i)
                                     for v, i in zip(per_scale[1], ideals)]))
        snr = float(np.mean([abs(v) / se for v, se in zip(per_scale[smax], ses)]))
        verdict = (("KOLAPS — liczby ZNE niewiarygodne" if R < 0.15 else
                    "ryzyko graniczne" if R < 0.30 else "sygnał zachowany")
                   if args.legacy_verdict else "")
        print(f"  {placement:>8}:{pattern:<11} cz={n2q:>3} | |O| ideal={mi:.3f} "
              f"lam1={m[1]:.3f} lam3={m[3]:.3f} lam5={m[5]:.3f}")
        print(f"      R=|O(5)|/|O(1)| = {R:.3f} | retencja/ideal = {ret_norm:.3f} | "
              f"SNR(lam_max) = {snr:.1f}" + (f" -> {verdict}" if verdict else "") + " | "
              f"err_raw={err_raw:.4f} err_zne={err_zne:.4f} | poza [-1,1]: {n_unphys}/{len(extraps)}")
        rows.append({"placement": placement, "pattern": pattern, "transpiled_cz": n2q,
                     "abs_ideal": round(mi, 4), "abs_lam1": round(m[1], 4),
                     "abs_lam3": round(m[3], 4), "abs_lam5": round(m[5], 4),
                     "retention_R": round(R, 4), "retention_norm": round(ret_norm, 4),
                     "snr_lmax": round(snr, 3), "err_raw": round(err_raw, 4),
                     "err_zne": round(err_zne, 4), "n_unphysical": n_unphys, "verdict": verdict})

    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"\nzapisano {args.out}")
    print("ODCZYT: niski SNR przy lambda_max i niska retencja/ideal => Richardson degeneruje się")
    print("do przeskalowania jednego pomiaru (arXiv:2607.09360). Rozstrzyga kontrola garbage-")
    print("folding i W_neg (sim/calibrate_wneg_null.py), nie samo R.")


if __name__ == "__main__":
    main()
