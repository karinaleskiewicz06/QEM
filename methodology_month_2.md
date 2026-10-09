# Month 2 — Methodology & Pipeline (control document)

**Purpose.** This is the spec you review *before/while* the code is written, so you stay in
control. Every component below is a contract: what it does, which files, the function
signatures, the scientific protocol, the exact commands (sim + hardware), the output schema,
and how it maps to the report. Nothing here runs itself — you run everything.

**Main goal:** real-hardware results on ODRA (star) + Garnet/Emerald (lattice). Simulation is
the *control* and the dry-run gate, never the headline.

---

## 0. Global conventions (inherited from Month 1 unless overridden)

| Thing | Value | Where to change |
|---|---|---|
| Shots | 4096 | `--shots` flag on every runner |
| ZNE noise scales | {1, 3, 5} (unitary folding) | `zne_dryrun.py` / runners |
| Repetitions (error bands) | R = 3 | `--reps` |
| Observable | mean-Z (two_curves) / single-Z on readout wire (Banknote) | frozen model config |
| Primary metric | mean \|⟨O⟩_noisy − ⟨O⟩_ideal\| vs **frozen** noiseless ideal | `freeze_reference.py` |
| Secondary metrics | accuracy (sign decision), macro-F1, mirror fidelity | — |
| Seed | 42 (training + transpiler) | `seed=` / `seed_transpiler=` |
| Cost x-axis | transpiled CZ count (+ SWAP, topo_dist, depth) | `routing_sweep.py` |
| Safety | every hardware script is **dry-run by default**; needs `--submit` | runner argparse |
| Resume | append-only CSV + `--resume` | runner |

**Credentials / environment**
- **ODRA** (Month 1): `iqm-client` + `IQM_SERVER_URL`, `IQM_TOKEN`.
- **Garnet / Emerald** (this month): **IQM Resonance via `qiskit-iqm`**. Env:
  `IQM_RESONANCE_URL=https://resonance.iqm.tech` (BASE url; device chosen via `quantum_computer=`)
  + `IQM_TOKEN`. ⚠️ The old CoCoS host `cocos.resonance.meetiqm.com` / `resonance.meetiqm.com` is
  **DEPRECATED and no longer resolves** (DNS failure) — use `resonance.iqm.tech`; a token for the
  old API may need reissuing. ⚠️ `qiskit-iqm` must be installed
  in the run environment (it failed on py3.13 in Month 1 — resolve there, e.g. a py3.11 venv).
- Placements on real devices are **hand-given** by you: fill `topology.HARDWARE_PLACEMENTS`
  with real physical-qubit lists after inspecting each backend; hardware transpile uses the
  **backend's live coupling map**, not the idealized grid.

**Pipeline shape (every method reuses this backbone):**
```
frozen model (weights, ideal ⟨O⟩)  ─┐
routing ladder (device, placement) ─┼─►  build circuits ─► [mitigation/QEC] ─►
noise-calibrated sim  OR  real QPU ─┘        execute (shots)     post-process
                                            ─► ⟨O⟩, error, accuracy, fidelity, cost ─► CSV ─► figures
```

---

## 1. Lattice sim-execution (`execute_expectation` + `initial_layout`)

**Goal.** Let the existing pipeline run a 5-qubit VQC on a 20/54-qubit device *in simulation*
by placing it with an explicit layout (optimal/adverse) and reading out the right wires.

**Files.** `noisy_sim.py` (edit), `test_noisy_sim_layout.py` (new).

**Contract.**
- `execute_expectation(..., initial_layout: list[int] | None = None)` — when the device is
  larger than the circuit, transpile onto `cal.coupling_map` with `initial_layout`, run on the
  device-sized sim, and read ⟨O⟩ from the logical qubits' **final** wires.
- New helper `logical_final_wires(transpiled, n_logical) -> list[int]` — derive each logical
  qubit's physical measurement wire from `transpiled.layout.final_index_layout()` (generalises
  the Month-1 Banknote readout-wire fix).
- New helper `perqubit_z_on_wires(counts, wires, device_width) -> np.ndarray`.

**Protocol.** Verify that running a 5-qubit circuit *embedded* on a 5-qubit device (identity
layout) reproduces the same-size path exactly; then that a 5-on-20 run returns finite ⟨O⟩ and
that adverse placement yields larger ⟨O⟩-error than optimal (routing costs quality).

**Command (sim).**
```bash
python zne_dryrun.py --device garnet --placement optimal --calibration <lattice.json>
```

**Output.** Same CSV schema as Month-1 `zne_dryrun_results.csv`, plus `device`, `placement`.

**Report mapping.** Enables the *simulated* optimal-vs-adverse ⟨O⟩-error curves before any QPU
time (W2/W4 sim control).

**Caveats.** Idle scheduling now runs over the full device width; only the placed qubits carry
signal. This path is **sim-only**; hardware readout wires come from the backend layout (§7).

---

## 2. Placeholder lattice calibration (`synthesize_lattice_calibration`)

**Goal.** A stand-in `DeviceCalibration` for Garnet/Emerald so §1/§3/§4 sim runs work *before*
real lattice calibration exists.

**Files.** `noisy_sim.py` (add function).

