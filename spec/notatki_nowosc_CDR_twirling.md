# Sprawdzenie nowości: ulepszenia CDR + Pauli twirling (projekt QEM, ODRA 5)

Data: 2026-10-15. Źródła: arXiv API (export.arxiv.org, ~40 zapytań po abstraktach), pełne teksty PDF z arxiv.org dla 18 prac (grep słów kluczowych), CrossRef (wyszukiwanie tytułów 2023+), 3 zapytania web_search. OpenAlex nie był używany.
**Ograniczenia:** wyszukiwanie arXiv obejmuje tylko tytuł i abstrakt, więc rozwiązania opisane wyłącznie w treści prac mogą być pominięte. Pełny tekst przeszukano tylko dla prac wymienionych niżej. Werdykt „nowe” znaczy „nie znaleziono” i nie dowodzi braku prac.

## Tabela zbiorcza

| # | Pomysł | Status | Najbliższa praca |
|---|---|---|---|
| 1 | CDR z korekcją rozcieńczenia regresji (EIV/Deming/SIMEX) | nowe (w QEM), metoda znana w statystyce | Scavino 2606.21686 (EIV wymienione jako reżim poza teorią, bez korekcji); Prodius 2307.05302 |
| 2 | Wspólne ramki twirlu (common random frames) dla treningu i celu | nowe | Liao 2309.17368 (ta sama *procedura* twirlu w learning i mitigation PEC, nie te same realizacje) |
| 3 | CDR rozdzielone na człony obserwabli (Z_i) | znane | Czarnik 2204.07109/Quantum 2025; Sundar 2507.09479 (per-kubit + twirling, hardware); Farrell 2308.04481 (ODR per-kubit po PT) |
| 4 | Projekt zbioru treningowego (near-Clifford vs. pełny Clifford) przy twirlu | częściowo znane | Czarnik 2005.10189; Czarnik 2204.07109; Zhang 2412.09518 (CPDR); Zhao 2511.03556 (ES/NCE); Tirado 2605.25830 (biased CDR) |
| 5 | TREX + CDR | częściowo znane (składniki znane, kombinacja nieopisana; teoretycznie w dużej mierze redundantna) | van den Berg 2012.09738; Liao 2309.17368 (ZNE+TREX); Scavino 2606.21686 (archiwalny kontrast readout/twirl dla CDR) |
| 6 | Twirling + vnCDR/UNITED na hardware | częściowo znane | Lowe 2011.01157 (sym.); Bultrini 2107.13470 (sym.); Sopena 2103.12680 (vnCDR na IBM, bez twirlu) |
| 7 | Hierarchiczne/bayesowskie łączenie współczynników CDR między oknami kalibracji; CDR odporne na dryf | częściowo znane | Liao 2309.17368 App. D (fine-tuning do dryfu); Korolev 2606.02697 (transfer między hamiltonianami); Prodius 2307.05302 |

---

## 1. Errors-in-variables / CDR z korekcją rozcieńczenia — **nowe w kontekście QEM (nie znaleziono)**

**Co jest w literaturze**
- Scavino 2026, *Finite-shot operating windows for probabilistic error cancellation and Clifford data regression*, arXiv:2606.21686. Jedyna znaleziona wzmianka o EIV w CDR. Autor zastrzega, że gdy szum predyktora jest duży, linearyzacja OLS „becomes an errors-in-variables problem”. Ten reżim zostaje poza teorią, a autor zaleca jedynie test stabilności (â, b̂) przez resampling. Korekcji nachylenia nie proponuje.
- Prodius, Czarnik, McKerns, Sornborger, Cincio 2023, *Robust design under uncertainty in quantum error mitigation*, arXiv:2307.05302. Propagują niepewność shotową przez ZNE i CDR (strategic sampling) i optymalizują rozkład obwodów treningowych CDR. Obciążenia nachylenia przez szum w x nie korygują.
- Oryginalne CDR (Czarnik, Arrasmith, Coles, Cincio, arXiv:2005.10189) i vnCDR (Lowe i in., arXiv:2011.01157, PRR 3, 033098) stosują zwykłe LS. Nie znaleziono pracy z Deming/TLS/SIMEX/ODR w CDR. Zapytania arXiv „errors-in-variables / total least squares / regression dilution / Deming” w połączeniu z „error mitigation” dały 0 trafień.

