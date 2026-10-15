# Köster & Mauerer, Scavino oraz propozycja ulepszonego CDR z twirlingiem

Uzupełnienie do [QEM_luka_badawcza_i_plan_ODRA.md](QEM_luka_badawcza_i_plan_ODRA.md). Szczegółowe notatki z pełnych tekstów: [Köster i Mauerer](koster_mauerer_2607.09360_notatki.md), [Scavino, decision kernels](notatki_Scavino_2607.02888_decision_kernels.md), [przegląd nowości pomysłów](notatki_nowosc_CDR_twirling.md).

## 1. Köster i Mauerer 2026: artefakt ZNE na sprzęcie IQM

**Co pokazują.** Gdy wartości przy skalach λ > 1 spadają do „podłogi” obserwabli f (dla parzystości f = 0), liniowa ekstrapolacja Richardsona przestaje cokolwiek ekstrapolować. Staje się stałym przeskalowaniem jednego pomiaru: Ê(0) = c₁·E(λ₁) + (1 − c₁)·f. Dla węzłów {1,3,5} jest to 15/8·E(1) − 7/8·f (ich równ. 2). Pozorna poprawa nie zależy więc od wzmacniania szumu i pojawia się nawet przy foldingu, który niczego nie wzmacnia ([arXiv:2607.09360](https://arxiv.org/abs/2607.09360), v2 z 3.08.2026, 4 strony, przyjęta na IEEE QCE 2026).

**Sprzęt i liczby.** IQM Euro-Q-Exa (54 kubity, LRZ): 4-kubitowy obwód Trottera na łańcuchu 8–11, obserwabla ⟨Z⊗⁴⟩, skale {1,3,5}, 4096 shotów.
- Przy głębokości d = 1 sygnał jest zachowany i Richardson odtwarza wartość idealną.
- Przy d = 3 i 5 wynik pokrywa się z czystym przeskalowaniem 15/8·E(1) z dokładnością 5%. Przy d = 3 przestrzela wartość idealną o 21% (1,16 wobec 0,96).
- **Kontrola „garbage folding”**: foldy U(V†U) ≠ U, dopasowane liczbą CZ i błędem, które nie niosą sygnału. Na sprzęcie dały *większą* pozorną poprawę niż prawdziwy folding: ρ = 2,77 ± 0,25 wobec 0,99 ± 0,13.
- **Darmowy wskaźnik W_neg**: Richardsona stosuje się do prawdopodobieństwa każdego stanu bazowego i sumuje ujemne wyniki. Prawidłowy folding daje 0,02–0,04, garbage 0,74 ± 0,06; rozdzielenie jest pełne (AUC = 1,0 na 405 przebiegach).
- **Lista kontrolna:** (1) czy E(λ > 1) niesie jeszcze sygnał, (2) raportować W_neg obok Ê(0), (3) oznaczać przestrzelenia wartości fizycznie osiągalnej.

**Ograniczenia.** Jedno urządzenie, jedna rodzina obwodów. Konstrukcja garbage-foldu jest tylko w pakiecie reprodukcyjnym. Brak liczbowego progu „blisko podłogi”. Nie omawiają szumu nieunitalnego (T1), który dla ⟨Z⟩ przesuwa podłogę f w stronę +1.

**Co to znaczy dla nas.**
- Najbardziej zagrożone są wyniki ZNE przy 36–57 CZ na ODRZE. Przy 39 CZ |⟨O⟩(1)| = 0,04, więc nawet λ = 1 leży na podłodze, a λ = 5 to ~195 CZ. Zysk 1,27× przy 54 CZ może być w całości przeskalowaniem 15/8. Zysk 3,3× przy 12 CZ najpewniej jest prawdziwy, ale musi przejść te same testy.
- Dla naszej obserwabli mean-Z podłoga f ≠ 0 z powodu T1. Trzeba ją zmierzyć (np. z garbage-foldu przy λ = 5), a nie zakładać f = 0.
- **Tanie poprawki:** usunąć z kodu ciche przełączanie na fit liniowy przy |EV| > 1,25 (ukrywa przestrzelenia, łamie punkt 3 listy) albo przynajmniej je logować. Liczyć W_neg na marginesach jednokubitowych. Rozkład zerowy W_neg skalibrować w symulatorze dla 32 stanów i naszej liczby shotów.
- **Na ODRZE:** w każdym punkcie drabiny prawdziwy folding, folding identycznościowy (pary CZ·CZ) i garbage folding przy tej samej liczbie CZ i tym samym układzie, w przeplocie. Zysk ZNE uznajemy tylko wtedy, gdy prawdziwy folding bije garbage i identyczność, a W_neg mieści się w rozkładzie zerowym.
- **Pozycjonowanie:** praca sama oddziela ten mechanizm od granicy help–harm Scavino Alfaro. My mierzymy obie granice okna ZNE: dolną (κ, skończona liczba shotów) i górną (zanik sygnału) na jednym urządzeniu i obciążeniu. Uwaga: to praca z QCE 2026, a my celujemy w QCE 2027, więc trzeba wyraźnie zaznaczyć, co dokładamy.

## 2. Scavino 2026: lepsza dokładność ≠ lepsze decyzje

**Co pokazuje.** Jeśli wynik obliczenia służy tylko do decyzji niezmienniczych względem przesunięcia (argmin, ranking, top-k, akceptacja kroku optymalizatora), to o decyzji decyduje prawo różnic (gap law), a nie MSE. W reżimie gaussowskim to prawo opisują dwa obiekty: efektywny margines μ = Δ + L·a (bias różnic) i jądro decyzyjne Σ = L·K·Lᵀ. To ostatnie jest „przeciągnięciem” wspólnego szumu urządzenia przez mapę mitygacji, Σ = (LM)·C_dev·(LM)ᵀ ([arXiv:2607.02888](https://arxiv.org/abs/2607.02888), v1, 52 strony, preprint jednoautorski).

**Twierdzenia (w skrócie).**
- **Faktoryzacja przez iloraz:** dodanie stałej nie zmienia żadnej decyzji, a MSE może przy tym rosnąć bez ograniczeń.
- **Marginal no-go:** dwie metody o tych samych marginesach, przedziałach i MSE mogą mieć różne ryzyko decyzji. Metoda o mniejszym MSE może być wykładniczo gorsza decyzyjnie.
- **Wykładnik ryzyka argmin:** I = minᵢ μᵢ²/(2Σᵢᵢ). Odwrotne twierdzenie na poziomie shotów mówi, że przy stałym przydziale żadne przetwarzanie nie zrobi lepiej.
- **ZNE pomaga decyzjom wtedy i tylko wtedy, gdy** μ_ZNE²/Σ_ZNE > μ_raw²/Σ_raw.
- **CDR z mapą dodatnio-afiniczną** nie zmienia rankingu w ogóle.

**Wyniki (wyłącznie symulacja QAOA-MaxCut, Aer).**
- CDR poprawiło MSE 43–180×, a ryzyko decyzji pozostało *identyczne* jak dla raw.
- PEC poprawiało dokładność, a pogarszało ryzyko decyzji.
- Selektor „decision-aware” obniżył odsetek złych decyzji z 0,4635 do 0,4104 (−11%), poniżej progu praktycznego 15% ustalonego przed eksperymentem.
- Mikrotest na ibm_marrakesh nie spełnił kryterium, więc autor sam nie zgłasza tezy dla urządzenia.

**Autor.** Ta sama osoba co [arXiv:2605.08251](https://arxiv.org/abs/2605.08251) („Scavino Alfaro”, granica help–harm ZNE) i [arXiv:2606.21686](https://arxiv.org/abs/2606.21686) (okna działania PEC i CDR). Wniosek opiera się na tym samym koncie GitHub; arXiv nie łączy tych dwóch form nazwiska.

**Przełożenie na nasz klasyfikator.**
- Nasza decyzja to sign(⟨O⟩) ze stałym progiem 0, czyli formalnie *nie* jest niezmiennicza względem przesunięcia. Twierdzenie o faktoryzacji nas nie obejmuje. Zachowane jest tylko to, że dodatnie skalowanie bez offsetu nie zmienia decyzji.
- Wnioski praktyczne:
  - **CDR zmienia decyzje wyłącznie przez swój próg** t̂ = −b̂/â. Różnica decyzji CDR vs raw może wystąpić tylko dla punktów, których surowa wartość leży między 0 a t̂. To jest bezpośrednio testowalne na naszych parach z twirlingiem: czy niższy błąd CDR zmienił jakiekolwiek decyzje.
  - **ZNE przy czystej depolaryzacji** tylko skaluje wynik (o 15/8 dla {1,3,5}), więc nie może poprawić decyzji, a powiększa wariancję ~4×. Może pomóc wyłącznie tam, gdzie raw ma zły znak z powodu błędów nieskalujących (koherentnych, asymetrycznego odczytu).
  - **„REM nie zmienił żadnej decyzji”** zgadza się z teorią, jeśli błąd odczytu działa prawie jak czyste skalowanie.
- **Ryzyko z naszych danych:** dla punktu x margines μ(x) = s(x)·⟨O⟩_mit(x), gdzie s(x) = znak wartości idealnej. Wariancja σ² pochodzi z bootstrapu shotów, a dla CDR także z bootstrapu 10 obwodów treningowych. R(x) = Φ(−μ/σ), a oczekiwana niezgodność to D = średnia R(x). Trzeba to policzyć dla raw / ZNE / CDR / CDR+twirl.
- **Zagrożenie dla artykułu:** recenzent zapyta, czy 16/17 par z niższym błędem CDR przełożyło się na decyzje. Dlatego zgodność decyzji (C7 w raporcie głównym) trzeba raportować obok MSE.

## 3. Czy CDR z twirlingiem można jeszcze poprawić? Tak, w symulacji

### 3.1 Nowy problem w obecnym kodzie: obwody treningowe są inaczej zroutowane niż cel
Kampania 100-punktowa (`run_odra_cdr.py` → `native_transpile`) transpiluje każdy obwód osobno, bez `seed_transpiler` i bez stałego układu. W obwodach z routingiem **żaden z 10 obwodów treningowych nie ma tego samego szkieletu CZ co cel**: linear, circular i all_to_all mają 0/10 (all_to_all w jednym przypadku 1/10), star 10/10. Ten sam cel transpilowany 5 razy daje 5 różnych szkieletów. CDR uczy się więc szumu innych obwodów niż ten, który koryguje. Psuje to `odra_full_100pt`/`odra_cdr_100pt` i wyjaśnia starą rozbieżność „linear 24 vs 27 CZ”. Kampania twirlingowa (`run_garnet_twirl.py`, stały układ i seed 42) ma szkielety zgodne w 10/10, więc **wynik 16/17 jest czysty**.

**Poprawka (jedna linia):** transpilować cel raz i budować obwody treningowe na *obwodzie natywnym* (podmieniając kąty PRX na kąty Clifforda), zamiast transpilować je ponownie. Ewentualnie przynajmniej stały `initial_layout` i `seed_transpiler`.

### 3.2 Co przetestowałam
Symulator skalibrowany do ODRY z 23.07: T1/T2 i odczyt dla każdego kubitu, CZ 60 ns z depolaryzacją, PRX 20 ns. Dwa modele: null (bez błędu koherentnego) i koherentny (faza ZZ θ = 0,05 rad i Z 0,03 rad na każdym CZ). Drabina 12/27/36/54 CZ z prawdziwymi wagami `trained_models_hard`, 8192 shotów, M = 6, **równy budżet we wszystkich ramionach**, scalanie bramek 1q we wszystkich ramionach. Jednostka powtórzenia to „okno”: 8 powtórzeń × 8 punktów ewaluacyjnych; CI 95% z bootstrapu po powtórzeniach.

| pomysł | wynik | werdykt |
|---|---|---|
| wspólne ramki Pauliego dla treningu i celu | iloraz vs obecny twirl 0,96–1,15 (koh.), 0,94–1,17 (null) | brak zysku, porzucić |
| CDR osobno dla każdego Zᵢ | błąd 2–5× większy (Clifford daje ⟨Zᵢ⟩ ≈ 0, regresja źle uwarunkowana) | porzucić; per-term CDR jest zresztą znany (Czarnik i in. 2025) |
| korekta EIV nachylenia (szum shotów w x) | brak efektu przy ~49 tys. shotów (np. 54 CZ koh.: 0,0190 vs 0,0191) | ma sens tylko przy małym budżecie |
| zbiór treningowy bliski celowi (10 obwodów) | mieszany: 0,45 przy 12 CZ, ale 1,46 przy 36 CZ | sam nie wystarcza |
| **60 różnych obwodów × 1 ramka** | najlepszy we wszystkich punktach (tabela niżej) | **proponowana metoda** |

### 3.3 Proponowana metoda: twirled CDR z randomizowanym treningiem
**Idea.** Obecnie ramię z twirlingiem dla każdego celu uruchamia 10 obwodów treningowych × 6 ramek, a cel × 6 ramek (66 obwodów × S shotów). Przy *tym samym* budżecie proponuję 60 **różnych** obwodów treningowych, każdy z **jedną** losową ramką Pauliego, oraz cel z 6 ramkami. Obwody treningowe to Cliffordy losowane blisko celu: każdy kąt zastępowany kątem Clifforda z wagą exp(−d²/σ²), σ = π/4, osobno dla każdego celu. Uśrednianie po ramkach przenosi się z wnętrza punktu treningowego do samej regresji. Regresja dostaje 6× więcej różnych punktów, a ramki stają się zwykłym szumem w x.

Błąd CDR (średnia), iloraz względem obecnego potoku bez twirlingu i CI 95%:

| wariant (równy budżet) | 12 CZ | 27 CZ | 36 CZ | 54 CZ |
|---|---|---|---|---|
| **model koherentny** | | | | |
| obecny, bez twirlu | 0,0558 | 0,0281 | 0,0248 | 0,0879 |
| obecny + twirl | 0,0427 ×0,49 [0,32; 0,75] | 0,0126 ×0,44 [0,32; 0,61] | 0,0164 ×0,59 [0,46; 0,77] | 0,0357 ×0,33 [0,21; 0,52] |
| 60 obwodów, bez twirlu | 0,0163 ×0,39 [0,20; 0,68] | 0,0233 ×0,83 [0,74; 0,91] | 0,0171 ×0,71 [0,49; 1,00] | 0,0617 ×0,69 [0,59; 0,78] |
| **60 obwodów × 1 ramka** | **0,0083 ×0,21 [0,11; 0,37]** | **0,0111 ×0,39 [0,28; 0,53]** | **0,0117 ×0,52 [0,36; 0,72]** | **0,0190 ×0,20 [0,15; 0,27]** |
| **model null** | | | | |
| obecny, bez twirlu | 0,0393 | 0,0102 | 0,0153 | 0,0263 |
| obecny + twirl | ×1,06 [0,87; 1,27] | ×0,87 [0,74; 1,02] | ×0,82 [0,71; 0,94] | ×1,02 [0,84; 1,27] |
| 60 obwodów, bez twirlu | ×0,26 [0,09; 0,62] | ×0,65 [0,56; 0,74] | ×0,57 [0,33; 0,82] | ×0,41 [0,29; 0,57] |
| **60 obwodów × 1 ramka** | **×0,23 [0,08; 0,61]** | **×0,71 [0,59; 0,86]** | **×0,59 [0,32; 0,88]** | **×0,46 [0,31; 0,66]** |

![Rys. 2](fig_cdr_variants_sim.png)

**Rys. 2.** Błąd CDR w symulatorze skalibrowanym do ODRY, przy równym budżecie pomiarów, dla czterech wariantów w układzie 2×2: zbiór treningowy (10 obwodów × 6 kopii vs 60 różnych obwodów) × twirling (nie / tak). (a) Szum wyłącznie niekoherentny. (b) Dodatkowa faza ZZ θ = 0,05 rad i Z 0,03 rad na każdym CZ. Punkty to średnia z 8 powtórzeń × 8 punktów ewaluacyjnych; słupki to 95% CI z bootstrapu po powtórzeniach; linia kropkowana to błąd bez mitygacji. Wszystkie ramiona mają scalone bramki 1q.

**Interpretacja: dwie niezależne dźwignie, które się mnożą.**
- **Różnorodność zbioru treningowego** pomaga zawsze (null i koherentny), bo zmniejsza wariancję dopasowania a, b. W modelu null cały zysk pochodzi stąd (twirl nic nie dodaje: 0,46 vs 0,41 przy 54 CZ).
- **Twirling** pomaga tylko przy błędzie koherentnym. Przy 54 CZ obniża błąd 60-obwodowego CDR z 0,0617 do 0,0190 (3,2×).
- Razem, względem obecnego CDR z twirlingiem: 0,43× [0,19; 0,90] przy 12 CZ i 0,61× [0,46; 0,80] przy 54 CZ, istotnie. Przy 27 i 36 CZ ilorazy wynoszą 0,88 z CI obejmującym 1.
- W modelu koherentnym, względem obecnego potoku bez twirlingu: 1,9–5,0× mniejszy błąd przy tej samej liczbie shotów i tej samej liczbie obwodów na cel (66).

**Teoria, która to przewiduje.** Twierdzenie o projekcji odpowiedzi celu z [Scavino 2026b (arXiv:2606.21686)](https://arxiv.org/abs/2606.21686) mówi, że afiniczne CDR usuwa bias pierwszego rzędu tylko wtedy, gdy odpowiedź szumu na cel jest afiniczna w wartości idealnej. Błąd koherentny tę afiniczność łamie, a twirling ją przywraca. To dobre ramy teoretyczne dla naszego wyniku sprzętowego.

**Nowość (wstępnie).**
- Twirling i CDR były już łączone na sprzęcie jako narzędzie, bez porównania z twirlingiem i bez niego przy tym samym budżecie: pseudotwirling bramek FSIM i regresja w symulacji fal plazmy ([Sundar i in. 2025, arXiv:2507.09479](https://arxiv.org/abs/2507.09479)).
- Jedna ramka na obwód treningowy przy zwiększonej liczbie różnych obwodów i równym budżecie: przegląd nowości jej nie znalazł. Opierał się jednak głównie na abstraktach i 18 pełnych tekstach, więc to ocena wstępna.
- Wybór szerokiego rozkładu obwodów treningowych jest znany ([Czarnik i in. 2025](https://doi.org/10.22331/q-2025-05-05-1727)). Nowe jest połączenie z randomizacją ramek i wykazanie, że to ono zastępuje uśrednianie ramek w obrębie obwodu.
- Wspólne ramki dla treningu i celu (CRN) też nie zostały znalezione w literaturze, ale nie działają.

**Zastrzeżenia.**
- Jeden model szumu koherentnego (wartość θ przyjęta, nie zmierzona) i jedna kalibracja.
- Brak bezczynności i crosstalku.
- Punkty ewaluacyjne losowane jednostajnie, nie z rozkładu danych.
- σ = π/4 nie było strojone.
- Przy 12 CZ obecne CDR w symulacji jest *gorsze* od raw (0,056 vs 0,040, szerokie CI), podczas gdy na sprzęcie poprawia wynik. To wynika z wyboru punktów ewaluacyjnych i wspólnego zbioru treningowego; nie interpretować ilościowo.

### 3.4 Jak to sprawdzić na ODRZE (wpięte w C1/C3 z raportu głównego)
1. Kod (bez QPU):
   - obwody treningowe budowane na obwodzie natywnym celu (§3.1);
   - generator „60 × 1 ramka, bliskie celowi”;
   - scalanie 1q we wszystkich ramionach;
   - zapis zliczeń dla każdego obwodu.
2. Projekt czynnikowy 2×2 (zbiór treningowy × twirl) plus obecny wariant 10 × 6 jako punkt odniesienia. Ta sama liczba obwodów (66 na cel) i shotów w każdym ramieniu, kolejność losowana blokowo w oknie.
3. Drabina 12/27/36/54 CZ, 24 punkty ewaluacyjne, ≥ 12 okien (to samo co C1, ~6,5 h na noc plus ~30% na dodatkowe ramiona).
4. Analiza:
   - model mieszany na log ε (efekty: zbiór × twirl × CZ; losowe: okno, punkt);
   - interakcję zbiór × twirl testujemy wprost;
   - dla każdego ramienia także ryzyko decyzji D (§2).
5. Kryterium (pre-rejestracja): wariant 60 × 1 ramka ma iloraz < 1 względem 10 × 6 z twirlem, z 95% CI wykluczającym 1 w ≥ 2 z 4 punktów drabiny, a w żadnym punkcie nie jest istotnie gorszy.

## 4. Co zmienia się w artykule
- **Luka (doprecyzowana):** twirling i CDR były już łączone na sprzęcie jako narzędzie (Sundar i in. 2025), ale nikt nie zmierzył przy równym budżecie, czy i kiedy twirling jest *konieczny*. Brakuje też eksperymentalnego testu twierdzenia o projekcji (Scavino 2026b).
- **Nowy wkład metodologiczny:** randomizacja treningu (60 × 1 ramka) jako sposób na wykorzystanie budżetu twirlingu. W symulacji daje 0,43–0,61× niższy błąd od zwykłego twirled CDR (12 i 54 CZ); wymaga potwierdzenia na ODRZE.
- **ZNE:** raportować W_neg i garbage folding (Köster i Mauerer) przy każdym zysku powyżej ~30 CZ.
- **Klasyfikator:** raportować ryzyko decyzji obok MSE (Scavino).
- **Erratum do danych:** CDR w `odra_full_100pt`/`odra_cdr_100pt` było trenowane na inaczej zroutowanych obwodach. Te liczby nadają się tylko jako dolna granica jakości CDR, albo trzeba je powtórzyć po poprawce.

## Pliki
- [fig_cdr_variants_sim.png](fig_cdr_variants_sim.png) — Rys. 2
- [cdr_variants_sim_summary.csv](cdr_variants_sim_summary.csv) — ilorazy i CI dla wszystkich wariantów
- [cdr_variants_sim_raw.csv](cdr_variants_sim_raw.csv) — błędy dla każdego (powtórzenie × punkt)
- [sim_cdr_variants_bench2.py](sim_cdr_variants_bench2.py), [sim_cdr_variants_bench3_control.py](sim_cdr_variants_bench3_control.py) — kod symulacji
