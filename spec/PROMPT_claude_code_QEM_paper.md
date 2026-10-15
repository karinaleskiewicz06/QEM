# Prompt dla Claude Code: przygotowanie repozytorium QEM do kampanii ODRA i artykułu

> Skopiuj wszystko poniżej linii do Claude Code uruchomionego w katalogu repozytorium `QEM` (gałąź `month2-topology-port`, commit `81e0f97`). Przed startem skopiuj do repo, do katalogu `spec/`, pliki pomocnicze z sesji:
> - `merge_prx_native_twirl.py`
> - `sim_cdr_variants_bench2.py`
> - `sim_cdr_variants_bench3_control.py`
> - `QEM_luka_badawcza_i_plan_ODRA.md`
> - `QEM_Koster_Scavino_i_nowa_metoda_CDR.md`
> - `draft_artykul_QEM_ODRA.md`
> - jeden plik kalibracji ODRY w formacie `collect_odra_calibration.py`, zapisany jako `spec/odra_cal_example.json` (potrzebny do P7/P8).

---

## Rola i cel

Jesteś inżynierem badawczym w projekcie QEM (mitygacja błędów na IQM ODRA 5: 5 kubitów, topologia gwiazdy, hub QB3, bramki natywne PRX `r` i `cz`). Masz przygotować kod, symulator i analizę pod **pre-rejestrowaną kampanię na ODRZE** oraz artykuł *„Shot-matched Pauli twirling as a precondition for Clifford data regression, and the finite-shot window of ZNE”* (draft: `spec/draft_artykul_QEM_ODRA.md`, uzasadnienie: dwa pozostałe pliki `.md` w `spec/`).

Pracujesz wyłącznie na kodzie, symulatorze (Qiskit Aer) i trybie dry-run. **Nie wysyłasz niczego na QPU.**

## Twarde zasady

1. **Zakaz QPU.** Nie uruchamiaj żadnego skryptu z `--submit` i nie wywołuj `odra_backend.run_circuits` na prawdziwym backendzie. Nie czytaj, nie wypisuj i nie zapisuj `IQM_TOKEN`. Sprawdzasz wszystko w `--sim` lub `--dry-run`.
2. **Dane historyczne są nietykalne.** Nie modyfikuj ani nie usuwaj istniejących `*.csv`, `trained_models_hard/*` ani raportów `.tex`. Nowe wyniki trafiają wyłącznie do `runs/` i `results_sim/`.
3. **Gałąź i commity.** Pracuj na nowej gałęzi `paper-odra-campaign` utworzonej z `month2-topology-port`. Jeden commit na zadanie (prefiks `P0:`, `P1:` …), z testami w tym samym commicie.
4. **Zgodność wstecz.** Stare zachowanie zostaje dostępne pod flagą `--legacy`, bo potrzebujemy go do reprodukcji starych wyników. Nowe ustawienia są domyślne.
5. **Testy.** Każda zmiana ma test w `tests/` (pytest). Na koniec `python -m pytest -q` przechodzi w całości. Testy symulacyjne mają flagę `@pytest.mark.slow`; szybki zestaw musi trwać < 3 min.
6. **Komentarze i docstringi** po angielsku albo po polsku, spójnie z plikiem, który edytujesz. Nie zmieniaj nazw istniejących publicznych funkcji, tylko dodawaj nowe.
7. Gdy coś w specyfikacji jest niejednoznaczne albo sprzeczne z kodem, **zatrzymaj się i zapytaj** zamiast zgadywać. Dotyczy to zwłaszcza fizyki: konwencji PRX, mapowania kubitów i definicji obserwabli.

## Fakty o obecnym kodzie, sprawdzone (punkt startowy)

