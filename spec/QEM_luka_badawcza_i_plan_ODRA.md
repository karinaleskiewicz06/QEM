# QEM: wyniki do publikacji, luka badawcza i plan doliczeń (ODRA 5 + symulator)

**Źródło danych:** github.com/karinaleskiewicz06/QEM, gałąź `month2-topology-port`, commit `81e0f97` (9.10.2026). Wszystkie liczby przeliczono z CSV. `final_raport.pdf` (skompilowany 8.09) ma tę samą strukturę co `final_raport.tex` w repozytorium; ani PDF, ani `.tex` nie zawierają wyników ODRY z gałęzi (twirling o1/o2, natywny, L6/9/13, κ{1,3,5,7}). Zip `QEM-main (1).zip` to gałąź `main` (kod z miesiąca 1, bez CSV) i nie wnosi danych.

## 1. Najważniejsze w skrócie

Najmocniejszy, już publikowalny wynik projektu: **twirling Pauliego przy dopasowanym budżecie pomiarów obniża błąd CDR na sprzęcie w 16 z 17 par** (ODRA 8/8, średnia geometryczna ilorazu 0,42; Garnet 8/9, 0,59; łącznie test znaków p = 2,7·10⁻⁴). W symulacji z szumem wyłącznie niekoherentnym efekt jest słaby (10/15, iloraz 0,86), a z błędem koherentnym silny (15/15, 0,33). Drugi wynik: **stała wariancyjna ZNE κ zależy tylko od węzłów ekstrapolacji**, co potwierdzono dla trzech zbiorów węzłów na dwóch urządzeniach. Wymaga to jednak przeramowania jako eksperymentalnej walidacji teorii [Scavino Alfaro 2026](https://arxiv.org/abs/2605.08251).

W literaturze 2021–2026 nie znalazłam sprzętowego testu, czy twirling jest warunkiem poprawnego działania CDR, przeprowadzonego z kontrolą budżetu pomiarów, wzdłuż kontrolowanej drabiny liczby CZ i z replikacją między oknami kalibracji. Nie ma też wspólnej, przewidywalnej z wielkości mierzonych przed kampanią mapy reżimów raw / ZNE / CDR / CDR+twirl dla jednego obciążenia. To jest proponowana luka (§5).

Przegląd kodu ujawnił trzy nowe, tanie do naprawienia problemy (§4):
- wszystkie punkty ewaluacyjne dzielą 9 z 10 obwodów treningowych CDR;
- twirling natywny po scaleniu bramek 1q przestaje mieć narzut; sprawdziłam to obliczeniowo;
- obecne obwody bez twirlingu mają około 2× więcej bramek PRX, niż to konieczne.

![Rys. 1](fig_main_qem_odra.png)

**Rys. 1.**
- **(a)** Błąd CDR z twirlingiem wobec błędu bez twirlingu, przy równej łącznej liczbie pomiarów. Punkt to para (punkt drabiny × okno kalibracyjne); linia przerywana: y = x. Dane: ODRA 2 okna × 4 punkty, Garnet 3 × 3, ODRA natywny 1 × 4, symulacja niekoherentna 5 × 3.
- **(b)** Stała κ zmierzona (wyraz wolny regresji, 95% CI) wobec przewidywanej przy równym podziale pomiarów (kreska) i przy optymalnym podziale Neymana (romb, do zmierzenia na ODRZE). G = Garnet, O = ODRA, liczba = CZ.
- **(c)** Liczba bramek PRX w obwodzie po routingu na gwieździe 5q (Qiskit 2.5.2, `optimization_level=1`), przed scaleniem bramek 1q i po nim. Twirling natywny: średnia z 6 losowań. Wartości idealne ⟨Zᵢ⟩ są identyczne we wszystkich wariantach (maks. odchylenie 0,0).

---

## 2. Wyniki publikowalne (dane z CSV)

### 2.1 Twirling przy dopasowanym budżecie poprawia CDR (rdzeń pracy)

| seria | pary | ε spadł | p (znaki) | p (Wilcoxon, log-iloraz) | mediana ε_ON/ε_OFF | śr. geom. | śr. Δr² |
|---|---|---|---|---|---|---|---|
| ODRA, twirl logiczny (o1, o2; 8192 shotów) | 8 | 8 | 0,0078 | 0,0078 | 0,44 | 0,42 | +0,127 |
| Garnet, twirl logiczny (w1–w3; 1024) | 9 | 8 | 0,039 | 0,012 | 0,66 | 0,59 | +0,053 |
| ODRA, twirl natywny (o1n, bez scalania) | 4 | 3 | 0,63 | — | 0,93 | 0,93 | −0,050 |
| symulacja, tylko niekoherentny | 15 | 10 | 0,30 | 0,28 | 0,92 | 0,86 | −0,008 |
| symulacja, koherentny θ = 0,05 | 15 | 15 | 6·10⁻⁵ | 6·10⁻⁵ | 0,32 | 0,33 | +0,136 |
| symulacja, koherentny θ = 0,10 | 9 | 9 | 0,0039 | 0,0039 | 0,36 | 0,30 | +0,404 |

Przykład z ODRY, all_to_all 57 CZ, okno o2: ε 0,0987 → 0,0128. Pełna tabela: [twirl_pairs_recomputed.csv](twirl_pairs_recomputed.csv).

**Co jest mocne:** dopasowanie budżetu (ramię OFF uśrednia M = 6 kopii), dwa urządzenia, dwie kontrole symulacyjne o przeciwnych wynikach.

**Co trzeba uczciwie napisać:**
- Jednostką jest para (punkt drabiny × okno), a ε to średnia z zaledwie 4 punktów ewaluacyjnych.
- Pary z tego samego okna nie są niezależne.
- Twirl logiczny nie owija CZ pochodzących ze SWAP-ów.
- Symulacja niekoherentna także daje lekki zysk (0,86). Twirling „paulizuje” również nieunitalne tłumienie T1, więc nie każdy zysk oznacza koherencję. Porównanie trzeba robić wobec nulla, a nie wobec 1.

### 2.2 Granica opłacalności ZNE przy skończonym budżecie (walidacja teorii)

| węzły | urządzenie, punkt | κ przewidziane (równy podział) | κ zmierzone | S* | powt. |
|---|---|---|---|---|---|
| {1,3} | Garnet, star 12 CZ | 4,00 | 3,54 ± 0,56 | 197 | 12 |
| {1,3} | Garnet, star 36 CZ | 4,00 | 3,23 ± 0,58 | 76 | 12 |
| {1,3,5} | Garnet, star 12 CZ | 14,66 | 14,42 ± 0,95 | 847 | 12 |
| {1,3,5} | Garnet, star 48 CZ | 14,66 | 13,29 ± 1,73 | 291 | 12 |
| {1,3,5,7} | ODRA, star 12 CZ | 44,56 | 48,1 ± 6,0 | 1160 | 5 |

κ = |Λ|·Σcᵢ² − 1 wynika z propagacji wariancji przy niezależnych pomiarach. Wkładem nie jest więc „przewidywanie fizyczne”, tylko walidacja na sprzęcie, że pomiary są niezależne i nie dryfują w skali kampanii, oraz reguła praktyczna: {1,3} obniża S* około 4× względem {1,3,5}. Formalizm granicy, łącznie z optymalnym podziałem pomiarów (Remark 3), opisał [Scavino Alfaro 2026](https://arxiv.org/abs/2605.08251). Optymalizację współczynników Richardsona pod kątem wariancji wcześniej przeanalizowali [Krebsbach i in. 2022](https://doi.org/10.1103/physreva.106.062436). Punkt ODRA all_to_all (κ = 41 ± 49) jest nieinformatywny.

### 2.3 Koszt routingu: błąd rośnie z CZ, zysk ZNE jest największy przy najtańszym obwodzie

ODRA, 100 punktów, 8192 pomiarów, n_train = 100 (`odra_full_100pt.csv`):

| wzorzec | CZ | ε raw | ε ZNE{1,3,5} | ε CDR | r² CDR | zysk ZNE | zysk CDR |
|---|---|---|---|---|---|---|---|
| star | 12 | 0,0745 | 0,0226 | 0,0267 | 0,958 | 3,30× | 2,79× |
| linear | 27 | 0,1496 | 0,0895 | 0,0712 | 0,809 | 1,67× | 2,10× |
| circular | 36 | 0,1863 | 0,1416 | 0,1050 | 0,792 | 1,32× | 1,77× |
| all_to_all | 54 | 0,2776 | 0,2188 | 0,2198 | 0,598 | 1,27× | 1,26× |

Powtórzenie CDR w osobnym przebiegu (`odra_cdr_100pt.csv`) daje to samo: ε_CDR 0,023 / 0,071 / 0,088 / 0,205. Na ODRZE przecięcie ZNE i CDR leży między 12 a 27 CZ. Nie ma tu konfuzji „dwie kampanie” jak na Garnecie, bo oba ramiona pochodzą z tego samego przebiegu.

### 2.4 Uwaga poboczna: REM nie zmienia decyzji klasyfikatora

Ten wynik jest publikowalny jako jedno zdanie i dobrze wiąże się z teorią [Scavino 2026](https://arxiv.org/abs/2607.02888) o rozjeździe dokładności i decyzji.

---

## 3. Wyniki „cool”, ale z metodologią do poprawy, oraz co doliczyć (tylko ODRA + symulator)

Dla każdego punktu: stan, problem, doliczenie, kryterium sukcesu. Szacunek czasu: krok twirlingu logicznego w `overnight_odra.sh` to 2176 obwodów × 8192 pomiarów w ~3,1 h, czyli **~5 s na obwód**. Wszystkie budżety poniżej wynikają z tej liczby.

### C1. Twirled-CDR: z 4 punktów do porządnego eksperymentu (najwyższy priorytet)
- **Stan:** 8/8 na ODRZE, ale 2 okna × 4 punkty ewaluacyjne, a obwody treningowe są wspólne (§4.1).
- **Doliczyć na ODRZE:**
  - ≥ 12 okien w ≥ 10 różnych dniach (przy dobowej rekalibracji ~12 dni), z zapisem ID kalibracji przy każdym jobie (`collect_odra_calibration.py`);
  - 24 punkty ewaluacyjne stratyfikowane względem |⟨O⟩_ideal|, takie same w każdym oknie;
  - n_train = 20, z niezależnym losowaniem i obwodami prawdziwie near-Clifford (§4.1);
  - ramiona OFF(M = 6) / logiczny / natywny ze scalaniem, w kolejności losowanej blokowo w obrębie okna;
  - drabina 12/27/36/54 CZ oraz L6/L9/L13 bez routingu.
- **Koszt:** ~670 obwodów × 7 punktów ≈ 4700 obwodów ≈ 6,5 h na okno.
- **Analiza:** model mieszany na log(ε) per punkt ewaluacyjny: efekty stałe ramię × CZ, losowe okno i punkt; bootstrap z zapisanych zliczeń.
- **Moc:** przy obecnym SD log-ilorazu (0,55 przy 4 punktach) wykrycie ilorazu 0,74 w pojedynczym punkcie drabiny wymaga ~41 okien, a ilorazu 0,6 ~17 okien (α = 0,0125). Dla efektu bliskiego obecnemu (iloraz 0,42, log = −0,87) wystarczy ~9 okien nawet przy obecnym SD; 24 punkty ewaluacyjne na okno dodatkowo obniżają SD, więc 12 okien daje zapas na słabszy efekt w punktach o wysokim CZ.
- **Kryterium:** iloraz < 1 z 95% CI wykluczającym 1 w co najmniej 3 z 4 punktów drabiny, oraz istotnie mniejszy niż w nullu symulacyjnym skalibrowanym do ODRY (C5).

### C2. Twirling stabilizuje CDR wobec dryfu
- **Stan:** na Garnecie SD ε między oknami spada z 0,016–0,023 do 0,005–0,008. Na ODRZE (2 okna) efektu nie ma: SD po twirlingu przy 30 i 57 CZ jest większe (0,021 i 0,038 wobec 0,0006 i 0,007).
- **Doliczyć:** dane z C1 (te same okna).
- **Moc:** test F na ilorazie wariancji 0,25 wymaga ~15 okien przy 80% mocy.
- **Kryterium:** iloraz wariancji międzyokiennej < 1 (bootstrap). Jeśli wynik będzie zerowy, to też jest wynik: dryf na ODRZE nie jest koherentny.

### C3. Twirling natywny po poprawce
- **Stan:** wynik negatywny (3/4, iloraz 0,93), ponieważ implementacja wstawia Pauli jako osobne PRX.
- **Poprawka (zrobiona obliczeniowo, [merge_prx_native_twirl.py](merge_prx_native_twirl.py)):** bramki 1q między kolejnymi CZ łączymy w jedną PRX, a RZ przesuwamy przez CZ (komutuje) i odrzucamy przed pomiarem w bazie Z. Wyniki ([native_twirl_merge_check.csv](native_twirl_merge_check.csv)):

| wzorzec | CZ | PRX: OFF obecny | OFF scalony | natywny obecny | natywny scalony |
|---|---|---|---|---|---|
| star | 12 | 40 | 20 | 92 | 24,8 |
| linear | 24 | 84 | 50 | 178 | 51,5 |
| circular | 36 | 119 | 75 | 261 | 75,8 |
| all_to_all | 54 | 130 | 63 | 356 | 85,7 |

- **Doliczyć na ODRZE:** ramię natywne scalone w C1. Wszystkie ramiona (także OFF) przepuścić przez to samo scalanie, żeby porównanie było uczciwe.
- **Kryterium:** iloraz natywny ≤ logiczny.
- **Uwaga:** samo scalanie bramek 1q może obniżyć błąd raw na całej drabinie. To ważna kontrola przed porównaniem z danymi historycznymi; nowe i stare dane nie są porównywalne.

### C4. Okno ZNE: dolna granica (κ, podział Neymana) i górna granica (zanik sygnału)
- **Stan:** κ zgodne z przewidywaniem; ODRA ma tylko 5 powtórzeń. Kryterium retencji R przepuszcza punkty, w których sygnał leży na podłodze (ODRA circular 39 CZ: R = 0,81 / 0,67 przy |⟨O⟩(1)| = 0,04).
- **Doliczyć na ODRZE (tanie, 1 obwód × wiele powtórzeń):**
  - κ dla {1,3}, {1,3,5}, {1,3,5,7} w dwóch punktach (12 i 36 CZ), 45 powtórzeń (SE κ ≈ 2);
  - podział równy oraz podział Neymana nᵢ ∝ |cᵢ|σᵢ, z przewidywaniem κ_opt = (Σ|cᵢ|σᵢ/σ₁)² − 1. Przy równych σ daje to 3,0 / 11,25 / 35,0 wobec 4,0 / 14,66 / 44,56;
  - kontrola „garbage folding” [Köster i Mauerer 2026](https://arxiv.org/abs/2607.09360) w każdym punkcie drabiny;
  - zapis ⟨O⟩ dla każdej skali.
- **Symulator:** retencja znormalizowana do ideału |⟨O⟩(1)|/|⟨O⟩_ideal| oraz SNR = |⟨O⟩(λ_max)|/SE. Próg zaniku ustalić *przed* kampanią na modelu skalibrowanym do ODRY.
- **Kryterium:** κ_opt zmierzone zgodne z przewidywanym (95% CI), S* skaluje się jak B⁻². Górna granica okna przewidziana z SNR, przy której ZNE przestaje bić garbage-folding.

### C5. Mechanizm: ile koherencji jest w szumie ODRY (symulator, bez kosztu QPU)
- **Stan:** null ma placeholderową kalibrację (`p_2q = 0.01`), a kontrola pozytywna jest wyłącznie koherentna. Modele nie są zagnieżdżone, a „θ ≈ 0,02–0,03 rad” jest nieuprawnione.
- **Doliczyć:**
  - model szumu z kalibracji ODRY dla każdego okna (T1, T2, PRX/CZ z RB, macierz odczytu, czas bramek), z dodanym ZZ-fazą θ na CZ i nadrotacją ε na PRX;
  - siatka θ ∈ {0; 0,01; 0,02; 0,03; 0,05}, ten sam protokół co na sprzęcie (shoty, n_train, punkty, M);
  - dopasowanie θ do sprzętowych (r²_OFF, iloraz twirlingu) metodą ABC lub największej wiarygodności, z kontrolą predykcyjną na odłożonych punktach drabiny.
- **Kryterium:** jeden θ wyjaśnia jednocześnie spadek r² i zysk z twirlingu. Dopiero wtedy zdanie „r² jest sondą koherencji” jest obronione. Uzupełniająco można odnieść się do pomiaru unitarności na IQM Spark ([Figueroa-Romero i in. 2024](https://arxiv.org/abs/2409.02110)).

### C6. Liczba CZ, bramki 1q czy czas: co napędza degradację
- **Stan:** obwody bez routingu na ODRZE degradują się co najmniej tak szybko jak z routingiem (r² 0,827 / 0,719 / 0,444 przy 24/36/52 CZ wobec 0,809 / 0,792 / 0,598 przy 27/36/54).
- **Problem:** modele L6/9/13 to inne wytrenowane klasyfikatory, z innymi wartościami idealnymi, inną liczbą PRX i innym czasem trwania.
- **Doliczyć na ODRZE:** to samo L, a różna liczba CZ uzyskana przez wstawienie par CZ·CZ = I (identity insertion) zamiast nowego modelu, plus wariant z bezczynnością o tym samym czasie trwania. Regresja log(ε) na CZ, PRX i czas.
- **Kryterium:** rozdzielony wkład trzech składowych z przedziałami ufności.

### C7. Poziom decyzji klasyfikatora
- **Stan:** accuracy raw przekracza idealną (Garnet 96 CZ: 0,78 wobec 0,767; Banknote 5/9), więc accuracy nie mierzy mitygacji.
- **Doliczyć na ODRZE:** ≥ 200 punktów testowych, zgodność znaków sign⟨O⟩_mit = sign⟨O⟩_ideal, test McNemara raw vs metoda, analiza w funkcji marginesu |⟨O⟩_ideal|. To bezpośredni sprzętowy test tezy [Scavino 2026](https://arxiv.org/abs/2607.02888), że CDR może poprawiać MSE i nie zmieniać decyzji.
- **Kryterium:** wzrost zgodności istotny tylko dla punktów o małym marginesie (przewidywanie z teorii).

### C8. DD jako wynik negatywny
- **Stan:** DD pogarsza błąd we wszystkich 4 punktach, ale DD-off zawsze szło przed DD-on, a wzorzec circular był rozdzielony na dwa dni.
- **Doliczyć na ODRZE:** przeplot ABAB w jednym oknie, dwie sekwencje DD i obwód kontrolny z długą bezczynnością, w którym DD powinno pomagać ([Ezzell i in. 2023](https://doi.org/10.1103/physrevapplied.20.064027)).
- **Kryterium:** kara utrzymuje się przy przeplocie.

### Poza zakresem (tylko Garnet / Emerald, bez możliwości doliczenia)
[[4,2,2]] na Garnecie i Emerald zostają jako dane istniejące. Garnet służy w artykule jako urządzenie replikacyjne dla C1 i κ. Wyniki z Emeralda (1 okno, 4 punkty) najlepiej przenieść do suplementu albo pominąć. Na marginesie: gwiazda ODRY (hub + 4 liście) naturalnie mierzy stabilizator wagi 4 przez hub, co wykazano na architekturze star IQM ([Vigneau i in. 2025](https://doi.org/10.1103/8m33-wn4g)). To możliwy osobny projekt, ale nie ta praca.

---

## 4. Problemy w kodzie i tanie poprawki

1. **Wspólne obwody treningowe CDR.** `near_clifford_training_circuits(target, seed=args.seed)` z tym samym ziarnem daje obwody 1..9 identyczne dla wszystkich celów; sprawdzone w Qiskit 2.5.2, różni się tylko obwód 0. Do tego obwody 1..9 przypisują *każdemu* obrotowi losowy kąt Clifforda, więc są to losowe obwody Clifforda o tym samym szkielecie, a nie „near-Clifford” w sensie [Czarnik i in. 2021](https://doi.org/10.22331/q-2021-11-26-592). Konsekwencje: dopasowania dla różnych punktów są silnie skorelowane, rozkład treningowy nie jest blisko celu, a r² mierzy dopasowanie na losowych Cliffordach. **Poprawka:** ziarno zależne od punktu; zamiana na Clifford tylko części obrotów (np. połowy, z prawdopodobieństwem malejącym z odległością kąta); n_train ≥ 20; raportowanie, czy zbiór jest wspólny.
2. **Narzut twirlingu natywnego:** §3, C3, zrobione.
3. **Nadmiarowe bramki 1q we wszystkich obwodach:** `optimization_level=1` zostawia 2× więcej PRX niż po scaleniu. Ta sama funkcja `merge_prx` obniża głębokość każdego ramienia.
4. **Rozbieżność liczby CZ:** w Qiskit 2.5.2 linear daje 24 CZ, a w CSV 27; circular 36 w `odra_full_100pt`, a 39 w kampanii twirlingowej. **Poprawka:** przypiąć wersję Qiskit i `seed_transpiler`, zapisywać QASM obwodu transpilowanego razem z ID joba.

   > **Sprostowanie (zweryfikowane na Qiskit 2.4.1, gałąź `paper-odra-campaign`).** To nie jest
   > dryf wersji, tylko **dwie ścieżki transpilacji w jednym repozytorium**. Na 2.4.1:
   > ścieżka ze stałym układem `[0,1,2,3,4]` i `seed_transpiler=42` (używana przez
   > `run_garnet_twirl.py`) daje **12 / 30 / 39 / 57** CZ, co odtwarza drabinę kampanii
   > twirlingowej; `zne_dryrun.native_transpile` (używany przez `run_odra_cdr.py`, bez
   > `initial_layout` i bez `seed_transpiler`) daje **12 / 27 / 36 / 54**, co odtwarza
   > `odra_full_100pt.csv`. Obie liczby wychodzą z tej samej wersji, każda ze swojej ścieżki.
   > Na 2.5.2 ścieżka ze stałym układem daje 12 / 27 / 36 / 54, więc nie odtwarza 39 — co
   > czyni 2.4.1 wersją zgodną z danymi kampanii. Szczegóły i pomiary: `DATA_NOTES.md`.
5. **Brak surowych zliczeń per punkt:** CSV zawierają tylko średnie, więc nie da się policzyć przedziałów ufności. **Poprawka:** zapisywać `counts.json` dla każdego obwodu. Na ODRZE to tylko kilka MB na okno.
6. **Kolejność ramion:** losowanie blokowe w obrębie okna (dotyczy DD i twirlingu).
7. **Pre-rejestracja:** przed kampanią C1–C4 zrobić tag w gicie z plikiem hipotez, kryteriów i analizy. Tylko wtedy wolno użyć słowa „pre-registered”.

---

## 5. Literatura i luka badawcza

### Co jest ustalone
- CDR uczy liniowej mapy z obwodów bliskich Cliffordowi ([Czarnik i in. 2021](https://doi.org/10.22331/q-2021-11-26-592)).
- Uogólnienia łączą CDR z ZNE ([Lowe i in. 2021](https://doi.org/10.1103/physrevresearch.3.033098)).
- Porównania metod pokazują, że ranking zależy od budżetu pomiarów, ale głównie w symulacji z modelem szumu ([Bultrini i in. 2023](https://doi.org/10.22331/q-2023-06-06-1034)). Oszczędniejszy wariant CDR testowano na IBM Toronto ([Czarnik i in. 2025](https://doi.org/10.22331/q-2025-05-05-1727)).
- Na sprzęcie CDR wypadało lepiej niż ZNE dla dynamiki 9 kubitów ([Sopena i in. 2021](https://arxiv.org/abs/2103.12680)).
- Twirling i randomized compiling przekształcają błąd koherentny w stochastyczny Pauliego ([Wallman i Emerson 2016](https://doi.org/10.1103/physreva.94.052325)), co zademonstrowano na procesorze nadprzewodzącym ([Hashim i in. 2021](https://doi.org/10.1103/physrevx.11.041039)).
- Synergię RC z ZNE pokazano numerycznie dla VQE ([Kurita i in. 2023](https://doi.org/10.22331/q-2023-11-20-1184)).
- Twirling jest standardowym elementem eksperymentów skali utility ([Kim i in. 2023](https://doi.org/10.1038/s41586-023-06096-3); [van den Berg i in. 2023](https://doi.org/10.1038/s41567-023-02042-2)).

### Co jest nowe w 2026 i bliskie projektowi
Granicę help–harm ZNE przy skończonym budżecie wyprowadzono teoretycznie i sprawdzono w Aer oraz na pojedynczych testach IBM ([Scavino Alfaro 2026](https://arxiv.org/abs/2605.08251)). Wcześniejsze prace dotyczyły optymalizacji Richardsona ([Krebsbach i in. 2022](https://doi.org/10.1103/physreva.106.062436)) i fundamentalnych ograniczeń kosztu mitygacji ([Takagi i in. 2022](https://doi.org/10.1038/s41534-022-00618-z); [Quek i in. 2024](https://doi.org/10.1038/s41567-024-02536-7)). [Köster i Mauerer 2026](https://arxiv.org/abs/2607.09360) pokazali na sprzęcie IQM artefakt ZNE przy zaniku sygnału i kontrolę „garbage folding”. [Scavino 2026](https://arxiv.org/abs/2607.02888) wykazał teoretycznie i w symulacji, że poprawa MSE nie musi poprawiać decyzji. Ten sam rozjazd widać w danych projektu: REM nie zmienia żadnej decyzji, a accuracy surowa bywa wyższa od idealnej. Prace z obszaru QML ograniczają się zwykle do symulacji ([Njiki i in. 2026](https://arxiv.org/abs/2604.17515); [Adermann i in. 2025](https://arxiv.org/abs/2504.06775)).

### Czego nie znalazłam (luka)
Żadna z przejrzanych prac nie mierzy na sprzęcie, czy twirling poprawia CDR **przy równym budżecie pomiarów**. Bez tej kontroli zysk z twirlingu jest nieodróżnialny od zysku z uśredniania M razy większej liczby pomiarów. Żadna nie śledzi tego wzdłuż kontrolowanej drabiny liczby CZ jednego zamrożonego obciążenia, z replikacją między oknami kalibracji, ani nie zestawia na tym samym urządzeniu i obciążeniu trzech granic: dolnej granicy ZNE (κ, S*), górnej granicy ZNE (zanik sygnału vs garbage folding) i granicy liniowości CDR (z twirlingiem i bez).

> **Luka:** brakuje sprzętowego, kontrolowanego budżetem pomiarów testu tego, czy i od jakiej liczby bramek CZ twirling Pauliego jest warunkiem koniecznym poprawnego działania regresji danych Clifforda. Brakuje też mapy reżimów raw / ZNE / CDR / CDR+twirling dla jednego obciążenia na jednym procesorze, której granice da się przewidzieć z wielkości zmierzonych przed kampanią (κ z węzłów, V i B z pilota, θ z modelu skalibrowanego do urządzenia) i która jest powtarzalna między oknami kalibracji.

**Pytania badawcze:**
- **RQ1:** Czy przy równym budżecie twirling logiczny i natywny obniżają błąd CDR na ODRZE i jak efekt zależy od CZ?
- **RQ2:** Czy twirling zmniejsza wariancję błędu CDR między oknami kalibracji?
- **RQ3:** Czy granice okna ZNE (κ przy podziale równym i Neymana, zanik sygnału) są przewidywalne przed kampanią?
- **RQ4:** Czy poprawa ⟨O⟩ przekłada się na zgodność decyzji z modelem bezszumowym i dla jakich marginesów?

**Zagrożenia dla nowości:**
- Oczywistość „twirling + CDR”: kontrargument to brak danych sprzętowych z dopasowaniem budżetu i pokazanie pozornego zysku bez dopasowania.
- Prace Scavino i Köstera mogą zostać opublikowane z rozszerzeniami. Pozycjonujemy się jako eksperymentalna walidacja, a nie konkurencja.
- Ogólne studia IBM o budżecie i ZNE ([Chongder 2026](https://arxiv.org/abs/2608.28535)) nie obejmują CDR ani twirlingu z kontrolą budżetu.

Pełna lista zweryfikowanych pozycji: [literatura_zweryfikowana.csv](literatura_zweryfikowana.csv).

---

## 6. Gdzie publikować

| miejsce | typ | termin (2027) | dopasowanie |
|---|---|---|---|
| IEEE QCE 2027 (Quantum Week) | konferencja, pełny artykuł | prawdopodobnie kwiecień 2027; w latach 2023–2026 było to 31.03–22.04 | **najlepsze dopasowanie** (benchmarki mitygacji, IQM, tam publikowali Giurgica-Tiron i Majumdar) |
| QCE 2027, sesja posterowa | 2-stronicowy abstrakt | ~czerwiec 2027 (wzorzec 2026) | wersja wstępna przy niepełnych danych |
| IEEE Transactions on Quantum Engineering | czasopismo | ciągły | tam ukazały się Russo i in. (2023) i Pelofske i in. (2022) |
| Quantum | czasopismo (open access) | ciągły | tam ukazały się CDR, UNITED i RC+ZNE; wymaga mocnej części teoretycznej i C5 |
| EPJ Quantum Technology / Quantum Sci. Technol. | czasopismo | ciągły | bezpieczny wybór dla pracy eksperymentalno-metodologicznej |
| QTML 2027 | konferencja QML | do sprawdzenia | tylko jeśli główną osią będzie C7 (decyzje klasyfikatora) |

Terminów na 2027 nie da się jeszcze potwierdzić; daty QCE to ekstrapolacja z poprzednich edycji. Rekomendacja: przy 12 oknach na ODRZE w listopadzie–grudniu 2026 i analizie do lutego, **QCE 2027 (pełny artykuł) i równolegle wersja rozszerzona do IEEE TQE**.

---

## 7. Kolejność prac (sugerowana)

1. Kod (bez QPU, 1–2 dni): poprawki z §4 (1, 3–6), funkcja `merge_prx` w potoku, plik pre-rejestracji z tagiem w gicie.
2. Symulator (C5, C4-próg): model ODRY z kalibracji, siatka θ, symulacja mocy dla C1 z docelowym protokołem.
3. ODRA, noc pilotażowa: C4 (κ, Neyman, garbage folding) i C8 (DD przeplot). Tanie i szybkie.
4. ODRA, 12 okien: C1 + C2 + C3 + C6 (wspólny protokół ~6,5 h na noc), plus C7 dołączone do co trzeciego okna.
5. Analiza i draft ([draft_artykul_QEM_ODRA.md](draft_artykul_QEM_ODRA.md)).