**Contract.**
- `synthesize_lattice_calibration(device, *, seed=0, **overrides) -> DeviceCalibration` —
  Spark-class scalar error rates (T1 40 µs, T2\* 15 µs, p_1q 1e-3, p_2q 1e-2, p_ro 3e-2)
  broadcast onto the device, with the real grid coupling map; optional per-qubit jitter by
  `seed`; any field overridable.

**Protocol.** Clearly labelled PLACEHOLDER (like the ODRA default). Replaced by real
calibration (§7) before any quantitative lattice claim.

**Command.** Used internally by runners via `--device garnet` when no `--calibration` given.

**Report mapping.** None directly — infrastructure for sim controls.

---

## 3. Clifford Data Regression (CDR) — QEM method #2

**Goal.** A learning-based mitigator that does *not* amplify noise, compared head-to-head with
ZNE along the routing-cost axis (the report's §1 introduction already motivates it).

**Files.** `cdr.py` (new), `run_cdr.py` (new, mirrors `zne_dryrun.py`/`run_hardware.py`),
`test_cdr.py` (new).

**Contract (`cdr.py`).**
- `near_clifford_training_circuits(circuit, n_train=100, n_nonclifford=0, seed=42) -> list` —
  copy the target's structure/routing; snap each rotation angle to the nearest multiple of
  π/2 (optionally leave `n_nonclifford` gates free for a low-stabilizer-rank variant).
- `clifford_ideal_expval(training_circuit, observable) -> float` — exact ⟨O⟩ via
  `qiskit.quantum_info.Clifford` / `StabilizerState` (Gottesman–Knill; no statevector cost).
- `fit_cdr(noisy_vals, ideal_vals) -> (a, b, r2)` — least-squares `ideal ≈ a·noisy + b`.
- `apply_cdr(noisy_target, a, b) -> float`.

**Protocol.** Per ladder rung: build `n_train` near-Clifford circuits → run noisy (sim or QPU)
→ collect (noisy, ideal) pairs → fit (a,b) → apply to the target's raw ⟨O⟩. Run training +
target in the **same job/window** (drift is CDR's Achilles heel). Score on ⟨O⟩-error, accuracy,
and the shots-to-target currency (§5); CDR cost = `n_train × shots` + the target run.

**Commands.**
```bash
python run_cdr.py --device odra   --dry-run                 # validate
python run_cdr.py --device odra   --submit --n-train 100    # ODRA full ladder
python run_cdr.py --device garnet --submit --n-train 100 --placement optimal
```

**Output** `cdr_results.csv`: device, placement, pattern, transpiled_cz, err_raw, err_cdr,
acc_raw, acc_cdr, a, b, r2, n_train, shots, effective_shots.

**Report mapping.** The ZNE-vs-CDR resilience comparison (which breaks first with routing).

**Caveats.** Fully-Clifford training set first (exact, simplest); `n_nonclifford>0` needs a
near-Clifford simulator and is a later refinement. Linear fit first; polynomial optional.

---

## 4. `[[4,2,2]]` error detection — QEC-lite (logical-ish) layer

**Goal.** A near-term "logical" arm: detect (not correct) single-qubit errors and post-select,
comparing encoded vs physical along the routing-cost axis and at optimal vs adverse placement.

**⚠️ Pending your choice** of how it runs the VQC (Options A/B/C/D in chat). Files/contract
below are common; the runner specialises to the chosen option.

**Files.** `qec422.py` (new: encoder, logical ops, parity post-selection),
`run_qec422.py` (new), `test_qec422.py` (new).

**Contract (`qec422.py`).**
- `encode_422() -> QuantumCircuit` — prepare a `[[4,2,2]]` logical basis state on 4 data qubits.
- `logical_ops()` — the available transversal logical gates (Paulis, CNOT₁₂, H⊗H).
- `postselect_parity(counts) -> (kept_counts, acceptance_rate)` — compute XXXX/ZZZZ parity from
  the destructive 4-qubit readout; drop flagged shots (ancilla-free, Vuillot-style).
- Option-specific builder (A: near-Clifford surrogate; C: detection-wrapped mirror; etc.).

**Protocol.** Three arms — bare (physical) / encoded-optimal / encoded-adverse — at matched
logical operation. Metrics: ⟨O⟩-error or fidelity **plus acceptance rate** (kept/raw shots) as
the cost → shots-to-target. A clean negative (overhead > benefit) is a valid result.

**Commands.**
```bash
python run_qec422.py --device garnet --placement optimal --dry-run
python run_qec422.py --device garnet --placement optimal --submit
python run_qec422.py --device garnet --placement adverse --submit
```

**Output** `qec422_results.csv`: device, placement, arm, cost, metric_raw, metric_detected,
acceptance_rate, effective_shots.

**Report mapping.** Encoded-vs-physical comparison (research question 2), fused with mapping.

**Caveats.** Prototype in sim first (can dry-run on ODRA using the hub as a weight-4 ancilla).
`Ry(x)` non-transversal → the chosen option defines exactly what "runs the VQC" means.

---

## 5. Shots-to-target — the common cost currency

**Goal.** Put ZNE, CDR, and `[[4,2,2]]` on one comparable cost axis.

**Files.** `shots_to_target.py` (new), used by §7 figures.

**Contract.**
- `shots_to_target(method, per_rung_result, target_tol) -> float` — effective QPU shots to
  reach a fixed ⟨O⟩-error (or accuracy) tolerance, folding each method's real overhead:
  - ZNE: shots × (#noise-scaled copies) × reps;
  - CDR: shots × (n_train + 1);
  - `[[4,2,2]]`: shots ÷ acceptance_rate (post-selection discards).

**Protocol.** One helper, applied uniformly so no method is compared at unequal cost.

**Report mapping.** The headline "which method pays, up to what 2q budget" figure axis.

---

## 6. Task-agnostic mirror benchmark (methodology strengthener)

**Goal.** Show the routing frontier is a *device* property, not a VQC artifact, using
classifier-independent random/Clifford mirror circuits at matched 2q cost.

**Files.** extend `mirror_fidelity_two_curves.py` **or** new `random_mirror_benchmark.py`.

**Contract.**
- `random_mirror_circuit(n, target_cz, seed) -> QuantumCircuit` — random (Clifford) `U` then
  `U†`, ideal output `|0…0⟩`, transpiled to a chosen 2q-cost.
- Run per device/placement; report survival fidelity `P(|0…0⟩)` vs transpiled CZ.

**Report mapping.** Generality panel next to the VQC mirror-fidelity results.

**Caveats.** Optional but recommended; reuses the mirror-fidelity machinery.

---

## 7. Hardware generalization (ODRA + Garnet/Emerald)

**Goal.** Run the real experiments. Two submit paths: ODRA (`iqm-client`, Month-1 code) and
Garnet/Emerald (**`qiskit-iqm` / IQM Resonance**).

**Files.** `run_hardware.py` (generalise), new `iqm_resonance.py` (Resonance adapter),
`collect_iqm_calibration.py` (or parameterise the ODRA collector),
`topology.py` (add `HARDWARE_PLACEMENTS`).

**Contract.**
- `topology.HARDWARE_PLACEMENTS[device][strategy] = [physical qubit indices]` — **you fill**
  these from the real devices; validated against the backend coupling at runtime.
- `iqm_resonance.submit(circuits, device, shots) -> counts` — qiskit-iqm `IQMProvider`
  targeting the Resonance endpoint; transpile against the **backend's real coupling map**;
  native-gate conversion via the backend's target.
- `run_hardware.py --device {odra|garnet|emerald} --placement {optimal|adverse}` — dispatches
  to the right submit path; `--dry-run` builds/validates locally and submits nothing.

**Protocol.** Smoke test (1 circuit, print raw counts, confirm bit order/readout wire) →
go/no-go (2 patterns, few points) → full ladder. `--max-circuits` guard as in Month 1.

**Commands.**
```bash
# ODRA (unchanged path)
python run_hardware.py --device odra --submit --full --dd-ablation
# Garnet / Emerald (Resonance)
export IQM_RESONANCE_URL="<garnet endpoint>"; export IQM_TOKEN="<resonance token>"
python run_hardware.py --device garnet --placement optimal --submit --smoke
python run_hardware.py --device garnet --placement optimal --submit --go-no-go
python run_hardware.py --device garnet --placement adverse --submit --go-no-go
```

**Output.** `hardware_results_<device>_<placement>.csv` (Month-1 schema + device/placement).

**Report mapping.** All real optimal-vs-adverse, CDR, and encoded-vs-physical hardware results.

**Caveats.** `qiskit-iqm` install (py version); real coupling ≠ idealized grid → placements are
validated against live connectivity; Tier B/C queue is the scheduling risk (full ladders on
ODRA, bracketing points on Garnet/Emerald).

---

## 8. Drift & threshold campaign + synthesis (W4 + W7)

**Goal.** Turn single runs into drift-aware bands and publication figures.

**Files.** extend `make_figures.py`; small `aggregate_windows.py` (mean ± inter-window std).

**Protocol.** Repeat the ODRA ladder over ≥3 calibration windows; locate the breakdown region
(ZNE residuals / error bars diverge) and collapse (output variance → 0, barren-plateau link);
compare linear/Richardson/exponential extrapolators.

**Figures.** per-device accuracy vs 2q cost; optimal-vs-adverse panels; topo_dist ↔ SWAP ↔
degradation correlation; method comparison (ZNE/CDR/[[4,2,2]]) on the shots-to-target axis;
variance-collapse plot.

**Report mapping.** Final results sections + the hardware-aware compilation guideline.

---

## Suggested run order

1. **Sim controls (no credentials):** §1 → §2 → §3 (CDR) / §4 ([[4,2,2]]) dry-runs → §5.
2. **Hardware bring-up:** §7 smoke → go/no-go on ODRA, then Garnet, then Emerald bracketing.
3. **Campaigns:** optimal-vs-adverse ladders; CDR; encoded-vs-physical; ≥3 ODRA windows (§8).
4. **Synthesis:** §6 mirror benchmark + §8 figures + report.

## Definition of done (per the plan)

Cross-topology ladders (≥2 topologies) with drift bands; optimal-vs-adverse with SWAP/depth/
mean-value/fidelity; topo-distance↔SWAP↔degradation correlation; ZNE-vs-CDR-vs-[[4,2,2]] on the
shots-to-target axis; encoded-vs-physical (incl. a clean negative if that's the result);
publication figures + final report + reproducible release.

---

## 9. Circuit twirling pod routingiem — pilot + docelowa metodologia (potencjalnie kluczowy wątek)

**Cel.** Scharakteryzować, jak *randomized compiling* (Pauli twirling) tłumi **koherentny**
błąd routingu i przywraca skuteczność ZNE/CDR — **rozdzielone po koszcie routingu i topologii**,
i **ilościowo powiązane** z niezależnie zmierzoną frakcją koherentną urządzenia. Wyprowadzenie
matematyczne twirlingu: patrz `raport_month_2.tex`, sekcja „Circuit twirling".

**Kontekst (sim + realny sygnał).** Sim z wstrzykniętym koherentnym błędem (`twirl_zne_scope.py`,
`twirl_cdr_scope.py`): twirl+ZNE poprawia ⟨O⟩-błąd ~2.2×; **twirl+CDR przywraca r² 0.81→0.99**
(błąd 0.109→0.015). Realny sygnał zakotwiczający: `garnet_cdr` r² spada **0.99→0.69 przy 96 CZ**
— sygnatura błędu koherentnego łamiącego liniowość CDR. Hipoteza: twirling to odwróci.

**IQM Resonance nie ma twirlingu serwerowego** (iqm-client 34.x: tylko DD) → twirling
**client-side**: każda natywna bramka CZ owinięta losową Paulią `A` + kompensacją `B=CZ·A·CZ†`,
M losowych instancji, uśrednienie counts. Zwalidowane (ideał zachowany). Narzędzie:
`run_garnet_twirl.py` (dry-run domyślny).

### 9a. PILOT (krok 1, ~135 cr) — bramka decyzyjna
Zanim inwestujemy w pełną wersję, tani test rozstrzyga „czy w ogóle warto":
- **Drabina 3 punktów CZ:** `optimal:star` (~12 CZ), `optimal:all_to_all` (~57), `adverse:all_to_all` (~96).
- **Ramię:** CDR (r² to najostrzejszy sygnał; jego kolaps obserwowany w realu).
- **Twirl on/off** w **tym samym oknie** (jedyna różnica = twirling).
- Parametry (**Wariant 2, literaturowo-minimalny**): eval-points 3–4, shots **2048**,
  **n_train 10** (standard sprzętowy CDR, Czarnik i in.), **M_twirl 8** (zakres zbieżności RC 5–10,
  Hashim i in. używali 20). Reżim literaturowy: RC M~20 / shots~8192 / n_train~10 — pilot świadomie
  okrojony na shotach i M (patrz `raport_month_2.tex`, sekcja twirling, ref hashim2021/czarnik2021).
- **Koszt:** ~368 cr (E3) lub ~491 cr (E4).
- **Metryki:** `err`, `cdr_r2` per punkt.
- **Kryterium przejścia do pełnej wersji:** zysk rośnie z CZ — przy 96 CZ `r²(on) >> r²(off)`
  (≈0.69→~0.9), przy 12 CZ różnica mała. Jak tak → pełna wersja §9b; jak nie → Garnet ma mało
  koherencji (też wynik, ustalony za ~400 cr zamiast ~1100).
- Komenda (E3, ~368 cr): `python run_garnet_twirl.py --submit --arms cdr --points optimal:star optimal:all_to_all adverse:all_to_all --eval-points 3 --shots 2048 --n-train 10 --n-twirl 8`
  (E4, ~491 cr: `--eval-points 4`).
- Uwaga: pilot poniżej reżimu literaturowego na shotach/M → **liczby kierunkowe, nie publikowalne**;
  do paperu reżim pełnej wersji §9b (M20/shots8192).

### 9b. DOCELOWA METODOLOGIA (pełna, po pozytywnym pilocie)
1. **Pełna drabina routingu:** 2 placement × 4 pattern (CZ 12→96) + idealnie **Emerald**
   (cross-topology). Rozdziela wkład placement vs pattern do CZ.
2. **Trzy ramiona:** raw + ZNE + CDR, twirl on/off każde → czy twirling **przesuwa crossover
   ZNE↔CDR (~39 CZ)**? (bezpośrednie spięcie z Core Value / rozdz. porównania metod).
3. **Niezależny pomiar frakcji koherentnej — unitarity randomized benchmarking** (do napisania:
   `run_garnet_urb.py`). Zamienia claim z „twirl pomógł" na „twirl pomógł DOKŁADNIE tyle, ile
   przewiduje zmierzona frakcja koherentna X%" — ilościowe potwierdzenie mechanizmu. **Najważniejszy
   upgrade.**
4. **Pasma driftu:** ≥2 okna kalibracji (standard BRKD-01) → słupki błędu z driftu.
5. **Wysoka statystyka:** 15–30 eval-points, 4096 shots, **M_twirl 20** (RC standard), n_train 40.
6. **Sweep M** (2,4,8,16,32) — zbieżność estymatora twirla; **ablacja DD** (`dd_mode`) — twirl vs
   DD vs oba (komplementarne kanały: bramki koherentne vs dephasing bezczynności; domyka gap #7).

**Metryki (pełne):** err(⟨O⟩), cdr_r2, crossover-CZ (twirl on vs off), przewidziany-vs-zmierzony
zysk twirlingu (z URB), wszystko z pasmami driftu.

**Szacowany koszt pełnej wersji:** ~1000–1500 kredytów (M=20 × drabina × 3 ramiona × 2 okna +
URB) → uruchamiać TYLKO po pozytywnym pilocie 9a.

**Dlaczego to może być kluczowy wątek pracy:** to jedyna kompozycja, która **działa** na prawdziwym
klasyfikatorze (w przeciwieństwie do detekcja+ZNE), z **ilościowo przewidywalnym** mechanizmem
(URB→frakcja koherentna→zysk), rozdzielona po **osi routingu i topologii** spójnej z całym paperem.

### 9c. WERSJA WYKONAWCZA (b) — utwardzenie twirl+CDR na VQC + pasma driftu

Skonsolidowana metodologia po pilocie (9a, POZYTYWNY) i URB (§9b pkt 3, WYKONANE). Odróżnia się
od §9b tym, że **redukuje zakres do potwierdzonego, taniego, pewnego wyniku**: twirl+CDR na VQC z
oknami driftu. Trzy ustalenia zawężają plan:
- **Pilot potwierdził twirl+CDR** (r² OFF→ON: 0.957→0.986 / 0.820→0.939 / 0.837→0.909 przy 12/57/96 CZ;
  err spada wszędzie; zysk rośnie z CZ).
- **ZNE porzucone (H4):** twirl pomaga CDR (fit liniowy, wrażliwy na koherencję), NIE ZNE
  (ekstrapolacja, odporna). W symulacji twirl+ZNE pomaga (6/6), ale na Garnecie koherencja bramki
  jest mała → narzut twirla dominuje dla ZNE. Ramię ZNE **wyłączone** z kampanii (b).
- **URB:** frakcja koherentna CZ na Garnecie modest (u=0.843, p=0.908, u−p²≈0.019) i **drift-swamped**
  (drift u ≈0.09 >> sygnał 0.019) → zysk twirla jest na poziomie **obwodu** (routing/idle/crosstalk),
  nie izolowanej bramki. Stąd: drift MUSI być zmierzony (okna), a „predicted==measured" (H3) jest
  celem osobnym (punkt (a), cycle benchmarking) — **nie** blokuje (b).

**Claim (b):** *Circuit twirling przywraca jakość dopasowania liniowego CDR (r²) i obniża ⟨O⟩-błąd
klasyfikatora VQC, a efekt rośnie z narzutem routingu — istotnie ponad pasmo driftu kalibracji.*

**Obiekt:** prawdziwy VQC (`trained_models_hard`, offset 0.1, 5q, 3 warstwy, wagi per-pattern),
obserwabl mean-Z, metryka pierwotna ⟨O⟩-błąd vs zamrożony ideał, **r² dopasowania CDR = najostrzejszy
sygnał koherencji**.

**Drabina routingu (oś główna):** 3 punkty minimum — `optimal:star` (~12 CZ), `optimal:all_to_all`
(~57), `adverse:all_to_all` (~96); opcjonalnie `adverse:star` (~36) i `optimal:circular` (~39) dla
gładszego trendu.

**Ramiona (jedna kampania pokrywa BRKD-01 + flagowy twirl).** `--arms raw cdr zne --twirl-arms cdr`:
- **raw** (twirl OFF) — nieskorygowany ⟨O⟩-błąd = baseline breakdown, drift-banded.
- **zne** (twirl OFF) — ZNE-skorygowany błąd, drift-banded.
- **cdr** (twirl OFF **i** ON, matched) — CDR-skorygowany błąd + r² + **flagowy zysk twirla**.
Tylko CDR dostaje ramię ON (H4: twirl pomaga fitowi CDR, nie ekstrapolacji ZNE) → raw+ZNE dokładają
~3% kosztu, a dają **pasma driftu regionu breakdown (BRKD-01) w tej samej kampanii** — nie trzeba
osobnego 2. okna `garnet_full`. Procedura CDR per punkt/okno: near-Clifford treningi (ta sama
struktura/routing) → wartości idealne dokładnie (stabilizator) → zaszumione (OFF: M kopii matched;
ON: średnia M twirlowanych) → `fit_cdr`→(a,b,r²) → `apply_cdr` na targecie.

**Twirl:** **logiczny** (pilot zadziałał; pewny) z uczciwą adnotacją, że natywny RC to przyszły
refinement (layout-preservation niewalidowalny bez backendu; opcjonalny test 1-obwodowy przed pełną
kampanią).

**DWA CONFOUNDY I ICH KONTROLE (rdzeń rygoru — złapane w `--sim` przed wydaniem kredytów).**

1. **Confound próbkowania (usunięty).** Ramię ON uśrednia M randomizacji → M× więcej shotów niż OFF
   (1×). Samo to podnosi r² i obniża err — **niezależnie od koherencji**. Dowód: w `--sim` pod
   **depolaryzacją** (szum niekoherentny, twirl nie ma czego usuwać) niezrównane M=10 dało ON≫OFF
   (r² 0.72→0.87), a przy równym próbkowaniu M=1 dało ON≈OFF (a nawet gorzej). Cały „zysk" był
   próbkowaniem. **Kontrola: `--match-shots` (domyślnie ON)** — OFF uśrednia M identycznych,
   **nietwirlowanych** kopii → OFF i ON mają to samo próbkowanie; różnica ON−OFF izoluje **wyłącznie
   supresję błędu koherentnego**.
2. **Kara narzutu bramek (czyni claim konserwatywnym).** Twirlowany obwód ma dodatkowe bramki-owijki
   Pauliego → odrobinę więcej szumu **niekoherentnego**. Twirl walczy więc z własnym narzutem →
   zmierzone ON−OFF to **dolne ograniczenie** rzeczywistego zysku koherentnego. W `--sim` (depol,
   matched) ON jest ≈ lub lekko < OFF — widać tę karę.

**KOTWICA NULL (zmierzona — 3 sim-okna, matched, depol, per-okno twirl-seed).** Wynik:

| punkt | null Δr² (mean±std) | pojedyncze |
|---|---|---|
| cz=33 optimal:star | **−0.002 ± 0.002** | −0.004, −0.002, −0.001 |
| cz=87 adverse:a2a | **−0.016 ± 0.042** | −0.050, +0.031, −0.027 |
| cz=90 optimal:a2a | **−0.022 ± 0.017** | −0.004, −0.037, −0.026 |
| **trend** | **−0.030 ± 0.020 / 100 CZ** | „within drift" |

Trzy wnioski: (i) null Δr² ≈ **0 lub lekko UJEMNY** — pod matched+depol twirl nie pomaga, a nawet
lekko szkodzi (kara narzutu #3); kontrola matched zapadła zysk z niezrównanych +0.10–0.15 do ~0.
(ii) null **trend płaski/ujemny** → pod szumem niekoherentnym NIE ma „zysk rośnie z routingiem";
dodatni trend na sprzęcie jest więc **diagnostyczny dla koherencji**. (iii) floor ma realną szerokość
przy wysokim CZ (**~±0.02–0.04**) → to kwantyfikuje próg.

> **Reguła decyzji.** Zysk twirla na sprzęcie jest realny (koherentny) tylko gdy **hardware Δr² > 0
> ORAZ > null-floor** (mean+std pod symulowanym szumem NIEKOHERENTNYM: ~**+0.02–0.04** przy 87–90 CZ),
> **i** trend Δr² vs CZ jest **dodatni** (null trend jest płaski/ujemny). Uwaga na znak: werdykt
> agregatora `|Δr²|>std` mierzy istotność MAGNITUDY — dla sprzętu czytamy dodatkowo ZNAK (Δr²>0).

Framing pracy: *„pod symulowanym szumem niekoherentnym zrównany twirl daje floor ≈0/lekko ujemny bez
trendu; na sprzęcie Δr² przekracza floor i ROŚNIE z routingiem → zysk jest specyficzny dla błędu
KOHERENTNEGO, nie artefaktem próbkowania, fitu ani narzutu."* Sim-null raportujemy jako pasmo OBOK
sprzętu na figurze głównej. **Uwaga do pilota:** pozytyw twirl+CDR (+0.03/+0.12/+0.07) był
**niezrównany** → część to próbkowanie; kampania (b) MUSI go przemierzyć matched i porównać z null.

**Model błędu (dwa poziomy).**
- *Wewnątrz-okna*: szum shotów + rozrzut po eval-points + skończona wariancja M randomizacji.
- *Między-oknami*: drift kalibracji.
- **Paired ON−OFF kasuje common-mode drift** (oba mierzone w TYM SAMYM oknie) → pasmo na Δ (paired,
  między-oknowe std) to właściwa statystyka efektu twirla. Absolutne `r²(OFF)`/`r²(ON)` też dostają
  pasma driftu, ale te są zdominowane przez drift.

**Protokół okien.**
- Okno = jeden cykl kalibracji IQM. Okna MUSZĄ obejmować **różne cykle** (godziny/następny dzień) —
  inaczej drift≈0 i pasma są sztucznie wąskie (bezużyteczne).
- **≥2 okna** (minimum na std), **3 rekomendowane** (std z n=2 to bardzo słaby estymator).
- **Niezależny seed twirla per okno** (zaimplementowane: seed = args.seed ⊕ hash(window_id)) → każde
  okno losuje INNY zestaw M dressingów → między-oknowe std łapie **drift + wariancję randomizacji**
  (uczciwe, szersze pasma). Konstrukcja CDR + transpile na stałym `args.seed` → śledzimy drift TEGO
  SAMEGO estymatora, nie resampling treningu. Eval-targets stałe między oknami.
- OFF i ON w tym samym oknie (paired).

**Parametry (config matched).**

| Parametr | Wartość | Uzasadnienie |
|---|---|---|
| match-shots | **ON** | usuwa confound próbkowania (rdzeń) |
| M_twirl | **6** | matched 2×6=12 ≈ koszt starego niezrównanego M=10; w zakresie zbieżności RC 5–10 (Hashim) |
| n_train | 10 | standard CDR (Czarnik) |
| shots | 1024 | shots = główna dźwignia kosztu; 1024 utrzymuje wielookienność |
| eval-points | 4 | rozrzut wewnątrz-okna |
| okna | 3 (min 2) | ≥2 na std (BRKD-01) |
| twirl-seed | per okno | drift + wariancja randomizacji w pasmach |
| CDR/transpile seed | 42 (stały) | ten sam estymator śledzony |

**Metryki + figura główna:** `Δr² = r²(ON)−r²(OFF)` (paired) vs CZ z pasmami między-oknowymi,
**z nałożonym sim-null Δr²≈0**; ⟨O⟩-błąd analogicznie. Dwa testy:
- *Istotność*: `|mean(Δr²)| > między-oknowe std`? Z n=2–3 okien raportujemy też **wszystkie
  pojedyncze Δ per okno** (pokazuje spójność wprost, nie tylko słaby t z n−1 dof).
- *Trend (kluczowy, spina z Core Value)*: nachylenie `Δr²` vs CZ per okno → mean±std nachylenia;
  dodatnie = „zysk rośnie z routingiem".
- *Cross-check*: `r²(OFF)` vs niezależny `garnet_cdr` (0.99→0.69) → okno reprezentatywne, nie
  outlier kalibracji.

**Koszt (dry-run, dokładny; 3 pkt CZ; config matched).** Matched M=6 kosztuje ~tyle co stare
niezrównane M=10 (OFF 6 + ON 6 = 12 jednostek vs 1+10=11), ale jest rygorystyczne.

| Config (matched, per okno) | ~cr/okno | 2 okna | 3 okna |
|---|---|---|---|
| M5/n10/E4/1024 (10 jedn.) | ~275 | ~550 | ~825 |
| **Rekom.** M6/n10/E4/1024 (12 jedn.) | ~330 | ~660 | ~990 |
| M6/n10/E5/1024 | ~412 | ~824 | — |

Rekomendacja: **matched M6/n10/E4/1024 × 3 okna ≈ 990 cr** (× 2 ≈ 660 jeśli budżet ciasny).

**Zagrożenia dla trafności (pełna lista, z kierunkiem i statusem).** Kolumna *kierunek*: czy dany
efekt ZAWYŻA (na naszą korzyść — groźny) czy ZANIŻA (przeciw nam — bezpieczny, konserwatywny) mierzony
zysk. Status: **naprawione** / **konserwatywne** (działa przeciw nam → nie może wygenerować fałszywego
pozytywu) / **otwarte** (realne ograniczenie, spisane uczciwie).

*A. Trafność wewnętrzna (czy ON−OFF mierzy naprawdę supresję błędu koherentnego?)*
1. **Confound próbkowania** (ON dostaje M× shotów). Kierunek: ZAWYŻA. Status: **naprawione**
   (`--match-shots`) — potwierdzone w sim: matched zapadł Δr² z ~0.10–0.15 do ~0.005–0.03.
2. **Resztkowy floor null** (matched pod depol wciąż daje mały Δr² z szumu estymatora r²). Kierunek:
   ZAWYŻA. Status: **naprawione regułą decyzji** — sprzęt musi przekroczyć zmierzony null-floor
   (mean+std z sim-okien), nie tylko 0.
3. **Kara narzutu bramek** (twirl dokłada owijki Pauliego → więcej szumu niekoherentnego + dłuższy
   obwód → więcej dekoherencji T1/T2). Kierunek: ZANIŻA. Status: **konserwatywne** — zmierzone Δ to
   dolne ograniczenie prawdziwego zysku koherentnego.
4. **Twirl logiczny, nie natywny** — SWAP-y wstawione przez routing pozostają NIEotwirlowane; owijamy
   tylko logiczne cx. Kierunek: ZANIŻA (mniej pokrycia → mniej usuniętej koherencji). Status:
   **otwarte co do MAGNITUDY** (native RC dałby więcej), ale bezpieczne co do ZNAKU. Natywny twirl =
   przyszły refinement / punkt (a).
5. **Paired kasuje drift tylko przy współczesności OFF/ON** — runner submituje batch OFF, potem batch
   ON (nie interleaved) → drift wewnątrz okna między batchami skaża parę. Kierunek: dowolny (szum).
   Status: **otwarte, mitygowane** — okno = stabilny cykl kalibracji (drift wewnątrz-okna mały);
   pełna mitygacja = interleaving OFF/ON w jednym jobie (możliwy refinement runnera).
6. **r² jako proxy koherencji** — r² miesza nieliniowość koherentną z (usuniętym matchem) szumem
   shotów i z ewentualną nieliniowością kanału niezwiązaną z koherencją. Kierunek: dowolny. Status:
   **otwarte** — bezpośredni pomiar koherencji to URB (zrobione, poziom bramki, drift-swamped) /
   cycle benchmarking (punkt a); (b) pokazuje zysk SPÓJNY z koherencją, nie mierzy jej wprost.

*B. Trafność zewnętrzna (czy wnioski się uogólniają?)*
7. **Jedno urządzenie (Garnet)** dla studium driftu — magnituda driftu i frakcja koherentna są
   device-specific. Emerald dokłada oś topologii, ale **nie** niezależnej replikacji driftu. Status:
   **otwarte** (zakres pracy: Garnet-resolved).
8. **Jeden VQC / jedno zadanie / jedna obserwabla** (two_curves, mean-Z, model hard). Sygnatura
   koherencji i zysk twirla mogą zależeć od struktury obwodu. Status: **otwarte** — uogólnienie na
   inne obwody nieustalone.
9. **CZ-count jako oś kosztu routingu** — różne placementy o podobnym CZ mają różny crosstalk/idle;
   CZ to niedoskonałe jednowymiarowe podsumowanie „kosztu". Status: **otwarte** (uzupełnia je URB/
   cycle-benchmarking na poziomie warstwy).

*C. Trafność statystyczna*
10. **n=2–3 okna → std z 1–2 dof** — bardzo słaby estymator; unikamy twardych p-value, raportujemy
    WSZYSTKIE pojedyncze Δ per okno (spójność wprost). Status: **otwarte, mitygowane** (3 okna > 2).
11. **Trend z 3 punktów CZ** — nachylenie wrażliwe na jeden punkt; claim „rośnie z routingiem" jest
    **kierunkowy**, nie precyzyjny. Status: **otwarte** — więcej punktów CZ = przyszłe zagęszczenie.
12. **Null-floor też szumny** (z kilku sim-okien) → reguła decyzji dziedziczy jego niepewność. Status:
    **mitygowane** — sim-okna są darmowe, więc floor można zagęścić dowolnie (więcej seedów/E).

*D. Trafność konstruktu*
13. **„Frakcja koherentna" nie jest w (b) mierzona wprost** — wnioskujemy supresję z Δr² > null.
    „predicted==measured" (H3) jest **świadomie poza zakresem (b)** → wymaga cycle benchmarking
    (punkt a). (b) dowodzi, że twirl POMAGA w sposób spójny z koherencją; (a) domyka ILE.

**Bilans:** wszystkie groźne kierunki (ZAWYŻAjące — #1, #2) są NAPRAWIONE; pozostałe realne
ograniczenia albo działają PRZECIW nam (#3, #4 — konserwatywne, nie mogą sfabrykować pozytywu), albo
są uczciwie spisanym zawężeniem ZAKRESU (#6–#9, #13 → domyka je punkt (a)/Emerald), albo słabością
statystyczną łagodzoną przez raportowanie surowych per-okno Δ (#10–#12).

**Deliverable:** główna figura twirlingu do raportu (`r²(OFF)`/`r²(ON)` vs transpiled CZ ze słupkami
driftu, Δr² zaznaczone) + tabela per CZ (r² OFF/ON ± std, err OFF/ON ± std). Domyka główny wynik
twirlingu na VQC; H3 (predicted==measured) pozostaje dla punktu (a).

**Komendy (per okno — użytkownik, venv py3.11, IQM_RESONANCE_URL + IQM_TOKEN):**
```
# okno 1 (combined: raw+ZNE breakdown + CDR flagship, matched, ~340 cr) — --match-shots DOMYŚLNY
python run_garnet_twirl.py --submit --arms raw cdr zne --twirl-arms cdr \
  --points optimal:star optimal:all_to_all adverse:all_to_all \
  --eval-points 4 --shots 1024 --n-train 10 --n-twirl 6 \
  --window-id w1 --out garnet_twirl_w1.csv
# okno 2 (inny cykl kalibracji — godziny/następny dzień, NIE od razu) — identycznie, --window-id w2 --out ...w2.csv
# okno 3 (opcjonalne, lepszy estymator std) — --window-id w3 --out ...w3.csv
python aggregate_twirl_windows.py garnet_twirl_w*.csv   # → paired Δr² ± między-oknowe std + werdykt + trend; raw/ZNE/CDR pasma breakdown
# sim-null floor (za darmo, kotwica decyzji) — kilka sim-okien pod depol:
#   for w in n1 n2 n3; do python run_garnet_twirl.py --sim --arms cdr --twirl-arms cdr \
#     --points optimal:star optimal:all_to_all adverse:all_to_all --eval-points 4 --shots 1024 \
#     --n-train 10 --n-twirl 6 --window-id $w --out null_$w.csv; done
#   python aggregate_twirl_windows.py null_n*.csv   # → null Δr² mean±std = próg, który sprzęt musi przekroczyć
```

### 9d. EMERALD cross-topology (TOPO-02) — dwie opcje do decyzji budżetowej

Emerald (54q, klasycznie niesymulowalny: 2^54) to **jedyny punkt QPU-only** i 3. topologia (po ODRA
star, Garnet lattice) → sedno „cross-topology" z Core Value. **Bez twirla** (`--twirl-arms` puste) —
brak `--sim` na Emeraldzie → twirl nienadwalidowany; twirl zostaje na Garnecie. Feasibility metod:
ideały treningowe CDR są Cliffordowskie (symulowalne), ideał VQC = 5q statevector (trywialny), ZNE
nie potrzebuje ideału → **raw/ZNE/CDR działają**; niesymulowalny jest tylko device-noisy-sim
baseline → stąd **smoke-test** (1 obwód) zamiast walidacji sim. **1 okno** (bez driftu — drift na
Garnecie). Koszt realny ≈ estymata ×1.5 (Emerald 0.75 vs Garnet 0.50 cr/s).

| Opcja | Ramiona | Co daje | ~Real cr |
|---|---|---|---|
| **LEAN** | raw + zne | cross-topology breakdown + ZNE-decay na 3. topologii; zasila Spearman err–CZ i figurę frontier; TOPO-02 minimum | ~40 |
| **FULL** (rekom.) | raw + cdr + zne | + crossover ZNE↔CDR na Emeraldzie → korelacja „przesunięcie crossover z topologią" (spina Core Value) | ~150 |

Oba: 4 punkty (optimal/adverse × star/all_to_all), E4, shots 2048. Skoro tanio — można podbić
eval-points/patterny. Komendy:
```
# smoke (kilka cr)
python run_garnet_twirl.py --submit --device emerald --arms raw --twirl-arms \
  --points optimal:star --eval-points 1 --shots 256 --window-id em_smoke --out em_smoke.csv
# FULL
python run_garnet_twirl.py --submit --device emerald --arms raw cdr zne --twirl-arms \
  --points optimal:star adverse:star optimal:all_to_all adverse:all_to_all \
  --eval-points 4 --shots 2048 --n-train 10 --window-id em1 --out emerald_xtopo.csv
```