**Uwagi merytoryczne (do implementacji)**
- Układ to klasyczne EIV z dokładną odpowiedzią: y (ideał) liczony klasycznie bez błędu, x (szum) obciążony błędem shotowym. Nachylenie OLS ma oczekiwanie a_true·λ, gdzie λ = Var(x_true)/(Var(x_true)+mean σ²). Korekcja momentowa: â = cov(x,y)/(var(x) − mean σ_x²); b̂ = ȳ − â x̄.
- **Ważna poprawka do wzoru z zadania.** σ² = (1−⟨O⟩²)/S obowiązuje tylko dla pojedynczego Pauliego o wartościach ±1. Dla średniej Z (5 członów) wariancja na shot wynosi Var((1/5)Σ Z_i) = (1/25)ΣΣ Cov(Z_i,Z_j), czyli zawiera kowariancje. Trzeba ją estymować z bitstringów (empiryczna wariancja średniej-Z na shot). Przy twirlu z M ramkami i równą liczbą shotów na ramkę zbiorcza wariancja zawyża σ² o wariancję międzyramkową; poprawna jest wariancja wewnątrzramkowa (stratyfikowana).
- Kiedy to istotne (szacunek ilustracyjny, policzony z założonych wartości, nie z danych): przy tłumieniu f i wariancji ideałów treningowych V_y mamy λ ≈ f²V_y/(f²V_y + σ²), gdzie σ² = v_shot/S. Wariancja na shot v_shot dla średniej-Z leży między ≈0.2 (5 nieskorelowanych Z_i bliskich zeru) a 1 (pełna korelacja). Przy S = 4096 i V_y = 0.1: f=0.03, v_shot=0.2 → λ=0.65; f=0.03, v_shot=1.0 → λ=0.27; f=0.05, v_shot=0.2 → λ=0.84; f=0.05, v_shot=1.0 → λ=0.51; f=0.1, v_shot=0.2 → λ=0.95; f=0.1, v_shot=1.0 → λ=0.8; f=0.3, v_shot=0.2 → λ=0.99; f=0.3, v_shot=1.0 → λ=0.97. Wniosek: przy f ≲ 0.05 (rejon sygnału przy podłodze, jak |⟨O⟩(1)| ≈ 0.04 przy 39 CZ) nachylenie jest zaniżone o 16–73% (λ = 0.27–0.84). Przy f = 0.1 λ = 0.80–0.95, a przy f = 0.3 efekt jest pomijalny (λ ≥ 0.97). Uśrednianie M kopii/ramek zwiększa efektywne S i osłabia efekt.
- Ryzyko: korekcja momentowa jest niestabilna, gdy var(x) ≈ mean σ². Wtedy potrzebne jest obcięcie (λ ≥ λ_min) albo SIMEX/bootstrap. Wariancja estymatora rośnie, więc w budżecie MSE trzeba uwzględnić kompromis obciążenie–wariancja.

**Co byłoby nowe dla nas:** sformułowanie CDR jako EIV ze *znaną* heteroskedastyczną wariancją shotową (z poprawnym σ² dla obserwabli wieloczłonowych i dla twirlu). Do tego przewidywanie progu CZ, od którego korekcja obniża MSE przy równym budżecie shotów, i walidacja na ODRA 5. Część testu można zrobić bez nowych pomiarów: podpróbkowanie shotów z istniejących liczników, jeśli są zapisane (dla CSV twirl nie są; patrz notatki projektu).

## 2. Wspólne ramki twirlu (frame-matched / common random numbers) — **nowe (nie znaleziono)**