- `cdr.near_clifford_training_circuits(target, n_train, seed)` z tym samym `seed` zwraca **identyczne obwody 1..n−1 dla wszystkich celów**; różni się tylko obwód 0 (najbliższy Clifford). Obwody 1..n−1 zamieniają **każdy** obrót na losowy kąt Clifforda.
- `run_odra_cdr.py` transpiluje każdy obwód treningowy osobno przez `zne_dryrun.native_transpile` (bez `seed_transpiler` i bez `initial_layout`). Przy routingu (linear/circular/all_to_all) 0/10 obwodów treningowych ma ten sam szkielet CZ co cel, a ten sam cel transpilowany 5 razy daje 5 różnych szkieletów. `run_garnet_twirl.py` (stały układ, seed 42) daje zgodność 10/10.
- `run_garnet_twirl.twirl_native` wstawia Pauli jako osobne bramki `r` bez scalania. Na gwieździe 5q obwód ma przez to 2,3–2,7× więcej PRX, np. 356 zamiast 130 przy 54 CZ. `optimization_level=1` zostawia ~2× więcej PRX, niż jest potrzebne (40 zamiast 20 przy 12 CZ).
- `zne_dryrun._clamped` / `extrapolate` po cichu przełącza się na fit liniowy, gdy |EV| > 1,25 (`_EV_BOUND`).
- Mapowanie logiczne→fizyczne ODRY: `PHYS = [QB3, QB1, QB2, QB4, QB5]` (logiczny 0 = hub).
- Repo nie ma pliku zależności. Środowisko referencyjne: Python 3.12, `qiskit==2.5.2`, `qiskit-aer==0.17.2` (wersję `iqm-client` odczytaj z aktualnego środowiska i przypnij).
- Obecne CSV-y zapisują tylko średnie, bez surowych zliczeń.

---

## Zadania (w tej kolejności)

### P0. Odtwarzalność i zapis danych
- `requirements.lock` z przypiętymi wersjami. `qem/env_check.py` wypisuje wersje i przerywa, jeśli Qiskit ≠ 2.5.2 (chyba że użyto `--allow-env-mismatch`).
- Moduł `qem/provenance.py`:
  - `RunManifest` (JSON): `git_commit`, `git_dirty`, wersje pakietów, `seed`, argumenty CLI, `window_id`, `calibration_set_id` na początku i końcu okna, czasy UTC, lista job ID;
  - `save_counts(path, circuit_id, counts, meta)` dopisuje do `counts.jsonl` (jeden rekord na obwód, z QASM3 obwodu natywnego, liczbą CZ i PRX, szacowanym czasem trwania, ramieniem, ramką Pauliego, indeksem punktu i obwodu treningowego).
- Wszystkie runnery (`run_garnet_twirl.py`, `run_odra_cdr.py`, `zne_shot_boundary.py`, `random_mirror_benchmark.py`, `run_hardware.py`) zapisują manifest i `counts.jsonl` w `runs/<campaign>/<window_id>/`. CSV-y z wynikami zostają jako widok pochodny i dają się odtworzyć z `counts.jsonl` skryptem `analysis/rebuild_from_counts.py`.
- **Akceptacja:** test, że `rebuild_from_counts` na wynikach `--sim` daje bit w bit te same średnie co CSV z runnera.

### P1. Jedna ścieżka transpilacji i CDR na obwodzie natywnym
- `qem/compile.py`: `compile_native(circ, *, layout=PHYS_IDENTITY, seed=42, merge_1q=True)`. Ta funkcja jest jedynym miejscem transpilacji w repo (używa `topology.star_coupling_map`, stałego `initial_layout`, `seed_transpiler`). Zwraca obwód natywny i metadane: szkielet CZ (lista par), liczbę CZ i PRX, końcowy layout.
- `qem/merge1q.py`: przenieś `merge_prx` ze `spec/merge_prx_native_twirl.py`. Scala każdy ciąg bramek 1q między CZ w ≤ 1 PRX, przepycha wirtualne RZ przez CZ (komutują) i odrzuca końcowe RZ przed pomiarem w bazie Z. Ma obsługiwać `measure` i `barrier`.
  - **Akceptacja:** dla wzorców star/linear/circular/all_to_all na losowych wagach ⟨Zᵢ⟩ ze Statevector są identyczne (tolerancja 1e-10). Liczba PRX po scaleniu dla obwodu OFF wynosi 20/50/75/63 (±10%) przy 12/24/36/54 CZ (wartości referencyjne w `spec/`).
