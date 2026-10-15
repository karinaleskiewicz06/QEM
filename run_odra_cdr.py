"""CDR na PRAWDZIWEJ ODRZE (IQM Spark) --- domyka lukę: ramię CDR nigdy nie poszło na to urządzenie.

DLACZEGO TEN SKRYPT ISTNIEJE. Kampania sprzętowa ODRY (2026-07-30..08-01) objęła ZNE, REM i DD,
bo kod CDR powstał dopiero 2026-08-26 --- 25 dni później. Wszystkie dotychczasowe liczby CDR dla
ODRY (`cdr_hard_results.csv`) pochodzą więc z SYMULACJI, co osłabia tezę o topologicznej ogólności:
opiera się ona na dwóch urządzeniach sprzętowych plus jednej symulacji. Ten skrypt zbiera brakujący
punkt sprzętowy.

PROTOKÓŁ jest celowo IDENTYCZNY z `run_garnet_cdr.py` --- inaczej liczby nie byłyby porównywalne:

  * jeden zbiór treningowy bliski Cliffordowi na wzorzec, zbudowany z obwodu-kotwicy w x_mean
    (ta sama struktura i ten sam routing co obwody ewaluacyjne);
  * wartości idealne obwodów treningowych liczone dokładnie statewektorem (obwody są
    Cliffordowskie, więc przy większej skali wystarczy symulator stabilizatorowy);
  * JEDNO dopasowanie ideal ~ a*noisy + b na wzorzec, r^2 raportowane jako sonda koherencji;
  * zbiór treningowy i obwody ewaluacyjne w tym samym zgłoszeniu, bo dryf jest główną słabością CDR.

Różni się tylko warstwa sprzętowa: ODRA idzie przez `iqm-client` (nie Resonance), więc reużywamy
prymitywów z `run_hardware.py` (konwersja do natywnego IQM, wsad z ponawianiem, odczyt per-kubitowy)
oraz `native_transpile` na mapie gwiazdy. Transpilator permutuje kubity, ale obserwabla to średnie Z
z równymi wagami --- jest permutacyjnie niezmiennicza, więc odczyt po numerze drutu jest poprawny
(to samo założenie co w kampanii ODRY z Month 1).

BEZPIECZEŃSTWO: bez --submit skrypt tylko buduje obwody i raportuje koszt.

    python run_odra_cdr.py                    # próbny przebieg (nic nie wysyła)
    python run_odra_cdr.py --sim              # walidacja na symulatorze (bez kredytów)
    python run_odra_cdr.py --submit           # ODRA (wymaga IQM_SERVER_URL + IQM_TOKEN)
"""
from __future__ import annotations

import argparse
import csv
import os
import pathlib

import numpy as np
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from cdr import near_clifford_training_circuits, clifford_ideal_expval, fit_cdr, apply_cdr
from qem.env_check import require_locked_environment, add_env_argument
from qem.provenance import RunRecorder
from metrics import accuracy, macro_f1
from noisy_sim import (
    load_frozen_model, observable_coeffs, make_noisy_simulator,
    execute_expectation, DeviceCalibration,
)
from shots_to_target import cdr_effective_shots
from zne_dryrun import native_transpile, fold_global, extrapolate, SCALE_FACTORS
from run_hardware import qiskit_to_iqm, perqubit_z_iqm, submit_batch, fetch_counts
from topology import device_coupling_map

PATTERNS = ("star", "linear", "circular", "all_to_all")


RECORDER = None          # P0: ustawiany w main(); None wylacza zapis surowych danych
T_1Q, T_2Q = 20e-9, 60e-9
COEFFS = None            # wspolczynniki obserwabli; ustawiane w main()
REDUCTION = "dot_perqubit"   # sciezka sprzetowa; symulator przestawia na expval_z_sum