**Co jest w literaturze**
- Liao, Wang, Sitdikov, Salcedo, Seif, Minev 2023, *Machine Learning for Practical Quantum Error Mitigation*, arXiv:2309.17368. Piszą o PEC, że tę samą *procedurę* twirlu stosuje się w fazie uczenia i mitygacji („to keep the noise in the learning and the mitigation as similar as possible”). Chodzi o ten sam rozkład, nie o te same realizacje ramek. W ML-QEM używają 5 twirli na obwód bez wspólnych ramek.
- Kim i in. 2021, arXiv:2108.09197: „the same set of twirling gates” odnosi się do ramki przed i po RZZ w obrębie jednej bramki, a nie do współdzielenia między obwodami.
- Sundar i in. 2025 (Rigetti), arXiv:2507.09479: pseudotwirling FSIM + CDR na hardware. Nie znaleziono deklaracji współdzielenia ramek między obwodami Clifforda a celem.
- Zapytania arXiv „common random numbers” + quantum oraz „twirl + same randomization/correlated + error mitigation” dały 0 trafień na temat.

**Uwagi merytoryczne**
- Implementowalność: obwody treningowe mają ten sam szkielet CZ co cel, więc przypisanie Pauli (P_a⊗P_b) do każdej instancji CZ jest dobrze zdefiniowane i scala się z innymi 1q-bramkami. Wspólna ramka jest zatem wykonalna bez narzutu.
- Zastrzeżenie fizyczne: przy ustalonej ramce resztkowy błąd koherentny jest stały, ale jego wpływ na obserwablę zależy od stanu, a 1q-bramki treningu i celu różnią się. Korelacja reszt między treningiem i celem nie jest więc gwarantowana. Zysk CRN wymaga Corr(δ_train, δ_target) > 0 i należy go zmierzyć, a nie zakładać.
- Pułapka: przy wspólnych ramkach błędy reszt w punktach treningowych są skorelowane. Standardowe przedziały z OLS zaniżają wtedy niepewność, więc trzeba robić bootstrap po ramkach.

**Co byłoby nowe dla nas:** pierwsza (w znalezionej literaturze) kontrola CRN dla CDR+twirling: arm A z niezależnymi ramkami na obwód, arm B ze wspólnymi M ramkami, przy równych shotach. Do tego pomiar Corr(δ_train, δ_target) w funkcji M i liczby CZ. Na ODRA można to tanio wykonać przy M ∈ {1,2,4,6}.

## 3. CDR rozdzielone na człony obserwabli — **znane**

- Czarnik, McKerns, Sornborger, Cincio, *Improving the efficiency of learning-based error mitigation*, arXiv:2204.07109; Quantum (2025), DOI 10.22331/q-2025-05-05-1727. Dopasowują M osobnych ansatzów O_j^exact = a_j O_j^noisy + b_j, po jednym na obserwablę. Dla LiH piszą: „We perform CDR for each term of the Hamiltonian separately”.
- Sundar, Evert, Geyko, Patterson, Joseph, Shi i in. 2025, *Simulating plasma wave propagation on a superconducting quantum chip*, arXiv:2507.09479. Na hardware łączą (pseudo)twirling z CDR jako per-obserwablowymi/per-kubitowymi współczynnikami tłumienia (suppression coefficients), wyznaczanymi z losowych obwodów Clifforda o tej samej strukturze natywnej.
- Farrell, Illa, Ciavarella, Savage 2023, arXiv:2308.04481 (Schwinger, 100 kubitów). Operator Decoherence Renormalization: po Pauli twirlingu tempo dekoherencji wyznaczane jest osobno dla każdego kubitu z obwodu mitygacyjnego. Motywacja jest dokładnie taka jak w pomyśle 3.
- Urbanek i in. 2021, arXiv:2103.08591 (noise-estimation circuits): wcześniejsza, globalna wersja przeskalowania.

**Co byłoby nowe dla nas (wąsko):** zastosowanie do obserwabli średniej-Z klasyfikatora z porównaniem CDR zagregowanego i rozdzielonego przy *równych shotach*. Rozdzielenie nie kosztuje shotów, bo wszystkie Z_i pochodzą z tych samych bitstringów, ale ma 10 zamiast 2 parametrów przy n_train = 10, więc rośnie wariancja. Ocena na poziomie decyzji klasyfikatora. Możliwy wariant pośredni: wspólny wyraz wolny i osobne nachylenia albo shrinkage nachyleń a_i do wspólnej średniej (łączy się z pkt 7). To raczej ablacja niż wkład metodologiczny.

