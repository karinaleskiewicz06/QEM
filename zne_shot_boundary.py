"""Granica opłacalności ZNE w funkcji budżetu pomiarów --- test PRE-REJESTROWANEJ prognozy.

TEZA. ZNE wymienia obciążenie na wariancję. Przy ZRÓWNANYM całkowitym budżecie S pomiarów
estymator Richardsona ma wariancję (sum c_i^2)*|Lambda|*V/S, więc opłaca się tylko gdy
    B^2 > kappa * V / S,   kappa = (sum c_i^2)*|Lambda| - 1  (= 14.66 dla lambda={1,3,5}),
gdzie B to obciążenie (systematyczna część błędu), a V to wariancja obserwabla na pomiar.
Równoważnie: dla ustalonego punktu drabiny przejście następuje przy S* = kappa*V/B^2.

PROGNOZA (zapisana PRZED pomiarem, V ~ 0.2 dla mean-Z na 5 kubitach):
    Garnet optimal:star (B ~ 0.073)  ->  S* ~ 550   (ZNE szkodzi ponizej, pomaga powyzej)
    Garnet adverse:star (B ~ 0.117)  ->  S* ~ 214

TRZY RZECZY METODOLOGICZNE, które odróżniają ten skrypt od kampanii twirlingowej:

1. ZRÓWNANY BUDŻET CAŁKOWITY. Ramię ZNE dostaje S/|Lambda| pomiarów NA SKALĘ, więc zużywa
   dokładnie S pomiarów --- tyle samo co ramię surowe. Bez tego porównanie jest bezwartościowe:
   ZNE z 3S pomiarami "wygrywałoby" samą statystyką (ten sam confound co przy twirlingu).

2. MSE, NIE BŁĄD BEZWZGLĘDNY. Wyprowadzenie granicy dotyczy błędu średniokwadratowego
   (MSE = obciążenie^2 + wariancja), więc raportujemy MSE. Powtórzenia pozwalają rozdzielić
   te dwa składniki: średnia po powtórzeniach daje obciążenie, rozrzut --- wariancję.

3. POMIAR V ZAMIAST ZAŁOŻENIA. Rozrzut ramienia surowego po powtórzeniach daje V = S*sigma^2
   empirycznie. Jeśli zmierzone V odbiega od 0.2, przewidywane S* przelicza się samo --- czyli
   eksperyment jest informatywny także wtedy, gdy prognoza nie trafi.

    python zne_shot_boundary.py                      # dry-run (koszt, nic nie wysyla)
    python zne_shot_boundary.py --sim                # walidacja na symulatorze (za darmo)
    python zne_shot_boundary.py --submit             # Garnet

PODZIAŁ NEYMANA (P3, Scavino Alfaro arXiv:2605.08251, Remark 3). Z --allocation neyman
budżet ZNE dzieli się nie po równo, lecz n_i ∝ |c_i|·sigma_i, gdzie sigma_i (odchylenie
na pojedynczy pomiar przy skali i) pochodzi z krótkiego pilota (--pilot-shots). Wtedy
    kappa_opt = (sum |c_i| sigma_i / sigma_1)^2 - 1    (= 3.0 / 11.25 / 35.0 przy równych sigma)
i tę stałą przewiduje się przed pomiarem zamiast 4.0 / 14.66 / 44.56.

ESTYMATA BEZ CICHEGO FALLBACKU. Richardson z |E|>1.25 nie jest już zastępowany fitem
liniowym; teoria kappa dotyczy czystego estymatora Richardsona, a fallback zmieniał jego
wariancję przy małych budżetach. Liczbę estymat niefizycznych raportują kolumny
n_unphysical / n_fallback. Stare zachowanie: --legacy-clamp.
"""
from __future__ import annotations

