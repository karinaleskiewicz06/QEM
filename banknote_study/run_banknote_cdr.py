"""CDR na drabinie ansatzów Banknote --- drugi zbiór danych dla wyniku o~załamaniu liniowości.

DLACZEGO. Główny wynik pracy (monotoniczny spadek $r^2$ CDR z~narzutem routingu) zmierzono na
zbiorze two_curves. Banknote jest niezależnym zadaniem z~niezależnie wytrenowanymi modelami
(checkpointy KN-Axion, 5-krotna walidacja krzyżowa), więc powtórzenie na nim tego samego pomiaru
sprawdza, czy załamanie jest własnością sprzętu i~routingu, a~nie tego jednego zadania.

Trzy ansatze KN-Axion tworzą naturalną drabinę kosztu routingu na topologii gwiazdy:
    star (natywny, gwiazda)  <  odra (natywny pierścień)  <  simulator (CRX/CRY pierścień)
Zmienną jest zatem ta sama wielkość co w~badaniu głównym --- liczba bramek CZ po transpilacji.

PROTOKÓŁ jest identyczny z~`run_odra_cdr.py` (kotwica zbioru treningowego w~x_mean, jedno
dopasowanie na ansatz, wartości idealne obwodów treningowych liczone dokładnie w~formalizmie
stabilizatorowym), dzięki czemu liczby są bezpośrednio porównywalne z~drabiną two_curves.

UWAGA O~ODCZYCIE: odczytem Banknote jest \\langle Z \\rangle na JEDNYM kubicie, zależnym od ansatzu
(star czyta z~węzła centralnego QB2, pozostałe z~kubitu 0). Nie jest to obserwabl permutacyjnie
niezmienniczy, więc po transpilacji odczytujemy \\emph{końcowy} drut kubitu logicznego
(`logical_final_wires`), a~nie drut o~tym samym numerze.

    python banknote_study/run_banknote_cdr.py            # próbny przebieg
    python banknote_study/run_banknote_cdr.py --sim      # symulator kalibrowany ODRĄ (za darmo)
    python banknote_study/run_banknote_cdr.py --submit   # sprzęt ODRA
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys

import numpy as np

QEM_ROOT = pathlib.Path(__file__).resolve().parents[1]
UPSTREAM = QEM_ROOT / "banknote_study" / "upstream"
sys.path.insert(0, str(QEM_ROOT))
sys.path.insert(0, str(UPSTREAM / "src"))

from qiskit.quantum_info import Statevector  # noqa: E402

from cdr import (  # noqa: E402
    near_clifford_training_circuits, clifford_ideal_expval, fit_cdr, apply_cdr,
)
from metrics import accuracy, macro_f1  # noqa: E402
from noisy_sim import (  # noqa: E402
    load_iqm_calibration, make_noisy_simulator, logical_final_wires,
    perqubit_z_from_counts,
)
from shots_to_target import cdr_effective_shots  # noqa: E402
from zne_dryrun import native_transpile  # noqa: E402
from run_hardware import qiskit_to_iqm, perqubit_z_iqm, submit_batch, fetch_counts  # noqa: E402
from run_zne_banknote import (  # noqa: E402
    ANSATZ_FNS, READOUT_QUBIT, build_full_circuit, load_weights, load_eval_subset, zobs,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ansatze", nargs="+", default=["star", "odra", "simulator"],
                    choices=list(ANSATZ_FNS))
    ap.add_argument("--depth", type=int, default=4, choices=(2, 4, 6))
    ap.add_argument("--fold", type=int, default=1, choices=(1, 2, 3, 4, 5))
    ap.add_argument("--epoch", type=int, default=30, choices=(20, 30))
    ap.add_argument("--n-samples", type=int, default=30, help="podzbiór testowy (koszt rośnie z nim)")
    ap.add_argument("--n-train", type=int, default=100)
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-batch", type=int, default=100)
    ap.add_argument("--calibration", default="calibrations/odra.json")
    ap.add_argument("--url", default="")
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--out", default="banknote_study/banknote_cdr_results.csv")
    args = ap.parse_args()

    import os
    args.url = args.url or os.environ.get("IQM_SERVER_URL", "")

    n = 5
    X_eval, y_eval = load_eval_subset(args.fold, args.n_samples, args.seed)
    x_mean = X_eval.mean(axis=0)

    per_ans = args.n_train + len(X_eval)
    total = per_ans * len(args.ansatze)
    njobs = len(args.ansatze) * -(-per_ans // args.max_batch)
    print(f"PLAN: Banknote CDR | ansatze {args.ansatze} | głębokość {args.depth} | fold {args.fold}")
    print(f"  {len(X_eval)} pkt ewaluacyjnych | n_train {args.n_train} | shots {args.shots}")
    print(f"  obwodów {total} ({per_ans}/ansatz) | zgłoszeń {njobs} | pomiarów {total*args.shots}")
    if not (args.submit or args.sim):
        print("\n[PRÓBNY PRZEBIEG] nic nie wysłano. Dodaj --sim (za darmo) albo --submit.")
        return

    if args.submit:
        if not args.url:
            raise SystemExit("ustaw IQM_SERVER_URL (oraz IQM_TOKEN), aby wysłać na ODRĘ.")
        from iqm.iqm_client import IQMClient
        client = IQMClient(args.url)
        print("\n>>> ODRA (sprzęt) <<<\n")
        _sim = None
    else:
        cal = load_iqm_calibration(str(QEM_ROOT / args.calibration))
        _sim = make_noisy_simulator(cal, dd=False)
        print(f"\n[--sim] symulator kalibrowany plikiem {args.calibration}\n")

    def run_natives(natives, wire):
        """Wykonaj natywne obwody; zwróć ⟨Z⟩ na wskazanym drucie fizycznym."""
        if args.submit:
            vals = []
            for s in range(0, len(natives), args.max_batch):
                chunk = natives[s: s + args.max_batch]
                job = submit_batch(client, [qiskit_to_iqm(c) for c in chunk], args.shots,
                                   dd_on=False)
                counts, jid = fetch_counts(client, job)
                print(f"    zadanie {jid} | {len(counts)}/{len(natives)} obwodów")
                vals += [float(perqubit_z_iqm(c, n)[wire]) for c in counts]
            return vals
        out = []
        for c in natives:
            cc = c.copy(); cc.measure_all()
            counts = _sim.run(cc, shots=args.shots).result().get_counts()
            out.append(float(perqubit_z_from_counts(counts, n)[wire]))
        return out

    rows = []
    for name in args.ansatze:
        circ, xp, wp = build_full_circuit(name, n, args.depth)
        weights = load_weights(name, args.depth, args.fold, args.epoch)
        circ_w = circ.assign_parameters(dict(zip(wp, weights)))
        obs = zobs(n, READOUT_QUBIT[name])

        anchor = circ_w.assign_parameters(dict(zip(xp, x_mean)))
        train = near_clifford_training_circuits(anchor, n_train=args.n_train, seed=args.seed)
        ideal_train = [clifford_ideal_expval(t, obs) for t in train]

        eval_circs, ideal_eval = [], []
        for x in X_eval:
            b = circ_w.assign_parameters(dict(zip(xp, x)))
            eval_circs.append(b)
            ideal_eval.append(float(np.real(
                Statevector.from_instruction(b).expectation_value(obs))))

        natives = [native_transpile(c, n) for c in train + eval_circs]
        # odczyt po transpilacji: końcowy drut logicznego kubitu odczytu
        wire = logical_final_wires(natives[0], n)[READOUT_QUBIT[name]]
        n2q = sum(1 for i in natives[0].data if i.operation.name in ("cz", "cx"))
        print(f"  {name:<10} cz={n2q:>3} | odczyt: log {READOUT_QUBIT[name]} -> drut {wire} "
              f"| {len(natives)} obwodów")
        vals = run_natives(natives, wire)

        a, b, r2 = fit_cdr(vals[: len(train)], ideal_train)
        err_raw, err_cdr, pred_raw, pred_cdr = [], [], [], []
        for e, ideal in enumerate(ideal_eval):
            raw = vals[len(train) + e]
            cv = apply_cdr(raw, a, b)
            err_raw.append(abs(raw - ideal)); pred_raw.append(np.sign(raw))
            err_cdr.append(abs(cv - ideal)); pred_cdr.append(np.sign(cv))

        row = {
            "dataset": "banknote", "ansatz": name, "depth": args.depth, "fold": args.fold,
            "transpiled_cz": n2q, "readout_wire": wire,
            "err_raw": round(float(np.mean(err_raw)), 4),
            "err_cdr": round(float(np.mean(err_cdr)), 4),
            "acc_raw": round(accuracy(y_eval, pred_raw), 4),
            "acc_cdr": round(accuracy(y_eval, pred_cdr), 4),
            "f1_raw": round(macro_f1(y_eval, pred_raw), 4),
            "f1_cdr": round(macro_f1(y_eval, pred_cdr), 4),
            "cdr_a": round(a, 4), "cdr_b": round(b, 4), "cdr_r2": round(r2, 4),
            "n_train": args.n_train, "shots": args.shots, "n_points": len(X_eval),
            "effective_shots": int(cdr_effective_shots(args.shots, args.n_train)),
            "source": "hardware" if args.submit else "simulator",
        }
        rows.append(row)
        print(f"    -> err {row['err_raw']:.4f} -> {row['err_cdr']:.4f} | "
              f"acc {row['acc_raw']:.2f} -> {row['acc_cdr']:.2f} | r2 {r2:.4f}")
        with open(QEM_ROOT / args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)

    print(f"\nzapisano {args.out}")
    print("ODCZYT: jeśli r^2 spada z liczbą CZ także tutaj, załamanie nie jest własnością")
    print("zadania two_curves, lecz sprzętu i narzutu routingu.")


if __name__ == "__main__":
    main()