- **Obwody treningowe CDR budowane na obwodzie natywnym celu.** `qem/cdr_training.py`:
  - `snap_native_to_clifford(native, angle_sampler)` podmienia parametry każdej bramki `r(θ, φ)` na wartości Clifforda: θ ∈ {0, π/2, π, 3π/2}, φ ∈ {0, π/2, π, 3π/2}, a bramki z θ = 0 usuwa. Sprawdzone: dla wszystkich 4 wzorców daje to obwód Clifforda o identycznym szkielecie CZ. Szkielet CZ pozostaje identyczny z celem, **bez ponownej transpilacji**. Zweryfikuj `qiskit.quantum_info.Clifford(circ)` dla każdego obwodu treningowego i licz wartość idealną symulatorem stabilizatorowym.
  - Samplery kątów:
    - `nearest` (obwód 0);
    - `uniform_random` (legacy);
    - `near_target(sigma)`: kąt Clifforda losowany z wagą exp(−d²/σ²), gdzie d to odległość kątowa od oryginału; domyślnie σ = π/4, osobno dla θ i φ.
  - Seed **zależny od celu**: `seed = hash((base_seed, target_index, window_id))`. Tryb `--legacy-shared-training` odtwarza stare zachowanie.
- **Akceptacja:**
  - test, że dla wszystkich 4 wzorców 100% obwodów treningowych ma szkielet CZ identyczny z celem;
  - test, że dwa cele mają różne zbiory treningowe;
  - test, że w trybie legacy na ścieżce `native_transpile` odtwarzasz niezgodność (0/10 dla linear), jako udokumentowaną regresję.
- `DATA_NOTES.md`: opisz, że `odra_full_100pt.csv` i `odra_cdr_100pt.csv` mają CDR trenowane na obwodach o innym routingu niż cel (z wyjątkiem star), a `odra_twirl_o1/o2` i `garnet_twirl_w*` mają szkielety zgodne.

### P2. Twirling: natywny ze scalaniem i ramiona z równym budżetem
- `qem/twirl.py`:
  - `twirl_native_merged(native, rng)`: owija każdy fizyczny CZ losową parą Pauliego (A przed, B = CZ·A·CZ† po), potem `merge_prx`. Zwraca obwód i zapis ramki (lista Pauliego dla każdego CZ).
  - `twirl_logical` (dotychczasowe zachowanie) zostaje do porównań.
- Ramiona CDR, wybierane `--cdr-arms`, **każde przy tym samym budżecie** B = (n_train + 1)·M·S shotów na punkt ewaluacyjny:
  - `off_copies`: n_train obwodów, każdy M identycznych kopii po S shotów (kontrola z dopasowaniem; kopie zapisane osobno);
  - `twirl_logical`: n_train × M ramek;
  - `twirl_native`: n_train × M ramek, scalone;
  - `spread`: **n_train·M różnych obwodów treningowych (`near_target`), każdy z jedną ramką natywną, S shotów**; cel z M ramkami. To proponowana metoda; szczegóły i wyniki symulacji w `spec/QEM_Koster_Scavino_i_nowa_metoda_CDR.md` §3.3;
  - `spread_off`: to samo bez twirlingu (kontrola czynnikowa 2×2);
  - `train_set ∈ {shared_random, near_target}` jako osobny wymiar.
- Dopasowanie CDR: `fit_cdr` (OLS, bez zmian) plus `fit_cdr_eiv` (korekta rozcieńczenia regresji: nachylenie = cov(x, y)/(var(x) − średnia σ²ₓ), z ograniczeniem do 4× de-atenuacji). σ²ₓ jest liczone z bloków kopii lub ramek, a dla `spread` jako wariancja shotów plus wariancja między ramkami celu. Raportuj oba.
- **Akceptacja:**
  - test równości budżetu, czyli sumy shotów, we wszystkich ramionach;
  - test, że ramka zapisana w `counts.jsonl` pozwala zrekonstruować obwód;
  - smoke test w `--sim` dla 2 punktów drabiny.