## 4. Projekt zbioru treningowego (near-Clifford vs. pełny Clifford) przy twirlu — **częściowo znane**

- Czarnik i in. 2021, arXiv:2005.10189 (Quantum 5, 592). Obwody near-Clifford z N zachowanymi bramkami nie-Cliffordowymi. Proponują zamianę bramek na bliskie Cliffordy oraz próbkowanie MCMC według wartości obserwabli, ukierunkowane na stan docelowy.
- Czarnik i in., arXiv:2204.07109 / Quantum 2025. Celowy dobór danych treningowych („widely-spread distribution”) i wykorzystanie symetrii: rząd wielkości mniej shotów.
- Bultrini, Gordon, Czarnik, Arrasmith, Cerezo, Coles, Cincio, arXiv:2107.13470 (UNITED). Benchmark z liczbą bramek nie-Cliffordowych w treningu jako hiperparametrem (symulacje).
- Prodius i in., arXiv:2307.05302. Optymalizacja rozkładu obwodów treningowych CDR pod niepewnością.
- Zhang, Shao, Wei, Cheng, Wei, Liu 2024, *Clifford Perturbation Approximation for Quantum Error Mitigation* (CPDR), arXiv:2412.09518. Trening na obwodach z kątami w wąskim przedziale wokół Cliffordów (symulacja Sparse Pauli Dynamics). Zastosowane do danych IBM Eagle.
- Zhao, Kjellgren, Coriani, Kongsted, Sauer, Ziems 2025, arXiv:2511.03556. Energy Sampling (wybór obwodów najbliższych celowi) oraz Non-Clifford Extrapolation: liczba nie-Cliffordowych parametrów jako dodatkowa cecha regresji i ekstrapolacja do k = n. Najbliższa praca do „frakcji snapowanych rotacji”.
- Tirado i in. 2026, arXiv:2605.25830. „Biased CDR”: kliffordyzacja maksymalizująca podobieństwo do oryginału, na hardware IBM w skali użytkowej.
- Montanaro, Stanisic 2021, arXiv:2102.02120. Trening na obwodach fermionowej optyki liniowej, czyli klasa bliższa celowi niż Clifford.
- Korolev, Lakhmanskiy, Rabinovich 2026, arXiv:2606.02697. ML-QEM dla VQA z treningiem na (near-)Cliffordach, transfer na dowolne parametry.
- Sundar i in. 2025 (arXiv:2507.09479) używają przy twirlu w pełni losowych Cliffordów. Nie znaleziono systematycznego porównania near-Clifford i pełnego Clifforda *pod twirlem* na hardware.

**Kluczowa uwaga dla nas:** przy 5 kubitach każdy obwód jest klasycznie symulowalny (statevector), więc ograniczenie do Cliffordów jest sztuczne. Zbiór treningowy może zawierać obwody docelowe na innych wejściach danych klasyfikatora albo z perturbowanymi kątami, czyli być w pełni „w rozkładzie celu”. To jest mocny i tani test hipotezy z pracy Scavino (projection theorem: affine CDR usuwa obciążenie pierwszego rzędu tylko przy afinicznej odpowiedzi celu). Wynik nie przenosi się jednak na duże układy, co trzeba uczciwie zaznaczyć.

**Co byłoby nowe dla nas:** krzywa „frakcja snapowanych rotacji ∈ {1.0, 0.75, 0.5, 0.25, 0 (pełny cel)}” × {twirl, bez twirlu} × liczba CZ przy równym budżecie shotów i współdzielonej (pkt 2) albo niezależnej puli ramek. Do tego metryka odległości trening–cel (np. różnica rozkładów x_noisy lub odpowiedzi szumowej) jako predyktor błędu CDR.

## 5. TREX + CDR — **częściowo znane**