import argparse
import csv
import math
import pathlib

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from noisy_sim import (
    load_frozen_model, readout_observable, observable_coeffs, perqubit_z_from_counts,
    make_noisy_simulator, DeviceCalibration, IQM_BASIS_GATES,
)
from zne_dryrun import SCALE_FACTORS, fold_global
from topology import device_coupling_map, hardware_placement
from qem.env_check import require_locked_environment, add_env_argument
from qem.provenance import RunRecorder, add_archive_argument, guard_archive
from sim import device_model
from qem.compile import compile_native
from qem.zne import (extrapolate_flagged, kappa_opt, kappa_uniform, neyman_allocation,
                     richardson_coefficients, uniform_allocation)


def richardson_kappa(lams):
    """(kappa przy podziale równym, współczynniki Richardsona); zob. qem.zne."""
    return kappa_uniform(lams), [float(c) for c in richardson_coefficients(lams)]


def per_shot_variance_from_counts(counts, coeffs, n):
    """Wariancja obserwabla NA POJEDYNCZY POMIAR, wyznaczona wprost z rozkładu zliczeń.

    Dla obserwabla O = sum_i c_i Z_i każdy pomiar daje wartość v = sum_i c_i (1-2 b_i), gdzie b_i
    to zmierzony bit kubita i. Mając zliczenia, liczymy wariancję próbkową tych wartości --- czyli
    estymujemy V z WSZYSTKICH S pomiarów, a nie z kilku powtórzeń. Jest to nieporównanie
    dokładniejsze niż V = S * Var(średnie po powtórzeniach), które przy 5 powtórzeniach ma ~70%
    błędu względnego na pojedyncze oszacowanie.
    """
    tot = sum(counts.values())
    vals, w = [], []
    for b, cnt in counts.items():
        s = b.replace(" ", "")
        v = sum(coeffs[q] * (1 - 2 * int(s[len(s) - 1 - q])) for q in range(n))
        vals.append(v); w.append(cnt / tot)
    vals = np.array(vals); w = np.array(w)
    mean = float(np.dot(w, vals))
    return float(np.dot(w, (vals - mean) ** 2))



RECORDER = None          # P0: manifest + counts.jsonl; None = stare zachowanie
_REC_SEQ = [0]
COEFFS = None            # wspolczynniki obserwabli; ustawiane w main()


def _record(circs, counts, shots, arm="zne", metas=None) -> None:
    """Dopisz surowe zliczenia kazdego obwodu kappa-kampanii do counts.jsonl.

    Numeracja jest sekwencyjna w obrebie okna: te obwody roznia sie budzetem i skala
    foldingu, a nie rola, wiec identyfikator ma byc tylko stabilnym kluczem do
    zliczen. Skale i budzet odczytuje sie z metadanych, nie z nazwy: ``metas`` (jeden
    slownik na obwod) niesie budget_S, role (pilot/raw/zne), rep, target, scale.
    Zapisywane jest tez <O>, wiec rebuild_from_counts moze je sprawdzic bit w bit.
    """
    if RECORDER is None:
        return
    metas = metas or [{}] * len(circs)
    for c, cnt, meta in zip(circs, counts, metas):
        i = _REC_SEQ[0]; _REC_SEQ[0] += 1
        extra = {}
        if COEFFS is not None:
            extra["expval"] = float(np.dot(COEFFS, perqubit_z_from_counts(cnt, len(COEFFS))))
        RECORDER.record_circuit(f"kappa/c{i:05d}", cnt, native=c,
                                t_1q=T_1Q, t_2q=T_2Q, with_qasm=False,
                                arm=arm, shots_requested=int(shots),
                                coeffs=None if COEFFS is None else list(map(float, COEFFS)),
                                reduction="dot_perqubit", **meta, **extra)