### P3. ZNE: diagnostyka i kontrole (Köster i Mauerer, arXiv:2607.09360)
- Usuń cichy fallback. `extrapolate(..., on_unphysical="flag")` zwraca wynik i flagę. CSV dostaje kolumny `fallback_used`, `unphysical`. Stare zachowanie dostępne pod `--legacy-clamp`.
- Zapisuj ⟨O⟩ dla każdej skali λ (zawsze) i zliczenia dla każdej skali.
- **Kontrole foldingu** przy tej samej liczbie CZ i tym samym układzie na każdym λ (`qem/folding.py`):
  - `genuine`: U(U†U)^k;
  - `identity`: wstawione pary CZ·CZ i PRX(θ)PRX(−θ) na tych samych krawędziach, w liczbie dopasowanej do garbage;
  - `garbage`: U(V†U)^k, gdzie V ma szkielet CZ jak U, a losowe kąty PRX.
  - Transpilacja foldów wyłącznie w wariancie, który nie optymalizuje (bez scalania przez fold i bez kasowania CZ). Test, że liczba CZ i szkielet są identyczne dla wszystkich trzech wariantów przy każdym λ.
- **W_neg:** Richardson na prawdopodobieństwach każdego z 32 stanów, P̂(s) = Σₖ cₖ·Pₛ(λₖ); raportuj ułamek ujemnych, min P̂ i W_neg = Σ_{P̂<0} |P̂|. To samo na marginesach jednokubitowych. Skrypt `sim/calibrate_wneg_null.py` buduje rozkład zerowy W_neg dla naszych shotów w Aer (szum depolaryzujący, gdzie Richardson jest poprawny).
- **Podłoga f:** empiryczna wartość ⟨O⟩ dla garbage przy λ_max. Raportuj test śledzenia |Ê(0) − (c₁·E₁ + (1 − c₁)·f̂)|.
- Retencja znormalizowana do wartości idealnej |⟨O⟩(1)|/|O_ideal| oraz SNR = |⟨O⟩(λ_max)|/SE; usuń stare kryterium R > 0,3 jako regułę decyzyjną (zostaw jako kolumnę).
- **κ i podział Neymana** w `zne_shot_boundary.py`:
  - flaga `--allocation {uniform, neyman}`, gdzie nᵢ ∝ |cᵢ|·σᵢ, a σᵢ pochodzi z pilota;
  - przewidywanie κ_opt = (Σ|cᵢ|σᵢ/σ₁)² − 1;
  - zbiory węzłów {1,3}, {1,3,5}, {1,3,5,7};
  - wsparcie dla 45 powtórzeń.
  - **Akceptacja:** przy równych σ test daje κ_opt = 3,0 / 11,25 / 35,0, a κ (uniform) = 4,0 / 14,656 / 44,5625.

### P4. Poziom decyzji klasyfikatora (Scavino, arXiv:2607.02888)
- `analysis/decisions.py`:
  - **Zgodność decyzji:** sign⟨O⟩_mit = sign⟨O⟩_ideal dla każdego punktu, test McNemara raw vs metoda, analiza w przedziałach marginesu |O_ideal|. Granice przedziałów z modelu bezszumowego, ustalone przed kampanią.
  - **Ryzyko:** μ(x) = s(x)·⟨O⟩_mit(x), σ²(x) z bootstrapu shotów (dla CDR także bootstrap obwodów treningowych), R(x) = Φ(−μ/σ), D = średnia R(x). Kalibracja: przewidywane D wobec empirycznego, tolerancja 0,05.
  - **Test progu CDR:** t̂ = −b̂/â; sprawdź, czy wszystkie zmiany decyzji CDR vs raw leżą w (0, t̂).
- Ewaluacja na ≥ 200 punktach testowych z prawdziwego rozkładu `two_curves`, nie z rozkładu jednostajnego. Ustal, skąd brać dane: `qml_benchmarks.data.generate_two_curves` w `train_hard.py`. Jeśli pakietu nie ma, zapytaj.

### P5. Kontrola głębokości bez nowego modelu
- `qem/identity_insertion.py`: dla stałego L (zamrożony model star L3) wstawia k par CZ·CZ na wybranych krawędziach, żeby uzyskać 24/36/52 CZ przy niezmienionej funkcji obwodu. Wariant `idle_matched` dodaje opóźnienie (`delay`) o tym samym czasie trwania co wstawione CZ, tylko jeśli backend je obsługuje; jeśli nie, zapytaj.
- Zapisuj liczbę CZ, liczbę PRX i szacowany czas trwania (z czasów bramek w kalibracji). `analysis/depth_regression.py`: regresja log ε na te trzy zmienne.