- van den Berg, Minev, Temme 2020/2022, *Model-free readout-error mitigation for quantum expectation values* (TREX), arXiv:2012.09738.
- Liao i in. 2023, arXiv:2309.17368. ML-QEM naśladuje ZNE + TREX (100 kubitów, ibm_brisbane), więc TREX jest łączony z metodą uczoną, ale nie z CDR.
- Scavino 2026, arXiv:2606.21686. W archiwalnej analizie liczników z urządzenia raportuje kontrast „readout/twirling” dla CDR (średnia luka obciążenia CDR twirled-minus-mitigated 4.02e-4). Nie jest to nowy eksperyment ani projekt TREX+CDR.
- Czarnik 2005.10189 pomija szum odczytu, odsyłając do metod wyspecjalizowanych.

**Uwaga teoretyczna:** TREX diagonalizuje szum odczytu do mnożnika na każdego Pauliego. Afiniczne CDR, a zwłaszcza CDR rozdzielone na człony, już absorbuje taki mnożnik i asymetrię (wyraz wolny). Oczekiwany zysk w obciążeniu jest więc ~0. Możliwe efekty to tylko zmiana wariancji i usunięcie zależności szumu odczytu od stanu (co poprawia afiniczność). Projekt już pokazał, że mitygacja odczytu nie zmieniła żadnej decyzji klasyfikatora. **Niski priorytet.** Wartościowy byłby tylko jako kontrola negatywna potwierdzająca redundancję.

## 6. Twirling + vnCDR / UNITED na hardware — **częściowo znane**

- Lowe, Gordon, Czarnik, Arrasmith, Coles, Cincio 2021, *Unified approach to data-driven quantum error mitigation* (vnCDR), arXiv:2011.01157, PRR 3, 033098: symulacje z modelem szumu IBM Ourense.
- Bultrini i in., arXiv:2107.13470 (UNITED): symulacje z modelem szumu (IBM Toronto).
- Sopena, Gordon, Sierra, López 2021, arXiv:2103.12680: CDR, vnCDR i „poor-man's CDR” na prawdziwym IBM (9 kubitów, głębokość do 176). W tekście nie ma twirlu (0 wystąpień).
- Mitiq (LaRose i in., arXiv:2009.04417) implementuje vnCDR (scale_factors > 1).
- Nie znaleziono pracy łączącej twirling z vnCDR/UNITED na hardware.

**Co byłoby nowe dla nas:** vnCDR (skale {1,3} lub {1,3,5}, globalne foldowanie) z twirlem i bez, przy kontroli shot-matched, na drabinie 12/27/36/54 CZ. Szczególnie ciekawe w świetle wyniku κ dla ZNE: vnCDR dziedziczy wzmocnienie wariancji Richardsona, a twirl może poprawić liniowość odpowiedzi na foldowanie. Uwaga na podwojenie/potrojenie kosztu treningu przy równym budżecie.

## 7. Bayesowskie/hierarchiczne łączenie współczynników CDR, transfer, dryf — **częściowo znane**

- Liao i in., arXiv:2309.17368, App. D: modele ML-QEM można efektywnie dostroić (fine-tune) do dryfu szumu. Model trenowany raz jest stosowany do wielu obwodów (transfer między obwodami).
- Korolev i in., arXiv:2606.02697: transfer modelu mitygacji między hamiltonianami o podobnej strukturze.
- Chen, Cheng, Gao, Lin, Zhang, Wei 2025, *Neighbor-informed learning* (NIL), arXiv:2512.12578: uczenie z obwodów „sąsiednich”.
- Prodius i in., arXiv:2307.05302: projektowanie odporne na niepewność (nie bayesowskie pooling).
- Szachara i in. 2026, GSC-QEMit, arXiv:2604.24551: adaptacyjny wybór mitygacji pod dryf (prognoza + bandyta). Nie dotyczy współczynników CDR.
- Zapytania arXiv „Bayesian + quantum error mitigation” zwróciły tylko prace o odczycie (Zheng i in. 2010.09188; Stein i in. 2207.07237), nie o CDR. Nie znaleziono hierarchicznego modelu (a_w, b_w) ~ N(μ, Σ) między oknami kalibracji.

