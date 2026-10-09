"""Trenuj ansatz `star` przy rosnącej liczbie warstw --- oś GŁĘBOKOŚCI bez narzutu routingu.

DLACZEGO. Praca twierdzi, że to *narzut routingu* wstrzykuje błąd koherentny łamiący liniowość
CDR. Ale narzut routingu to zarazem po prostu *więcej bramek dwukubitowych*. Bez rozdzielenia tych
dwóch rzeczy teza jest podatna na zarzut, że mierzymy wyłącznie liczbę bramek.

Na ODRZE (gwiazda 5q) da się je rozdzielić, bo wzorzec `star` jest natywny --- transpilator nie
wstawia ani jednej bramki SWAP. Zwiększając liczbę warstw uzyskujemy drugą oś kosztu przy ZEROWYM
routingu i możemy porównać punkty o tej samej liczbie CZ:

    liczba CZ | z routingiem (L=3)      | bez routingu (star)
    ----------+-------------------------+---------------------
       24--27 | linear      (56% SWAP)  | L=6   (0% SWAP)
           36 | circular    (58% SWAP)  | L=9   (0% SWAP)
       52--54 | all_to_all  (44% SWAP)  | L=13  (0% SWAP)

Ramię z routingiem jest już zmierzone (`odra_full_100pt.csv`: r^2 = 0,809 / 0,792 / 0,598 przy
27 / 36 / 54 CZ). Ten skrypt dostarcza wag dla ramienia bez routingu; pomiar wykonuje potem
`run_odra_cdr.py --layers L`.

ODCZYT WYNIKU. Jeśli r^2 przy zrównanej liczbie CZ jest wyraźnie NIŻSZE po stronie routingu, to
routing wnosi więcej koherencji na bramkę niż samo powtarzanie warstw --- teza pracy jest
specyficzna. Jeśli oba ramiona wypadną tak samo, uczciwym wnioskiem jest, że decyduje liczba bramek
dwukubitowych, a routing jest jedynie jednym ze sposobów jej podniesienia.

ZASTRZEŻENIE, które trzeba raportować: oś głębokości dodaje także bramki jednokubitowe i wydłuża
obwód w czasie, więc niesie własną dekoherencję. Skrypt zapisuje dlatego również głębokość i czas
trwania obwodu po transpilacji, żeby porównanie dało się zrobić zarówno przy zrównanej liczbie CZ,
jak i przy zrównanym czasie.

    python train_star_depth.py                 # L = 6, 9, 13
    python train_star_depth.py --layers 6 9    # podzbiór
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np
import torch
from qiskit import transpile
from qiskit_machine_learning.gradients import ParamShiftEstimatorGradient
from qiskit_machine_learning.neural_networks import EstimatorQNN
from qiskit.primitives import StatevectorEstimator
from qml_benchmarks.data import generate_two_curves
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

from ansatz import HardwareEfficientAnsatz
from train_patterns import (
    DEGREE, N_FEATURES, N_QUBITS, NOISE, READOUT, SEED, acc, observable, train,
)
from train_hard import OFFSET, N_SAMPLES, TEST_SIZE
from noisy_sim import IQM_BASIS_GATES, star_coupling_map

OUT = pathlib.Path("trained_models_hard")


def build_qnn_depth(n_layers: int):
    """Jak train_patterns.build_qnn, ale z jawną liczbą warstw i wzorcem `star`."""
    vqc = HardwareEfficientAnsatz(N_QUBITS, n_layers, num_features=N_FEATURES,
                                  entanglement="star")
    circ = vqc.build()
    est = StatevectorEstimator()
    qnn = EstimatorQNN(
        circuit=circ, observables=observable(),
        input_params=vqc.feature_parameters(circ),
        weight_params=vqc.weight_parameters(circ),
        estimator=est, gradient=ParamShiftEstimatorGradient(est),
    )
    return vqc, qnn


def native_cost(circ) -> tuple[int, int]:
    """(liczba CZ, głębokość) po transpilacji na natywną bazę gwiazdy ODRY."""
    t = transpile(circ, basis_gates=IQM_BASIS_GATES,
                  coupling_map=star_coupling_map(N_QUBITS), optimization_level=1,
                  seed_transpiler=42)
    return sum(1 for i in t.data if i.operation.name == "cz"), t.depth()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--layers", type=int, nargs="+", default=[6, 9, 13])
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    X, y = generate_two_curves(N_SAMPLES, N_FEATURES, degree=DEGREE, offset=OFFSET, noise=NOISE)
    y = y.astype(float)
    X = MinMaxScaler((-np.pi, np.pi)).fit_transform(X)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=TEST_SIZE, random_state=SEED, stratify=y)
    Xtr_t = torch.tensor(Xtr, dtype=torch.float32)
    ytr_t = torch.tensor(ytr, dtype=torch.float32).view(-1, 1)

    print("OŚ GŁĘBOKOŚCI (wzorzec star = zero routingu). Ten sam zbiór, ten sam podział, "
          "to samo ziarno\nco kampania główna, więc jedyną zmienną jest liczba warstw.\n")
    for L in args.layers:
        vqc, qnn = build_qnn_depth(L)
        circ = vqc.build()
        cz, depth = native_cost(circ)
        print(f"  L={L:<3} params={vqc.num_weights:<4} CZ={cz:<3} głębokość={depth:<4} "
              f"-- trenuję (parameter-shift, to potrwa)...", flush=True)
        w, _ = train(qnn, vqc.num_weights, Xtr_t, ytr_t)
        tr, te = acc(qnn, w, Xtr, ytr), acc(qnn, w, Xte, yte)

        tag = f"two_curves_d{N_FEATURES}_q{N_QUBITS}_deg{DEGREE}_star_{READOUT}_L{L}"
        np.save(OUT / f"{tag}_weights.npy", w)
        (OUT / f"{tag}.json").write_text(json.dumps({
            "dataset": "two_curves", "n_samples": N_SAMPLES, "n_features": N_FEATURES,
            "degree": DEGREE, "offset": OFFSET, "noise": NOISE,
            "feature_range": [-float(np.pi), float(np.pi)],
            "n_qubits": N_QUBITS, "n_layers": L, "entanglement": "star",
            "entangling_gate": "cx", "readout": READOUT,
            "observable": "(1/n) sum_i Z_i (mean-Z)",
            "num_weights": int(vqc.num_weights),
            "transpiled_cz_odra": cz, "transpiled_depth_odra": depth,
            "routing_overhead_cz": 0,
            "train_acc": tr, "test_acc": te, "seed": SEED,
            "weights_file": f"{tag}_weights.npy",
            "note": "OŚ GŁĘBOKOŚCI: kontrola dla tezy o narzucie routingu. Zero bramek SWAP.",
        }, indent=2))
        print(f"        train {tr:.3f}  test {te:.3f}  -> {tag}_weights.npy")

    print("\nNASTĘPNY KROK (ODRA, darmowo):")
    for L in args.layers:
        print(f"  python run_odra_cdr.py --submit --patterns star --layers {L} "
              f"--eval-points 100 --out odra_depth_L{L}.csv")
    print("\nPorównanie: odra_depth_L*.csv (zero routingu) wobec odra_full_100pt.csv "
          "(ten sam CZ, ciężki routing).")


if __name__ == "__main__":
    main()