### P6. DD z przeplotem
- `run_hardware.py --dd-ablation`: kolejność ABAB (DD-off, DD-on, DD-off, DD-on) w obrębie jednego okna, dwie sekwencje DD (jeśli `iqm-client` je udostępnia; jeśli nie, zapytaj) oraz obwód kontrolny z długą bezczynnością.
- **Akceptacja:** test, że harmonogram jest przeplatany i zapisany w manifeście.

### P7. Symulator skalibrowany do urządzenia
- `sim/device_model.py`: `build_noise_model(calibration_json, theta_zz, phi_z, eps_prx)`:
  - relaksacja termiczna z T1/T2 i czasów bramek;
  - depolaryzacja CZ i PRX dobrana tak, żeby łączna wierność bramki zgadzała się z RB/IRB z kalibracji;
  - asymetryczny błąd odczytu (e01, e10) dla każdego kubitu;
  - na CZ błąd koherentny exp(−iθ/2·Z⊗Z)·(RZ(φ)⊗RZ(φ)), na PRX nadrotacja ε.
  - Kalibracja z `collect_odra_calibration.py` (format JSON), mapowanie przez `PHYS`.
  - Punkt odniesienia: `spec/sim_cdr_variants_bench2.py` (stałe z ODRY 23.07).
- Backend `--sim-device <calibration.json>` dla wszystkich runnerów, przez tę samą ścieżkę kodu co sprzęt: ten sam `compile_native`, te same ramiona, ten sam zapis `counts.jsonl`.
- `sim/fit_coherence.py`: dopasowanie (θ, ε) metodą ABC (siatka θ ∈ {0; 0,01; 0,02; 0,03; 0,05}, ε ∈ {0; 0,005; 0,01}) do sprzętowych statystyk: r² bez twirlingu i iloraz błędu z twirlingiem. Kontrola predykcyjna na odłożonych punktach drabiny.
- Przenieś benchmark wariantów CDR ze `spec/` do `sim/bench_cdr_variants.py` z nowymi modułami. **Test regresyjny (slow):** w modelu koherentnym (θ = 0,05, φ = 0,03) przy 54 CZ wariant `spread`+`near_target`+twirl ma średni błąd mniejszy niż `twirl_native`+`shared_random` w ≥ 6/8 powtórzeń. Wartości referencyjne: 0,0190 wobec 0,0357.

### P8. Orkiestracja kampanii ODRA (tylko przygotowanie)
- `campaign/odra_window.py` zastępuje `overnight_odra.sh` dla nowej kampanii. Jedno wywołanie to jedno okno kalibracyjne:
  - drabina 12/27/36/54 CZ (star/linear/circular/all_to_all, L3) plus L6/L9/L13 bez routingu i identity insertion;
  - 24 punkty ewaluacyjne, stratyfikowane po |O_ideal|, identyczne we wszystkich oknach (zapisane w `campaign/eval_points.json`);
  - n_train = 20 (spread: 120), M = 6, S = 8192;
  - ramiona CDR: off_copies / twirl_logical / twirl_native / spread / spread_off × {shared_random, near_target} w podzbiorze ustalonym w pre-rejestracji;
  - ZNE {1,3,5} z kontrolami foldingu.
  - **Kolejność ramion losowana blokowo** w oknie (seed w manifeście), z odczytem `calibration_set_id` przed i po każdym jobie. Jeśli kalibracja zmieni się w trakcie, oznacz okno jako `split`.
  - `--resume` (kontynuacja z `counts.jsonl`).
- `--dry-run` wypisuje liczbę obwodów i shotów na ramię oraz szacowany czas przy ~5 s na obwód przy 8192 shotach (wartość z timingu `overnight_odra.sh`: 2176 obwodów w ~3,1 h). Jeśli okno przekracza 8 h, zaproponuj podział na noce.
- Osobne tryby: `--kappa` (12 i 36 CZ, 45 powtórzeń, uniform i neyman) oraz `--dd-ablation`.
- **Akceptacja:** pełne okno w `--sim-device` na 2 punktach drabiny przechodzi end-to-end. Dry-run dla pełnego okna drukuje budżet.

