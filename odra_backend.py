"""Adapter ODRA (IQM Spark, `iqm-client`) o interfejsie zgodnym z `iqm_resonance`.

DLACZEGO. Runnery kampanijne (`run_garnet_twirl.py`, `zne_shot_boundary.py`) są
provider-agnostyczne: pobierają z adaptera trzy rzeczy --- ``get_backend``,
``transpile_for_backend`` i ``run_circuits`` --- i nic więcej o sprzęcie nie wiedzą. Adapter
Resonance obsługuje Garneta i Emeralda; ODRA idzie inną ścieżką (`iqm-client`, natywny format
IQM Circuit), dlatego dostaje własny adapter o TEJ SAMEJ sygnaturze. Runner wybiera adapter
po ``--device``; reszta kodu pozostaje bez zmian.

Znaczenie praktyczne: ODRA jest jedynym urządzeniem w tym projekcie, które jest jednocześnie
DARMOWE i KLASYCZNIE SYMULOWALNE (5 kubitów). Dzięki temu cały rygorystyczny protokół ---
kontrola zrównana na liczbie pomiarów, poziom zerowy z symulacji, wiele okien kalibracyjnych ---
da się na niej wykonać bez zużywania kredytów, a poziom zerowy liczy się na TEJ SAMEJ mapie
sprzężeń, więc liczby CZ zgadzają się dokładnie ze sprzętem (czego nie dało się osiągnąć na
Garnecie, gdzie kontrolę policzono przy 33/87/90 CZ, a sprzęt mierzono przy 12/57/96).

KONWENCJA ODCZYTU --- najważniejszy szczegół tego pliku. Runnery liczą ⟨Z_q⟩ funkcją
``perqubit_z_from_counts``, która zakłada konwencję Qiskita: w łańcuchu bitów znak na pozycji
``n-1-q`` należy do kubitu logicznego ``q``. Histogram IQM ma konwencję odwrotną i indeksowaną
DRUTEM FIZYCZNYM: znak na pozycji ``j`` należy do ``j``-tego kubitu w loci pomiaru. Co więcej
transpilator permutuje kubity, więc drut ``j`` nie musi trzymać kubitu logicznego ``j``. Adapter
wykonuje więc oba przeliczenia (odwrócenie kolejności + permutacja układu końcowego) i zwraca
zliczenia w konwencji Qiskita, indeksowane LOGICZNIE. Bez tego odczyt cichutko się rozjeżdża na
każdym wzorcu poza ``star`` --- dla obserwabli o równych wagach (średnie Z) efekt jest niewidoczny,
ale dla odczytu jednokubitowego daje po prostu zły kubit.

    export IQM_SERVER_URL="https://odra5.e-science.pl/"
    export IQM_TOKEN="<token>"

Samotest (bez sprzętu, bez kredytów):
    python odra_backend.py
"""
from __future__ import annotations

import os

from qiskit import QuantumCircuit, transpile

from noisy_sim import logical_final_wires
from run_hardware import PHYS, counts_of, qiskit_to_iqm, submit_batch, fetch_counts
from topology import star_coupling_map
from zne_dryrun import IQM_BASIS_GATES

# ODRA przyjmuje wsady; 100 obwodów na zgłoszenie trzyma je w rozmiarze, który serwer przyjmuje
# bez kolejkowania w nieskończoność (ta sama wartość co limit Resonance, dla spójności logów).
MAX_CIRCUITS_PER_JOB = 100


class OdraBackend:
    """Minimalny odpowiednik obiektu backendu: tylko to, czego runnery faktycznie używają."""

    def __init__(self, client, n_qubits: int = 5):
        self.client = client
        self.num_qubits = n_qubits
        self.name = "odra"
        self.coupling_map = star_coupling_map(n_qubits)

    def __repr__(self) -> str:  # pragma: no cover
        return f"OdraBackend(n={self.num_qubits}, hub={PHYS[0]})"


def get_backend(device: str = "odra", url: str | None = None, token: str | None = None):
    """Zwróć uchwyt do ODRY. ``token`` czytany jest przez iqm-client z ``IQM_TOKEN``."""
    if device != "odra":
        raise ValueError(f"ten adapter obsługuje wyłącznie 'odra', podano {device!r}; "
                         "dla Garneta/Emeralda użyj iqm_resonance.get_backend")
    url = url or os.environ.get("IQM_SERVER_URL", "")
    if not url:
        raise RuntimeError("ustaw IQM_SERVER_URL (np. https://odra5.e-science.pl/) oraz IQM_TOKEN")
    from iqm.iqm_client import IQMClient
    return OdraBackend(IQMClient(url.rstrip("/")))


def backend_coupling_map(backend) -> list[list[int]]:
    return [list(e) for e in backend.coupling_map]