T_1Q, T_2Q = 20e-9, 60e-9

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device", default="garnet")
    ap.add_argument("--points", nargs="+", default=["optimal:star"])
    ap.add_argument("--budgets", type=int, nargs="+", default=[128, 256, 512, 1024, 2048, 4096],
                    help="CAŁKOWITY budżet pomiarów na punkt ewaluacyjny (dzielony na skale w ZNE)")
    ap.add_argument("--reps", type=int, default=5, help="powtórzenia (rozdzielają obciążenie od wariancji)")
    ap.add_argument("--eval-points", type=int, default=4)
    ap.add_argument("--models-dir", default="trained_models_hard")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--scales", type=int, nargs="+", default=None,
                    help="wspolczynniki skalowania szumu (skladanie globalne -> tylko NIEPARZYSTE). "
                         "Domyslnie {1,3,5} (kappa=14.66). Inne zestawy przewiduja INNE kappa: "
                         "{1,3} -> 4.00, {1,3,5,7} -> 44.56 --- test ogolnosci teorii.")
    ap.add_argument("--allocation", choices=["uniform", "neyman"], default="uniform",
                    help="podział budżetu ZNE między skale: równy (S/|Lambda|, jak w archiwum) "
                         "albo Neymana n_i ∝ |c_i| sigma_i z sigma_i z pilota")
    ap.add_argument("--pilot-shots", type=int, default=2048,
                    help="[neyman] pomiary na obwód w pilocie szacującym sigma_i dla każdej skali")
    ap.add_argument("--legacy-clamp", action="store_true",
                    help="stary cichy fallback Richardson -> fit liniowy przy |E|>1.25")
    ap.add_argument("--out", default="zne_shot_boundary_results.csv")
    ap.add_argument("--resume", action="store_true",
                    help="pomiń pary (punkt, budżet) już obecne w --out i dopisz resztę; "
                         "zerwanie połączenia nie kasuje opłaconych pomiarów")
    ap.add_argument("--campaign", default='zne_boundary',
                    help="katalog runs/<campaign>/<window_id>/")
    ap.add_argument("--window-id", default="w1")
    ap.add_argument("--no-provenance", action="store_true",
                    help="pomin manifest i counts.jsonl")
    device_model.add_arguments(ap)
    ap.add_argument("--legacy-transpile", action="store_true",
                    help="ODRA: stara transpilacja (transpile opt1 bez scalania 1q) zamiast "
                         "qem.compile.compile_native; potrzebne do odtworzenia archiwum")
    add_archive_argument(ap)
    add_env_argument(ap)
    args = ap.parse_args()
    require_locked_environment(allow_mismatch=args.allow_env_mismatch)
    args.out = guard_archive(args.out, allow=args.allow_archive_write)
    dev = device_model.from_args(args, args.device)
    if dev is not None:
        args.sim = True
        print(dev.describe())

    global RECORDER, COEFFS
    if not args.no_provenance:
        RECORDER = RunRecorder.open(args.campaign, window_id=args.window_id,
                                    args=vars(args), seed=getattr(args, 'seed', None),
                                    device=args.device, submitted=args.submit)
        print(f"[provenance] {RECORDER.dir}")
        # wznowienie: numeracja dalej, nie od zera (inaczej ID obwodow sie powtarzaja)
        _REC_SEQ[0] = RECORDER.n_recorded
        if dev is not None:
            RECORDER.set_extra("device_model", device_model.manifest_entry(dev))

    # Galaz domyslna odwolywala sie wczesniej do nazwy, ktora nie istnieje na poziomie
    # modulu, a przypisanie w tej samej linii czynilo ja lokalna -- wiec kazdy przebieg
    # bez --scales konczyl sie UnboundLocalError. Archiwalne kampanie kappa dzialaly
    # tylko dlatego, ze --scales podawano zawsze jawnie. Zrodlem jest SCALE_FACTORS.
    SCALES = list(args.scales) if args.scales else list(SCALE_FACTORS)
    if any(x % 2 == 0 for x in SCALES):
        raise SystemExit(f"skladanie globalne daje tylko nieparzyste skale; podano {SCALES}")
    kappa, coeffs_r = richardson_kappa(SCALES)
    kappa_neyman_eq = kappa_opt(SCALES)       # przy równych sigma; pilot je zastąpi
    neyman = args.allocation == "neyman"
    _, observable, cfg = load_frozen_model(models_dir=args.models_dir)
    n = cfg["n_qubits"]; md = pathlib.Path(args.models_dir)
    tag = f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_star_{cfg['readout']}_L{cfg['n_layers']}"
    X = np.load(md / f"{tag}_reference.npz")["X_eval"][: args.eval_points]
    coeffs = observable_coeffs(observable, n)
    COEFFS = coeffs
    obs_op = readout_observable(n, cfg["readout"])
    cmap = device_coupling_map(args.device)

    if args.submit:
        if args.device == "odra":
            from odra_backend import get_backend, transpile_for_backend, run_circuits
        else:
            from iqm_resonance import get_backend, transpile_for_backend, run_circuits
        backend = get_backend(args.device)
        def tpile(c, layout): return transpile_for_backend(c, backend, initial_layout=layout)
        def run(circs, shots, arm="zne", metas=None):
            kw = ({"on_job": RECORDER.add_job}
                  if RECORDER is not None and args.device == "odra" else {})
            out = run_circuits(backend, circs, shots, **kw)
            _record(circs, out, shots, arm, metas)
            return out
    else:
        def tpile(c, layout):
            return transpile(c, basis_gates=IQM_BASIS_GATES, coupling_map=cmap,
                             initial_layout=layout, optimization_level=1, seed_transpiler=args.seed)
        if dev is not None:
            def run(circs, shots, arm="zne", metas=None):
                out = dev.run(circs, shots)
                _record(circs, out, shots, arm, metas)
                return out
        elif args.sim:
            ndev = max(max(e) for e in cmap) + 1
            _sim = make_noisy_simulator(
                DeviceCalibration(num_qubits=ndev, coupling_map=cmap, p_2q=0.01))
            def run(circs, shots, arm="zne", metas=None):
                out = [_sim.run(c, shots=shots).result().get_counts() for c in circs]
                _record(circs, out, shots, arm, metas)
                return out
        else:
            run = None

    if args.device == "odra" and not args.legacy_transpile:
        # P1/P7: ta sama sciezka kompilacji na sprzecie i w symulatorze
        def tpile(c, layout):
            return compile_native(c, layout=layout, seed=args.seed).circuit

    # ---- koszt ---- #
    per_pt = sum(args.reps * len(X) * (1 + len(SCALES)) for _ in args.budgets)
    tot_shots = sum(args.reps * len(X) * 2 * S for S in args.budgets) * len(args.points)
    circ = per_pt * len(args.points)
    # RZECZYWISTA liczba zadań: surowe + ZNE na budżet, dzielone po 100 obwodów. Przy
    # podziale Neymana skale mają różne liczby pomiarów, więc każda idzie osobnym zgłoszeniem.
    zne_jobs = (len(SCALES) * math.ceil(args.reps * len(X) / 100) if neyman
                else math.ceil(args.reps * len(X) * len(SCALES) / 100))
    jobs = len(args.points) * sum(math.ceil(args.reps * len(X) / 100) + zne_jobs
                                  for _ in args.budgets)
    if neyman:
        pilot_circ = len(args.points) * len(X) * len(SCALES)
        circ += pilot_circ
        tot_shots += pilot_circ * args.pilot_shots
        jobs += len(args.points) * len(SCALES) * math.ceil(len(X) / 100)
    print(f"PROGNOZA (pre-rejestrowana): kappa = {kappa:.3f}, wsp. Richardsona "
          f"{[round(c,3) for c in coeffs_r]}")
    print(f"  podział {args.allocation}"
          + (f": kappa_opt = {kappa_neyman_eq:.3f} przy równych sigma; ostateczna wartość "
             f"z sigma_i pilota ({args.pilot_shots} pomiarów/obwód)" if neyman else ""))
    print(f"  skale {SCALES} | S* = kappa*V/B^2 ; przy V~0.2 i~B zmierzonym na Garnecie:")
    for _b, _n in ((0.0567, "optimal:star"), (0.1003, "adverse:star")):
        _k = kappa_neyman_eq if neyman else kappa
        print(f"     {_n:<14} B={_b:.4f} -> S* ~ {_k*0.2/_b**2:.0f}")
    print(f"\nPLAN: {args.device} | punkty {args.points} | budżety {args.budgets} | "
          f"reps {args.reps} | eval {len(X)}")
    # ODRA nie jest rozliczana kredytami Resonance -- nie strasz uzytkownika cena, ktorej nie ma
    _cost = ("dostep niemierzony kredytami" if args.device == "odra"
             else f"~{tot_shots*0.0002 + jobs*0.33:.1f} kredytow")
    print(f"  obwodów {circ} | pomiarów {tot_shots} | jobów {jobs} | {_cost}")
    if not (args.submit or args.sim):
        print("\n[DRY-RUN] nic nie wysłano. Dodaj --sim (za darmo) albo --submit.")
        return

    rows = []
    done = set()
    if args.resume and pathlib.Path(args.out).exists():
        with open(args.out, newline="") as f:
            rd = csv.DictReader(f)
            if "allocation" not in (rd.fieldnames or []):
                raise SystemExit(f"{args.out} pochodzi sprzed P3 (brak kolumny 'allocation'); "
                                 "--resume pogubiłby nowe kolumny. Podaj nowe --out.")
            for r in rd:
                if r["allocation"] != args.allocation:
                    raise SystemExit(f"{args.out} ma allocation={r['allocation']}, "
                                     f"a uruchomiono z {args.allocation}")
                for k in ("transpiled_cz", "budget_S", "shots_per_scale", "reps"):
                    r[k] = int(r[k]) if r[k] else 0
                for k in ("bias_rms", "V_counts", "V_reps", "mse_raw", "mse_zne", "delta_mse"):
                    r[k] = float(r[k]) if r.get(k) else float("nan")
                rows.append(r)
                done.add((r["placement"], r["pattern"], r["budget_S"]))
        print(f"[resume] wczytano {len(rows)} wierszy z {args.out}")
    for spec in args.points:
        placement, pattern = spec.split(":")
        layout = hardware_placement(args.device, placement)
        ptag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_{pattern}"
                f"_{cfg['readout']}_L{cfg['n_layers']}")
        wpth = md / f"{ptag}_weights.npy"
        weights = np.load(wpth) if wpth.exists() else np.load(md / cfg["weights_file"])
        ans = HardwareEfficientAnsatz(n, cfg["n_layers"], num_features=cfg["n_features"],
                                      entanglement=pattern,
                                      entangling_gate=cfg.get("entangling_gate", "cx"))
        c0 = ans.build()
        xp, wp = ans.feature_parameters(c0), ans.weight_parameters(c0)
        circ_w = c0.assign_parameters(dict(zip(wp, weights)))

        targets = [circ_w.assign_parameters(dict(zip(xp, x))) for x in X]
        ideals = [float(np.real(Statevector.from_instruction(t).expectation_value(obs_op)))
                  for t in targets]

        def measured(bound, fold=1):
            cc = fold_global(bound.copy(), fold) if fold > 1 else bound.copy()
            cc.measure_all()
            return tpile(cc, layout)

        n2q = sum(1 for i in measured(targets[0]).data if i.operation.name in ("cz", "cx"))
        print(f"\n=== {placement}:{pattern}  cz={n2q} ===")

        # ---- pilot Neymana: sigma_i na pojedynczy pomiar dla każdej skali ---- #
        sigmas = None
        if neyman:
            pilot = run([measured(t, f) for t in targets for f in SCALES], args.pilot_shots,
                        arm="zne_pilot",
                        metas=[{"point": spec, "role": "pilot", "target": i, "scale": f}
                               for i in range(len(targets)) for f in SCALES])
            ns_ = len(SCALES)
            sigmas = [float(np.sqrt(np.mean([per_shot_variance_from_counts(
                pilot[i * ns_ + k], coeffs, n) for i in range(len(targets))])))
                for k in range(ns_)]
            kappa = kappa_opt(SCALES, sigmas)
            print(f"  pilot: sigma_i = {[round(x, 4) for x in sigmas]} -> "
                  f"kappa_opt = {kappa:.3f} | podział "
                  f"{neyman_allocation(1000, SCALES, sigmas)} na 1000 pomiarów")
        else:
            kappa = kappa_uniform(SCALES)
        print(f"{'S':>6} {'B_rms':>9} {'V(cnt)':>9} {'V(rep)':>9} "
              f"{'MSE raw':>10} {'MSE zne':>10} {'Delta MSE':>11} {'wynik':>10}")

        for S in args.budgets:
            if (placement, pattern, S) in done:
                print(f"  [pomijam] {placement}:{pattern} S={S} — już w {args.out}")
                continue
            # ZRÓWNANY budżet całkowity: suma po skalach to S (Neyman) albo S//|Lambda| na skalę
            alloc = (neyman_allocation(S, SCALES, sigmas) if neyman
                     else uniform_allocation(S, SCALES))
            s_zne = alloc[0]
            # Wszystkie powtórzenia w JEDNYM zgłoszeniu (run_circuits dzieli na paczki <=100).
            # Redukuje liczbę zadań ~5-krotnie, a metodologicznie jest właściwsze: powtórzenia
            # wykonane blisko siebie w czasie dają rozrzut odzwierciedlający szum próbkowania,
            # a nie dryf kalibracji --- a to właśnie wariancję próbkowania chcemy tu zmierzyć.
            ns = len(SCALES)
            E = len(targets)
            raw_counts = run([measured(t) for _ in range(args.reps) for t in targets], S,
                             metas=[{"point": spec, "budget_S": S, "role": "raw", "rep": r,
                                     "target": i, "scale": 1}
                                    for r in range(args.reps) for i in range(E)])
            rv = [float(np.dot(coeffs, perqubit_z_from_counts(ct, n))) for ct in raw_counts]
            raw_vals = np.array(rv).reshape(args.reps, E)
            # V wprost z rozkładu zliczeń (wszystkie S pomiarów), nie z rozrzutu powtórzeń
            V_counts = float(np.mean([per_shot_variance_from_counts(ct, coeffs, n)
                                      for ct in raw_counts]))

            if len(set(alloc)) == 1:
                zne_counts = run([measured(t, f) for _ in range(args.reps)
                                  for t in targets for f in SCALES], alloc[0],
                                 metas=[{"point": spec, "budget_S": S, "role": "zne",
                                         "rep": r, "target": i, "scale": f}
                                        for r in range(args.reps) for i in range(E)
                                        for f in SCALES])
            else:
                # osobne zgłoszenie na skalę (różne liczby pomiarów), potem ta sama kolejność
                by_scale = [run([measured(t, f) for _ in range(args.reps) for t in targets], nk,
                                metas=[{"point": spec, "budget_S": S, "role": "zne",
                                        "rep": r, "target": i, "scale": f}
                                       for r in range(args.reps) for i in range(E)])
                            for f, nk in zip(SCALES, alloc)]
                zne_counts = [by_scale[k][r * E + i] for r in range(args.reps)
                              for i in range(E) for k in range(ns)]
            zv = [float(np.dot(coeffs, perqubit_z_from_counts(ct, n))) for ct in zne_counts]
            bound = float(np.sum(np.abs(coeffs)))
            ests = [[extrapolate_flagged(SCALES, zv[(r * E + i) * ns:(r * E + i + 1) * ns],
                                         "richardson", bound=bound,
                                         legacy_clamp=args.legacy_clamp)
                     for i in range(E)] for r in range(args.reps)]
            zne_vals = np.array([[e.value for e in row] for row in ests])
            n_unphys = sum(e.unphysical for row in ests for e in row)
            n_fallback = sum(e.fallback_used for row in ests for e in row)
            sig_run = [float(np.sqrt(np.mean([per_shot_variance_from_counts(
                zne_counts[j * ns + k], coeffs, n) for j in range(args.reps * E)])))
                for k in range(ns)]

            ideal = np.array(ideals)
            # Obciążenie liczymy jako RMS (a nie średnią modułów), bo tylko wtedy zachodzi
            # tożsamość MSE = B^2 + V/S, na której opiera się granica. Średnia modułów zaniżałaby
            # B (nierówność Jensena) i psuła wewnętrzną spójność porównania.
            bias_rms = float(np.sqrt(np.mean((raw_vals.mean(axis=0) - ideal) ** 2)))
            var_raw = float(np.mean(raw_vals.var(axis=0, ddof=1))) if args.reps > 1 else float("nan")
            V_reps = var_raw * S if args.reps > 1 else float("nan")  # kontrola krzyżowa
            mse_raw = float(np.mean((raw_vals - ideal) ** 2))
            mse_zne = float(np.mean((zne_vals - ideal) ** 2))
            meas = "pomoze" if mse_zne < mse_raw else "zaszkodzi"
            print(f"{S:>6} {bias_rms:>9.4f} {V_counts:>9.4f} {V_reps:>9.4f} "
                  f"{mse_raw:>10.5f} {mse_zne:>10.5f} {mse_zne-mse_raw:>+11.5f} {meas:>10}")
            rows.append({"placement": placement, "pattern": pattern, "transpiled_cz": n2q,
                         "budget_S": S, "shots_per_scale": s_zne, "reps": args.reps,
                         "bias_rms": round(bias_rms, 5), "V_counts": round(V_counts, 5),
                         "V_reps": round(V_reps, 5),
                         "mse_raw": round(mse_raw, 6), "mse_zne": round(mse_zne, 6),
                         "delta_mse": round(mse_zne - mse_raw, 6), "measured": meas,
                         "allocation": args.allocation,
                         "shots_alloc": "/".join(map(str, alloc)),
                         "kappa_pred": round(kappa, 4),
                         **{f"sigma_lam{f}": round(x, 5) for f, x in zip(SCALES, sig_run)},
                         "n_unphysical": n_unphys, "n_fallback": n_fallback,
                         "legacy_clamp": args.legacy_clamp})
            # zapis po KAŻDYM budżecie — zerwanie połączenia nie kasuje opłaconych pomiarów
            with open(args.out, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
                w.writeheader(); w.writerows(rows)

    # ---- ocena po PULI: V i B są niezależne od budżetu, więc estymujemy je łącznie ---- #
    print("\n" + "=" * 78)
    print("OCENA PO PULI (V i B nie zależą od S, więc pojedyncze oszacowania per-budżet są zaszumione)")
    for spec in args.points:
        placement, pattern = spec.split(":")
        sel = [r for r in rows if r["placement"] == placement and r["pattern"] == pattern]
        if not sel:
            continue
        V_pool = float(np.mean([r["V_counts"] for r in sel]))
        kappa = float(sel[-1]["kappa_pred"]) if sel[-1].get("kappa_pred") not in (None, "") \
            else kappa_uniform(SCALES)
        B_pool = float(np.mean([r["bias_rms"] for r in sel]))
        S_star = kappa * V_pool / B_pool ** 2

        # --- ESTYMATOR CIĄGŁY: Delta MSE * S = kappa*V - B^2 * S  (funkcja liniowa S) --- #
        # Wyraz wolny daje kappa*V, nachylenie -B^2. Ponieważ V mierzymy niezależnie z rozkładu
        # zliczeń, otrzymujemy kappa jako LICZBĘ Z NIEPEWNOŚCIĄ, zamiast binarnego werdyktu
        # "w którym przedziale siatki wypadło przejście" (test o znikomej mocy przy siatce x2).
        Sx = np.array([r["budget_S"] for r in sel], float)
        Y = np.array([r["delta_mse"] for r in sel], float) * Sx
        kap_meas = kap_err = b_fit = float("nan")
        if len(Sx) >= 3:
            A = np.vstack([np.ones_like(Sx), Sx]).T
            coef, res, *_ = np.linalg.lstsq(A, Y, rcond=None)
            a_fit, b_fit = float(coef[0]), float(coef[1])
            dof = len(Sx) - 2
            if dof > 0:
                resid = Y - A @ coef
                s2 = float(resid @ resid) / dof
                cov = s2 * np.linalg.inv(A.T @ A)
                a_err = float(np.sqrt(cov[0, 0]))
                kap_meas, kap_err = a_fit / V_pool, a_err / V_pool

        print(f"\n  {placement}:{pattern}")
        print(f"    V (z rozkładu zliczeń) = {V_pool:.4f}    B_rms = {B_pool:.4f}")
        print(f"    S* = kappa*V/B^2       = {S_star:.0f}")
        harm = [r["budget_S"] for r in sel if r["measured"] == "zaszkodzi"]
        helps = [r["budget_S"] for r in sel if r["measured"] == "pomoze"]
        lo = max(harm) if harm else None
        hi = min([s for s in helps if lo is None or s > lo], default=None)
        if lo is not None and hi is not None:
            print(f"    przejście zaobserwowane w przedziale ({lo}, {hi}]")
        if np.isfinite(kap_meas):
            print(f"    --> kappa ZMIERZONE = {kap_meas:.2f} +/- {kap_err:.2f}   "
                  f"(przewidziane: {kappa:.2f})")
            z = abs(kap_meas - kappa) / kap_err if kap_err > 0 else float("inf")
            print(f"        odchylenie {z:.1f} sigma -> "
                  f"{'ZGODNE z teorią' if z < 2 else 'NIEZGODNE'}")
            if np.isfinite(b_fit) and b_fit < 0:
                # Richardson z 3 wezlow usuwa tylko dwa pierwsze rzedy, wiec ZNE zachowuje
                # obciazenie resztkowe: MSE_zne = B_zne^2 + (sum c^2)|L| V/S. Nachylenie dopasowania
                # to zatem -(B^2 - B_zne^2), czyli USUNIETA czesc obciazenia --- a nie samo B.
                # Wyraz wolny pozostaje kappa*V, wiec estymator kappa jest tym nienaruszony.
                removed = np.sqrt(-b_fit)
                resid2 = B_pool ** 2 + b_fit
                print(f"        usunięte obciążenie sqrt(B^2-B_zne^2) = {removed:.4f} "
                      f"(B zmierzone bezpośrednio: {B_pool:.4f})")
                if resid2 > 0:
                    print(f"        -> obciążenie RESZTKOWE ZNE: B_zne = {np.sqrt(resid2):.4f} "
                          f"({100*np.sqrt(resid2)/B_pool:.0f}% obciążenia surowego)")
                    print(f"        -> skorygowane S* = kappa*V/(B^2-B_zne^2) = "
                          f"{kappa*V_pool/(-b_fit):.0f}")
        for r in sel:
            r["S_star_pooled"] = round(S_star, 1)
            r["kappa_meas"] = round(kap_meas, 3) if np.isfinite(kap_meas) else ""
            r["kappa_err"] = round(kap_err, 3) if np.isfinite(kap_err) else ""

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    print(f"\nzapisano {args.out}")
    if RECORDER is not None:
        RECORDER.close()
        print(f"[provenance] manifest + counts.jsonl -> {RECORDER.dir}")
    print(f"ODCZYT: falsyfikowalna jest STAŁA kappa ({args.allocation}) --- przejście ma wypaść przy")
    print("S* = kappa*V/B^2 z V i B zmierzonymi w tym samym przebiegu, bez dopasowywania.")


if __name__ == "__main__":
    main()