### P9. Analiza i pre-rejestracja
- `preregistration.md` w katalogu głównym:
  - hipotezy H1–H5 z `spec/QEM_luka_badawcza_i_plan_ODRA.md` (C1–C4, C7) oraz H6 = „spread < twirl_native przy równym budżecie” z `spec/QEM_Koster_Scavino_i_nowa_metoda_CDR.md` §3.4;
  - dla każdej: metryka, test, α z korektą Holma, kryterium sukcesu, liczba okien (≥ 12 w ≥ 10 dniach), reguły wykluczeń (okno `split`, awaria jobów), progi W_neg i SNR (z P3, ustalone w symulacji).
  - Na końcu instrukcja: `git tag prereg-v1` **przed** pierwszym oknem. Tagu nie twórz sam, to decyzja użytkownika.
- `analysis/primary.py`:
  - model mieszany `statsmodels` MixedLM na log ε z efektami stałymi ramię × CZ (oraz train_set × twirl dla H6) i losowymi wyrazami wolnymi dla okna i punktu;
  - cluster bootstrap po oknach (≥ 2000) dla ilorazów błędów;
  - bootstrap ilorazu wariancji między oknami (H2);
  - korekta Holma;
  - wyniki do `results/primary_*.csv`.
- `analysis/power.py`: symulacja mocy z wariancji z istniejących danych. Referencja: SD log-ilorazu 0,55 przy 4 punktach daje ~9 okien dla ilorazu 0,45 i ~15 okien dla 4× redukcji wariancji. Ma pokazać moc dla 24 punktów i 12 okien.
- `analysis/legacy_reanalysis.py` odtwarza z istniejących CSV:
  - pary twirl ON/OFF: 16/17, test znaków p = 2,7·10⁻⁴; ODRA 8/8 ze średnią geometryczną ilorazu 0,42, Garnet 8/9 z 0,59;
  - κ: {1,3} 3,54 ± 0,56 i 3,23 ± 0,58; {1,3,5} 14,42 ± 0,95 i 13,29 ± 1,73; {1,3,5,7} 48,1 ± 6,0.
  - Test, że te liczby wychodzą dokładnie.
- `figures/make_paper_figures.py`: rysunki z draftu (Fig. 1a–c i Fig. 2 z `spec/`), wyłącznie z plików w `results*/` i `runs/`.

### P10. Dokumentacja
- `README_campaign.md`: jak uruchomić dry-run, sim-device, okno, κ, DD i analizę; gdzie lądują dane; jak dodać kalibrację.
- Uzupełnij `DATA_NOTES.md` (P1) o znane problemy starszych danych:
  - DD-off zawsze przed DD-on;
  - 4 punkty ewaluacyjne;
  - wspólny zbiór treningowy;
  - placeholder `p_2q = 0.01` w nullu.

---

## Definicja ukończenia
1. `python -m pytest -q` przechodzi; `pytest -m slow` przechodzi w < 30 min na laptopie (10 rdzeni).
2. `python campaign/odra_window.py --dry-run --window-id test` drukuje budżet.
3. `python campaign/odra_window.py --sim-device spec/odra_cal_example.json --window-id sim1 --points optimal:star adverse:all_to_all` przechodzi end-to-end i zapisuje manifest, `counts.jsonl` oraz CSV.
4. `analysis/legacy_reanalysis.py` odtwarza liczby referencyjne z P9.
5. Na końcu przedstaw raport: lista commitów, co zmieniono w każdym runnerze, wyniki testów, wynik dry-run (liczba obwodów i czas na okno) oraz **lista pytań lub decyzji do podjęcia przez użytkownika** przed pierwszym oknem na ODRZE (np. σ dla near_target, które ramiona idą do pre-rejestracji, czy dzielić okno na dwie noce).

Zacznij od przeczytania `spec/*.md`, `cdr.py`, `run_garnet_twirl.py`, `run_odra_cdr.py`, `zne_dryrun.py`, `zne_shot_boundary.py`, `odra_backend.py` i `collect_odra_calibration.py`. Potem pokaż mi plan commitów P0–P10 (bez kodu) i poczekaj na akceptację.