def transpile_for_backend(circuit: QuantumCircuit, backend, initial_layout=None,
                         seed_transpiler: int = 42) -> QuantumCircuit:
    """Transpiluj do natywnej bazy {r, cz} na mapie gwiazdy ODRY.

    Odpowiednik ``iqm_resonance.transpile_for_backend``. Na ODRZE obwód logiczny ma tyle kubitów,
    ile urządzenie, więc ``initial_layout`` jest tożsamościowe i służy tylko zgodności sygnatury.
    """
    return transpile(circuit, basis_gates=IQM_BASIS_GATES,
                     coupling_map=star_coupling_map(backend.num_qubits),
                     initial_layout=initial_layout, optimization_level=1,
                     seed_transpiler=seed_transpiler)


def iqm_counts_to_qiskit(counts: dict, n: int, wire_of_logical: list[int]) -> dict[str, int]:
    """Przelicz histogram IQM (bit ``j`` = drut ``j``) na konwencję Qiskita indeksowaną logicznie.

    ``wire_of_logical[q]`` to drut fizyczny, na którym po transpilacji siedzi kubit logiczny ``q``
    (z ``logical_final_wires``). Wynik nadaje się do ``perqubit_z_from_counts``.
    """
    out: dict[str, int] = {}
    for bits, c in counts.items():
        s = str(bits).replace(" ", "")
        chars = ["0"] * n
        for q in range(n):
            chars[n - 1 - q] = s[wire_of_logical[q]]
        key = "".join(chars)
        out[key] = out.get(key, 0) + int(c)
    return out


def run_circuits(backend, circuits, shots: int, max_per_job: int = MAX_CIRCUITS_PER_JOB,
                 dd: bool = False):
    """Wykonaj listę natywnych obwodów na ODRZE; zwróć zliczenia w kolejności zgłoszenia.

    Zgłoszenie następuje RAZ na porcję, a ponawiane jest wyłącznie pobieranie wyniku (po
    ``job_id``), więc awaria sieci nigdy nie powoduje powtórnego wykonania obwodów.
    """
    if not circuits:
        return []
    n = circuits[0].num_qubits
    wires = [logical_final_wires(c, n) for c in circuits]
    out: list[dict[str, int]] = []
    for i in range(0, len(circuits), max_per_job):
        chunk = circuits[i:i + max_per_job]
        job = submit_batch(backend.client, [qiskit_to_iqm(c) for c in chunk], shots, dd_on=dd)
        raw, job_id = fetch_counts(backend.client, job)
        print(f"    [odra] zadanie {job_id} | {len(raw)} obwodów "
              f"({i + len(chunk)}/{len(circuits)})")
        for k, cts in enumerate(raw):
            out.append(iqm_counts_to_qiskit(cts, n, wires[i + k]))
    return out


# --------------------------------------------------------------------------- #
# Samotest konwencji odczytu --- uruchamiany bez sprzętu                       #
# --------------------------------------------------------------------------- #

def _selftest() -> None:
    import numpy as np
    from noisy_sim import perqubit_z_from_counts
    from run_hardware import perqubit_z_iqm

    n = 5
    print("samotest konwersji histogramu IQM -> Qiskit\n")

    # 1) bez permutacji: wynik musi zgadzać się z perqubit_z_iqm bit w bit
    iqm = {"10000": 700, "00001": 300}          # drut 0 wzbudzony w 70% / drut 4 w 30%
    ident = list(range(n))
    q = iqm_counts_to_qiskit(iqm, n, ident)
    a = perqubit_z_iqm(iqm, n)
    b = perqubit_z_from_counts(q, n)
    print(f"  IQM  {iqm}\n  Qiskit {q}")
    print(f"  <Z> przez perqubit_z_iqm       : {np.round(a, 4)}")
    print(f"  <Z> przez perqubit_z_from_counts: {np.round(b, 4)}")
    assert np.allclose(a, b), "konwersja bez permutacji niepoprawna"
    print("  OK -- tożsamość bez permutacji\n")

    # 2) z permutacją: logiczny 0 siedzi na drucie 3
    wires = [3, 1, 2, 0, 4]
    iqm2 = {"00010": 1000}                       # wzbudzony drut 3
    q2 = iqm_counts_to_qiskit(iqm2, n, wires)
    z2 = perqubit_z_from_counts(q2, n)
    print(f"  drut 3 wzbudzony, logiczny 0 -> drut 3")
    print(f"  <Z> = {np.round(z2, 4)}  (oczekiwane: -1 na kubicie logicznym 0)")
    assert z2[0] == -1.0 and all(z2[k] == 1.0 for k in (1, 2, 3, 4)), "permutacja niepoprawna"
    print("  OK -- permutacja układu końcowego uwzględniona\n")

    # 3) transpilacja rzeczywistego obwodu: sprawdź, że layout jest odczytywany
    qc = QuantumCircuit(n)
    for a_, b_ in [(1, 2), (2, 3), (3, 4), (4, 1)]:
        qc.cx(a_, b_)
    qc.measure_all()
    t = transpile_for_backend(qc, OdraBackend(client=None, n_qubits=n))
    cz = sum(1 for i in t.data if i.operation.name == "cz")
    print(f"  obwód pierścieniowy -> {cz} CZ na gwieździe, "
          f"logical_final_wires = {logical_final_wires(t, n)}")
    print("\nwszystkie testy przeszły")


if __name__ == "__main__":
    _selftest()