def _record(natives, counts, vals, tags) -> None:
    """Dopisz surowe zliczenia kazdego obwodu do counts.jsonl (jesli RECORDER aktywny).

    Na symulatorze ``execute_expectation`` nie zwraca zliczen, wiec zapisujemy sam
    obwod i policzone <O>; na sprzecie mamy pelne zliczenia i zapisujemy jedno i drugie.
    """
    if RECORDER is None:
        return
    for i, (native, val) in enumerate(zip(natives, vals)):
        tag = (tags[i] if tags and i < len(tags) else {}) or {}
        cid = tag.pop("circuit_id", f"{tag.get('point', 'p?')}/c{i}")
        RECORDER.record_circuit(cid, counts[i] if counts else {}, native=native,
                                t_1q=T_1Q, t_2q=T_2Q, expval=float(val),
                                coeffs=list(map(float, COEFFS)),
                                reduction=REDUCTION, **tag)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--patterns", nargs="+", default=list(PATTERNS), choices=list(PATTERNS))
    ap.add_argument("--models-dir", default="trained_models_hard")
    ap.add_argument("--eval-points", type=int, default=15)
    ap.add_argument("--n-train", type=int, default=100)
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--layers", type=int, default=None,
                    help="nadpisz liczbe warstw ansatzu (OS GLEBOKOSCI: kontrola dla tezy o "
                         "narzucie routingu; wymaga wag z train_star_depth.py)")
    ap.add_argument("--max-batch", type=int, default=100,
                    help="obwodów na jedno zgłoszenie (dzielimy wsad na porcje)")
    ap.add_argument("--url", default=os.environ.get("IQM_SERVER_URL", ""))
    ap.add_argument("--campaign", default=None,
                    help="katalog runs/<campaign>/<window_id>/ (domyslnie odra_cdr)")
    ap.add_argument("--window-id", default="w1")
    ap.add_argument("--no-provenance", action="store_true",
                    help="pomin manifest i counts.jsonl (stare zachowanie: sam CSV)")
    add_env_argument(ap)
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--sim", action="store_true", help="walidacja na symulatorze (bez kredytów)")
    ap.add_argument("--zne", action="store_true",
                    help="dodaj ramię ZNE w TYM SAMYM wsadzie (raw/CDR/ZNE w jednych warunkach)")
    ap.add_argument("--out", default="odra_cdr_results.csv")
    args = ap.parse_args()
    require_locked_environment(allow_mismatch=args.allow_env_mismatch)

    global RECORDER, COEFFS, REDUCTION
    if not args.no_provenance:
        RECORDER = RunRecorder.open(args.campaign or "odra_cdr", window_id=args.window_id,
                                    args=vars(args), seed=args.seed, device="odra",
                                    submitted=args.submit)
        print(f"[provenance] {RECORDER.dir}")

    _, observable, cfg = load_frozen_model(models_dir=args.models_dir)
    base_layers = cfg["n_layers"]          # warstwy modelu zamrozonego (plik referencyjny)
    if args.layers is not None:
        # OS GLEBOKOSCI: ten sam wzorzec, wiecej warstw -> wiecej CZ przy ZEROWYM routingu.
        cfg = {**cfg, "n_layers": args.layers}
        print(f"[os glebokosci] n_layers {base_layers} -> {args.layers} "
              f"(zero narzutu routingu; wagi z train_star_depth.py)")
    n = cfg["n_qubits"]
    md = pathlib.Path(args.models_dir)
    # Podzbior ewaluacyjny NIE zalezy od liczby warstw -- to podzial zbioru danych, nie model.
    # Plik referencyjny czytamy wiec zawsze z tagu modelu zamrozonego (base_layers), zeby os
    # glebokosci ewaluowala sie na DOKLADNIE tych samych punktach co os routingu.
    tag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
           f"{cfg['entanglement']}_{cfg['readout']}_L{base_layers}")
    ref = np.load(md / f"{tag}_reference.npz")
    X_eval, y_eval = ref["X_eval"][: args.eval_points], ref["y_eval"][: args.eval_points]
    star_weights = np.load(md / cfg["weights_file"])
    coeffs = observable_coeffs(observable, n)
    COEFFS = coeffs
    x_mean = X_eval.mean(axis=0)

    # ZNE dokłada obwody złożone (fold) w skalach >1; skala 1 to te same obwody, co ramię raw
    extra_scales = [s for s in SCALE_FACTORS if s != 1] if args.zne else []
    per_pat = args.n_train + len(X_eval) * (1 + len(extra_scales))
    total = per_pat * len(args.patterns)
    njobs = sum(-(-per_pat // args.max_batch) for _ in args.patterns)
    print(f"PLAN: ODRA (gwiazda, iqm-client) | wzorce {args.patterns} | "
          f"{len(X_eval)} pkt ewaluacyjnych | n_train {args.n_train} | shots {args.shots}")
    print(f"  obwodów {total} ({per_pat}/wzorzec) | zgłoszeń {njobs} | "
          f"pomiarów {total * args.shots}")
    if not (args.submit or args.sim):
        print("\n[PRÓBNY PRZEBIEG] nic nie wysłano. Dodaj --sim (za darmo) albo --submit.")
        return

    if args.submit:
        if not args.url:
            raise SystemExit("ustaw IQM_SERVER_URL (oraz IQM_TOKEN), aby wysłać na ODRĘ.")
        from iqm.iqm_client import IQMClient
        client = IQMClient(args.url)  # token z IQM_TOKEN
        print("\n>>> ODRA: dostęp niemierzony kredytami Resonance <<<\n")
        _sim = _cal = None
    else:
        cmap = device_coupling_map("odra")
        _cal = DeviceCalibration(num_qubits=n, coupling_map=cmap, p_2q=0.01)
        _sim = make_noisy_simulator(_cal)
        # execute_expectation redukuje przez expval_z_from_counts, a sciezka
        # sprzetowa przez np.dot(coeffs, perqubit_z): roznia sie kolejnoscia
        # sumowania, wiec rebuild musi wiedziec, ktora odtwarzac.
        REDUCTION = "expval_z_sum"
        print("\n[--sim] pełny potok na symulatorze (bez kredytów)\n")

    def run_natives(natives: list, tags: list | None = None) -> list[float]:
        """Wykonaj natywne obwody i zwróć ⟨O⟩ dla każdego (kolejność zachowana).

        Gdy ``RECORDER`` jest aktywny (P0), każdy obwód trafia razem ze swoimi surowymi
        zliczeniami do ``counts.jsonl``; ``tags`` opisuje rolę obwodu (punkt, indeks
        treningowy, ramię), żeby wynik dało się odtworzyć bez CSV.
        """
        if not args.submit:
            # pre_transpiled=True: obwody są już w bazie {r, cz} i nie wolno ich
            # przekompilować --- zniknęłaby struktura routingu, którą badamy
            # return_counts=True: bez surowych zliczen rekord w counts.jsonl nie da sie
            # odtworzyc, a to jest caly sens archiwum (P0).
            pairs = [execute_expectation(c, observable, _sim, shots=args.shots, cal=_cal,
                                         pre_transpiled=True, return_counts=True)
                     for c in natives]
            vals = [v for v, _ in pairs]
            _record(natives, [cnt for _, cnt in pairs], vals, tags)
            return vals
        vals: list[float] = []
        for s in range(0, len(natives), args.max_batch):
            chunk = natives[s: s + args.max_batch]
            job = submit_batch(client, [qiskit_to_iqm(c) for c in chunk], args.shots, dd_on=False)
            counts, jid = fetch_counts(client, job)
            print(f"    zadanie {jid} | {len(counts)}/{len(natives)} obwodów")
            chunk_vals = [float(np.dot(coeffs, perqubit_z_iqm(c, n))) for c in counts]
            if RECORDER is not None:
                RECORDER.add_job(jid)
            _record(chunk, counts, chunk_vals,
                    tags[s: s + args.max_batch] if tags else None)
            vals += chunk_vals
        return vals

    def weights_for(pattern: str) -> np.ndarray:
        ptag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
                f"{pattern}_{cfg['readout']}_L{cfg['n_layers']}")
        wp = md / f"{ptag}_weights.npy"
        if wp.exists():
            return np.load(wp)
        if args.layers is not None:
            # cichy fallback na wagi L=3 dalby obwod o zlej liczbie parametrow -> lepiej padnac
            raise SystemExit(f"brak wag dla L={cfg['n_layers']}: {wp}\n"
                             f"uruchom najpierw: python train_star_depth.py --layers {cfg['n_layers']}")
        return star_weights

    rows = []
    for pattern in args.patterns:
        ans = HardwareEfficientAnsatz(n, cfg["n_layers"], num_features=cfg["n_features"],
                                      entanglement=pattern,
                                      entangling_gate=cfg.get("entangling_gate", "cx"))
        circ = ans.build()
        xparams, wparams = ans.feature_parameters(circ), ans.weight_parameters(circ)
        circ_w = circ.assign_parameters(dict(zip(wparams, weights_for(pattern))))

        # zbiór treningowy z kotwicy w x_mean (jeden na wzorzec, jak u Garneta)
        anchor = circ_w.assign_parameters(dict(zip(xparams, x_mean)))
        train = near_clifford_training_circuits(anchor, n_train=args.n_train, seed=args.seed)
        ideal_train = [clifford_ideal_expval(tc, observable) for tc in train]

        eval_circs, ideal_eval = [], []
        for x in X_eval:
            b = circ_w.assign_parameters(dict(zip(xparams, x)))
            eval_circs.append(b)
            ideal_eval.append(float(np.real(
                Statevector.from_instruction(b).expectation_value(observable))))

        natives = [native_transpile(c, n) for c in train + eval_circs]
        nat_eval = natives[len(train):]
        # składanie WYKONUJEMY na obwodzie natywnym, żeby struktura U^dag U nie została
        # zoptymalizowana przez ponowną transpilację (tak samo jak w run_hardware.py)
        for s in extra_scales:
            natives.extend(fold_global(c, s) for c in nat_eval)
        n2q = sum(1 for i in natives[0].data if i.operation.name in ("cz", "cx"))
        print(f"  {pattern:<11} cz={n2q:>3} | {len(natives)} obwodów"
              + (f" (ZNE, skale {SCALE_FACTORS})" if args.zne else ""))
        # etykiety: pozwalaja odtworzyc role kazdego obwodu z samego counts.jsonl
        tags = [{"circuit_id": f"{pattern}/train{i:03d}", "pattern": pattern,
                 "arm": "cdr", "role": "train", "train_index": i, "scale": 1,
                 "transpiled_cz": n2q} for i in range(len(train))]
        tags += [{"circuit_id": f"{pattern}/eval{i:03d}/lam1", "pattern": pattern,
                  "arm": "cdr", "role": "eval", "point_index": i, "scale": 1,
                  "transpiled_cz": n2q} for i in range(len(eval_circs))]
        for s_ in extra_scales:
            tags += [{"circuit_id": f"{pattern}/eval{i:03d}/lam{s_}", "pattern": pattern,
                      "arm": "zne", "role": "eval", "point_index": i, "scale": int(s_),
                      "transpiled_cz": n2q} for i in range(len(eval_circs))]
        vals = run_natives(natives, tags)

        a, b, r2 = fit_cdr(vals[: len(train)], ideal_train)
        base = len(train)
        err_raw, err_cdr, err_zne, pred_raw, pred_cdr = [], [], [], [], []
        for e, ideal in enumerate(ideal_eval):
            raw = vals[base + e]
            cdr_val = apply_cdr(raw, a, b)
            err_raw.append(abs(raw - ideal)); pred_raw.append(np.sign(raw))
            err_cdr.append(abs(cdr_val - ideal)); pred_cdr.append(np.sign(cdr_val))
            if args.zne:
                # skala 1 to `raw`; kolejne bloki po len(X_eval) wartości na skalę
                sv = [raw] + [vals[base + len(X_eval) * (1 + k) + e]
                              for k in range(len(extra_scales))]
                err_zne.append(abs(extrapolate(SCALE_FACTORS, sv, "richardson") - ideal))

        row = {
            "device": "odra", "placement": "optimal", "pattern": pattern,
            "transpiled_cz": n2q, "per_pattern_weights": True,
            "err_raw": round(float(np.mean(err_raw)), 4),
            "err_cdr": round(float(np.mean(err_cdr)), 4),
            "acc_raw": round(accuracy(y_eval, pred_raw), 4),
            "acc_cdr": round(accuracy(y_eval, pred_cdr), 4),
            "f1_raw": round(macro_f1(y_eval, pred_raw), 4),
            "f1_cdr": round(macro_f1(y_eval, pred_cdr), 4),
            "err_zne": round(float(np.mean(err_zne)), 4) if err_zne else "",
            "cdr_a": round(a, 4), "cdr_b": round(b, 4), "cdr_r2": round(r2, 4),
            "dd": False,
            "n_train": args.n_train, "shots": args.shots,
            "effective_shots": int(cdr_effective_shots(args.shots, args.n_train)),
            "source": "hardware" if args.submit else "simulator",
        }
        rows.append(row)
        print(f"    -> raw {row['err_raw']:.4f} | CDR {row['err_cdr']:.4f}"
              + (f" | ZNE {row['err_zne']:.4f}" if err_zne else "")
              + f" | acc {row['acc_raw']:.2f} -> {row['acc_cdr']:.2f} | r2 {r2:.4f}")
        with open(args.out, "w", newline="") as f:  # zapis po każdym wzorcu (crash-safe)
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)

    print(f"\nzapisano {args.out}")
    if RECORDER is not None:
        RECORDER.close()
        print(f"[provenance] manifest + counts.jsonl -> {RECORDER.dir}")
    print("ODCZYT: r^2 ma spadać z liczbą CZ --- to sprzętowy odpowiednik krzywej ODRY")
    print("z Rysunku 1, zastępujący dotychczasową symulację.")


if __name__ == "__main__":
    main()