**Co byłoby nowe dla nas:** empirical-Bayes/hierarchiczne shrinkage (a,b) między oknami kalibracji ODRA i między poziomami CZ, a także między członami Z_i (łączy się z pkt 3). Przy n_train = 10 i sygnale przy podłodze może to wyraźnie zmniejszyć wariancję współczynników bez dodatkowych shotów. Do tego test „ile świeżych obwodów treningowych potrzeba po rekalibracji” (warm-start). Rzetelna walidacja wymaga wielu okien kalibracji, co jest możliwe przy nielimitowanym ODRA.

---

## Inne ulepszenia CDR (2023–2026) istotne przy równym budżecie shotów

1. CPDR: trening na obwodach z perturbowanymi kątami wokół Cliffordów, większa różnorodność (Zhang i in., arXiv:2412.09518).
2. Energy Sampling i Non-Clifford Extrapolation, gdzie liczba nie-Cliffordów jest cechą regresji (Zhao i in., arXiv:2511.03556).
3. Rozszerzenia CDR o kopie obwodu i dodatkową warstwę rotacji 1q, z mniejszym RMSE (Pérez-Guijarro, Pagès-Zamora, Fonollosa, arXiv:2411.16653; IEEE TQE 2026, DOI 10.1109/tqe.2026.3677541).
4. Echo-Verified CDR (EVCDR), CDR po weryfikacji echem z ancillą, hardware do 35 spinów (Weaving, Ralli, Love, Succi, Coveney, arXiv:2408.07439).
5. Biased CDR, czyli kliffordyzacja maksymalizująca podobieństwo do celu, hardware IBM (Tirado i in., arXiv:2605.25830).
6. Shot-frugal CDR z symetriami i rozłożonym rozkładem treningowym, ~10× taniej (Czarnik i in., arXiv:2204.07109 / Quantum 2025).
7. Projektowanie odporne: optymalizacja rozkładu obwodów treningowych i przydziału shotów pod niepewność (Prodius i in., arXiv:2307.05302).
8. Teoria okien skończonej liczby shotów dla CDR vs PEC, z twierdzeniem o projekcji odpowiedzi i analizą przydziału shotów trening/cel (Scavino, arXiv:2606.21686). Uwarunkowanie macierzy Grama wzmacnia szum treningu, co przekłada się bezpośrednio na wybór n_train vs shoty/obwód.
9. ML-QEM (lasy losowe, GNN) z treningiem raz na wiele obwodów, co amortyzuje koszt treningu (Liao i in., arXiv:2309.17368). NIL: obwody sąsiednie i trening 2-design (Chen i in., arXiv:2512.12578).
10. Trening na obwodach fermionowej optyki liniowej zamiast Cliffordów (Montanaro, Stanisic, arXiv:2102.02120).
11. Teoria mitygacji dla bramek nie-Cliffordowych (np. małe RZZ) i ich twirlowania (Layden, Mitchell, Siva, arXiv:2403.18793; Quantum 2026, DOI 10.22331/q-2026-02-10-2003). Mniej istotne dla natywnego CZ na ODRA.

## Rekomendacja priorytetów dla ODRA 5 (moja ocena)

1. **Pkt 1 (EIV)**: najwyższy stosunek nowości do kosztu, czysto analityczny i działa na istniejących danych, jeśli są liczniki. Uderza dokładnie w reżim wysokiego CZ.
2. **Pkt 2 (wspólne ramki)**: nowe i tanie na ODRA. Wymaga pomiaru korelacji reszt.
3. **Pkt 7 (shrinkage)** razem z pkt 3: redukcja wariancji przy n_train = 10. Pkt 3 jako ablacja, nie jako wkład.
4. Pkt 4 i 6: częściowo znane, sensowne jako mapy reżimów.
5. Pkt 5 (TREX): kontrola negatywna, niski priorytet.


## Weryfikacja DOI
Wszystkie DOI czasopism podane w notatkach sprawdzono rekordem CrossRef (api.crossref.org/works/<DOI>): 10.22331/q-2025-05-05-1727 (Czarnik, McKerns, Sornborger, Cincio; Quantum, 2025-05-05), 10.1103/PhysRevResearch.3.033098 (Lowe i in.), 10.1109/tqe.2026.3677541 i 10.22331/q-2026-02-10-2003 (z wyszukiwania CrossRef). Identyfikatory arXiv zweryfikowano przez arXiv API.
