# Niezależna weryfikacja odtwarzalności — okno w01 (noc A + noc P5)

Data: 2026-10-25. Weryfikator: niezależny audyt offline (bez dostępu do QPU, bez poświadczeń).
Wszystkie skrypty są w `review/scripts/`, a wyniki pośrednie w `review/scripts/tmp/`.
Niczego w repozytorium nie zmieniałem. `results/` sprawdziłem sumą md5 przed i po uruchomieniu prereg: bez zmian.

| skrypt | co robi |
|---|---|
| `recompute_w01A.py` | liczy ⟨O⟩ z `counts` (obie konwencje bitów), budżet, OLS CDR, Richardsona, W_neg i SNR; porównuje z `cdr.csv`/`zne.csv` (A oraz P5). Kod projektu nie jest importowany. |
| `headline.py` | liczby nagłówkowe, testy Wilcoxona, regresja P5 |
| `check_skeleton_twirl.py`, `twirl_equiv.py` | szkielety CZ, ideały z qasm3 (Statevector), `rebuild_from_frame` |
| `identity_anomaly.py` | odbudowa obwodów ZNE ścieżką kampanii, symulacja Aer z ablacjami szumu |
| `p5_robust.py`, `p5_calib_sens.py` | odporność wnioskowania P5 przy 8 klastrach oraz wpływ zmiany kalibracji |
| `power_h1.py` | moc H1 po nocy B |

Stan `w01B`: pomiar w toku. `counts.jsonl` ma 400 rekordów, manifest nie ma `finished_utc` ani zapisanych bloków, a `w01.log` od 18:38 pokazuje „ODRA not answering”. Nie analizowałem tej nocy.

---

## 1. Tabela: deklarowane vs przeliczone

Wszystkie średnie są liczone po 8 punktach (eval_index 0, 3, …, 21), fit OLS. Przeliczenie idzie wprost z `counts.jsonl`.

| wielkość | deklarowane | przeliczone | status |
|---|---|---|---|
| A star near_target off_copies | 0.0216 | 0.0216 | OK |
| A star near_target twirl_native | 0.0150 | 0.0150 | OK |
| A star near_target spread | 0.0122 | 0.0122 | OK |
| A circular near_target off_copies | 0.0529 | 0.0529 | OK |
| A circular near_target twirl_native | 0.0397 | 0.0397 | OK |
| A circular near_target spread | 0.0679 | 0.0679 | OK |
| A star shared_random twirl_native / twirl_logical | 0.0308 / 0.0194 | 0.0308 / 0.0194 | OK |
| A circular shared_random twirl_native / twirl_logical | 0.0320 / 0.0248 | 0.0320 / 0.0248 | OK |
| raw (target off_copies) star / circular | 0.0737 / 0.1608 | 0.0737 / 0.1608 | OK |
| ZNE genuine / garbage, star | 0.0452 / 0.1373 | 0.0452 / 0.1373 | OK |
| ZNE genuine / garbage, circular | 0.1115 / 0.1028 | 0.1115 / 0.1028 | OK |
| ZNE identity star / circular | 0.0720 / 0.1939 | 0.0720 / 0.1939 | OK |
| identity ⟨O⟩ λ3/λ5 star | 0.16 / 0.28 | 0.156 / 0.282 | OK |
| identity ⟨O⟩ λ3/λ5 circular | 0.40 / 0.57 | 0.403 / 0.568 | OK |
| twirl vs off, star: wygrane, ratio geom. | 4/8, 1.41 | 4/8, 1.410 | OK |
| twirl vs off, circular | 7/8, 0.68 | 7/8, 0.683 | OK |
| H1 łącznie (16 par), Wilcoxon 1-str. na log ε | p = 0.35 | p = 0.3529 (ratio 0.981) | OK |
| H4 star: ZNE<raw, ZNE<garbage | p = 0.47, 0.012 | 0.4727, 0.0117 | OK |
| H4 circular: ZNE<raw, ZNE<garbage | p = 0.004, 0.84 | 0.0039, 0.8438 | OK |
| P5 raw: czynnik cz10, p | 0.955, 0.68 | 0.955, 0.68 | OK (uwaga F4) |
| P5 raw: czynnik dur, p | 1.434, p<1e-4 | 1.434, 5.3e-13 | OK liczbowo; przy korekcie małej liczby klastrów p = 1.7e-4 (t(7)), a wild cluster bootstrap daje 0.010 (F4) |
| P5 CDR: czynnik cz10, p | 1.339, 0.002 | 1.339, 0.0020 | OK liczbowo; t(7): p = 0.018, wild bootstrap: 0.020 (F4) |
| P5 bez star_cz52: raw dur, raw cz10, CDR cz10 | 1.48, 1.03, 1.59 | 1.484, 1.025, 1.586 | OK |
| budżet CDR na punkt (każde ramię) | 1 032 192 | 1 032 192 we wszystkich 80 (A) i 80 (P5) grupach | OK |
| budżet ZNE genuine na punkt | 24 576 | 24 576 (16/16) | OK |

**Zgodność z CSV projektu (zadanie 1).** Maksymalne rozbieżności:

| plik | wiersze | max różnica |
|---|---|---|
| `w01A/cdr.csv` | 80 | |Δ| ≤ 3e-15 w `raw`, `mitigated`, `err`, `a`, `b`, `r2`; `shots_total` i `n_train_points` identyczne |
| `w01A/zne.csv` | 48 | |Δ| ≤ 2e-15 w `zne` i `err_zne`; `w_neg` 4.8e-7 (to zaokrąglenie do 6 miejsc w `as_row`); `snr_lmax` 3e-14 |
| `w01P5/cdr.csv` | 80 | |Δ| ≤ 6e-16 |

Dla każdego z 10 192 (A) i 10 080 (P5) rekordów `expval` policzone z `counts` zgadza się z polem do 1e-16, a suma counts równa się `shots`.

**Kolejność bitów.** `odra_backend.iqm_counts_to_qiskit` zapisuje counts w konwencji Qiskita, a dalej `perqubit_z_from_counts` i `qem.zne.probabilities(..., "qiskit")` czytają je zgodnie. Dla obserwabli mean-Z (współczynniki 1/5) kolejność bitów nie ma znaczenia: obie konwencje dają tę samą wartość (max Δ = 0). Na W_neg permutacja też nie wpływa. Zależą od niej tylko wielkości per kubit (`w_neg_marg_max` i rozkłady per kubit), ale żadna liczba nagłówkowa ich nie używa. Uwaga utajona: zob. B7.

---

## 2. Ustalenia

### F1. Szkielety CZ i ramki twirlu (zadania 3–4): OK
- Szkielet jest zgodny w 100% rekordów CDR w A (10 080) i P5 (10 080). Pole `skeleton_matches_target` = True dla wszystkich ramion poza `twirl_logical`, gdzie ma wartość `null` zgodnie z kodem. Przeliczenie z `cz_skeleton` też daje 100% zgodności z targetem, także dla `twirl_logical`. `cz_skeleton` zgadza się z qasm3 w próbce 408 rekordów.
- Wartości `ideal` liczyłem niezależnie z qasm3 przez Statevector. Wszystkie 80 targetów: max |Δ| = 2e-15. Próbka 260 obwodów treningowych: 7e-16, a 156 obwodów twirl_logical: 8e-16. Warianty genuine i identity ZNE dają ideał równy ideałowi U do 1e-14. Garbage z założenia ma inny ideał, a pole `ideal` niesie ideał targetu.
- `rebuild_from_frame(niet-twirlowany, frame)` odtwarza wykonany obwód bramka w bramkę w 184/184 próbkach twirl_native. Twirlowany obwód różni się od nietwirlowanego tylko macierzą diagonalną na wyjściu: `merge_prx` porzuca końcowe RZ. Rozkład pomiaru jest identyczny (max |Δp| = 5e-16, 119/119). To jest poprawne dla odczytu w bazie Z.

### F2. Anomalia foldingu `identity` (zadanie 5): efekt fizyczny (T1), nie błąd w kodzie, ale kontrola jest źle pomyślana

Dowody przeciw hipotezie błędu:
1. Obwody ZNE odbudowałem ścieżką kampanii (`frozen` → `compile_native` → `fold_native`, ziarno `_seed(42,"w01A",cid)`). Wszystkie 112 są identyczne bramka w bramkę z qasm3 w rekordach.
2. Ideał każdego obwodu identity z qasm3 równa się ideałowi genuine (Δ ≤ 9e-15). Bloki identity są więc ściśle identycznością, bez problemu z barierami czy scalaniem.
3. Obserwabla mean-Z jest symetryczna względem permutacji kubitów, więc żaden błąd mapowania kubit↔drut nie może przesunąć ⟨O⟩.
4. Liczby bramek i czas ASAP są identyczne dla trzech wariantów: star λ3 to 36 CZ, 60 PRX i 2.40 µs; circular λ5 to 195 CZ, 400 PRX i 15.5 µs.

Dowody za mechanizmem T1. Model Aer `sim/device_model.py` z kalibracją `odra_raw_w01A_start.json` (T1 = 13–24 µs), 32 768 shotów, średnia po 8 punktach:

| model | star identity λ3 / λ5 | star genuine λ5 | circular identity λ3 / λ5 | circular genuine λ5 |
|---|---|---|---|---|
| **sprzęt** | **+0.156 / +0.282** | −0.028 | **+0.403 / +0.568** | +0.021 |
| pełny model | +0.055 / +0.132 | −0.018 | +0.277 / +0.444 | +0.042 |
| T1 → ∞ (T2 bez zmian) | −0.031 / −0.029 | −0.013 | −0.001 / +0.001 | +0.029 |
| bez relaksacji idle | +0.003 / +0.038 | −0.022 | +0.079 / +0.158 | +0.030 |
| tylko depolaryzacja + readout | −0.032 / −0.026 | −0.024 | −0.016 / −0.007 | +0.022 |
| DD (echo T2 w idle) | +0.052 / +0.129 | −0.024 | +0.270 / +0.439 | +0.045 |

Dryf w kierunku +1 pojawia się wyłącznie, gdy model ma T1. Rośnie z λ i z długością obwodu (circular > star). Znika, gdy T1 → ∞, i nie zależy od T2 ani od DD. Per kubit dryfują wszystkie kubity, w symulacji i na sprzęcie. Model odtwarza ok. 50% efektu na star i ok. 75% na circular. Resztę można przypisać realnym czasom bramek i harmonogramowi IQM oraz fluktuacjom T1 (blok ZNE wykonano o 14:06 i 16:36, czyli ok. 6–8 h po zrzucie kalibracji). Kierunek, skalowanie i ablacja są jednoznaczne.

Mechanizm. W `identity_block` druga połowa to sam ciąg CZ (diagonalny, bez PRX), a pierwsza ma pary g·g⁻¹. Stan po U nie jest więc „przetwarzany” przez kolejne U. Tłumienie amplitudy działające po U pcha stan wprost do |00000⟩, czyli ⟨mean-Z⟩ → +1. W genuine `U(U†U)^k` relaksacja zachodzi w środku, a końcowe U obraca ją w przybliżeniu ku U|0⟩. Dlatego genuine stoi płasko, a identity „ucieka”.

Wniosek: to nie bug, ale założenie z docstringu `qem/folding.py:10-11` („Same cost, same function: it should behave like genuine”) jest fałszywe w obecności T1. Wariant identity nie jest kontrolą równoważną szumowo. Nie należy go raportować jako „ZNE z kontrolą identity zawodzi”, tylko jako skutek konstrukcji. Dobrze byłoby to opisać w pracy albo przeprojektować kontrolę, np. wstawiając PRX z pary g·g⁻¹ także w połowie U.

### F3. Analiza prerejestrowana (zadanie 6)
`python -m analysis.prereg_w01 --out review/scripts/tmp/prereg` wykonuje się bez błędu na A+P5. Wyniku nie traktuję jako konfirmacyjnego. Brak nocy B jest obsłużony *bez błędu, ale po cichu*:
- `w01B` nie ma `cdr.csv`, więc jest pomijana. H1, H3 i H6 liczą się na 16 parach zamiast 32 i nie ma żadnego ostrzeżenia ani asercji `n_pairs == 32`.
- Gdyby ktoś wygenerował `w01B/cdr.csv` w trakcie pomiaru nocy B, częściowe dane weszłyby do testu bez śladu, bo `paired()` robi inner join.
- Wyjście na A+P5: H1 p = 0.353, H3 p = 0.851, H6 p = 0.550, H7a p = 0.660, H7b p ≈ 0. Po Holmie odrzucona jest tylko H7b. H4 „pays” = False dla obu rungów. H5: 1 zmiana decyzji, McNemar p = 1.

### F4. Wnioskowanie P5 przy 8 klastrach jest antykonserwatywne
`depth_regression.fit` używa klastrowanego SE z rozkładem normalnym przy G = 8 klastrach (`analysis/depth_regression.py:58-59`). Przy t(G−1) i wild cluster bootstrap (Rademacher, 999 losowań, z restrykcją H0) wychodzi:

| term | p (deklarowane, asympt.) | p t(7) | p wild bootstrap |
|---|---|---|---|
| raw dur | 5e-13 | 1.7e-4 | 0.010 |
| raw cz10 | 0.68 | 0.69 | 0.67 |
| CDR cz10 | 0.002 | 0.018 | 0.020 |

H7b pozostaje istotna. Przy wild bootstrap Holm ×5 daje jednak ok. 0.05, czyli wynik graniczny, a przy G = 8 rozdzielczość tego testu to ok. 1/256. Wartość „p<1e-4” jest optymistyczna. CDR cz10 nie przeżywa korekty Holma przy m = 5, ale nie jest testem pierwszorzędowym.

### F5. Zmiana kalibracji w trakcie P5 i błędne tagowanie
Manifest `w01P5` notuje zmianę kalibracji b1b5d2a8 → 0642097d w trakcie bloku `star_cz52`. Bloki `star_L6` i `star_cz24` wykonano w całości po zmianie: T1 QB1 wzrósł z 15.6 do 20.8 µs, a QB2 z 12.7 do 17.0 µs. Wszystkie 1008 rekordów `star_cz52` mają jednak tag starej kalibracji (zob. B1). Regresja H7 nie zawiera efektu kalibracji.
- Wpływ na wynik (`p5_calib_sens.py`): bez cz24 cz10(raw) = 0.954 i dur = 1.441. Tylko stara kalibracja (bez cz24 i cz52): cz10(raw) = 1.029 (p = 0.87), dur = 1.478 (p = 0.002), cz10(CDR) = 1.70. Jakościowe wnioski H7a/H7b się nie zmieniają. Kontrast cz24 vs idle24 jest jednak w pełni zakłócony kalibracją, a rung cz52, który przestawia znak cz10, jest właśnie tym mieszanym blokiem.

### F6. Ramiona = bloki w czasie (zakłócenie dryftem)
Noc A trwała w praktyce 12.3 h (08:19–20:39 UTC 24.10, z wznowieniem). Każde ramię danego rungu to jeden blok wykonany w innym czasie. Na star twirl_native/near_target wykonano 16:58–19:43, w tym 208 obwodów 2.5 h później po wznowieniu, a off_copies 12:27–13:04. Kontrast H1 w jednym oknie jest więc kontrastem „ramię × godzina” z n = 1 blokiem. Kolejność bloków jest losowana, więc nie ma obciążenia systematycznego, ale wariancja dryftu siedzi w każdej parze punktów i nie jest niezależna między 8 punktami rungu. Wilcoxon zakłada niezależne pary. To zgodne z zasadą projektu „pasma z ≥2 okien”, ale warto to zaznaczyć przy p z jednego okna.

### F7. shared_random: ten sam zbiór treningowy dla wszystkich punktów
`near_clifford_training_circuits(logical[pi], n_train, seed=args.seed)` (`campaign/odra_window.py:207-208`) używa tego samego ziarna dla każdego punktu. Ideały treningowe są identyczne między punktami w 135–140 na 140 przypadków i przyjmują tylko 3 wartości: 0 i ±0.2. Fity H3 w 8 punktach rungu są silnie skorelowane, a regresja ma słabą rozpiętość y, więc pary H3 nie są niezależne. Według docstringu `cdr_training` jest to świadomie „legacy”, ale H3 jest testem pierwszorzędowym.

### F8. Moc H1 po nocy B (zadanie 7)
`power_h1.py`: 16 par z A jest ustalonych, a 16 par B losuję łącznie z wektorów (d_H1, d_H3, d_H6) jednego punktu, co zachowuje korelację w Holmie. H7a/H7b są ustalone na p z P5. Pełny Holm w rodzinie 5 testów, kryterium p_holm < 0.05 i ratio < 1. Po 4000 replikacji na scenariusz:

| scenariusz nocy B | P(H1 sukces) | P(nieskorygowane p<0.05) | mediana p H1 |
|---|---|---|---|
| jak 12 CZ (star) | **0.000** (wygładzony bootstrap: 0.000) | 0.004 | 0.70 |
| jak 39 CZ (circular) | **0.16** (wygładzony bootstrap: 0.17) | 0.60 | 0.042 |
| jak mieszanka nocy A | 0.006 | 0.06–0.07 | 0.28 |

Uwaga: to jest „moc obserwowana” z 8 punktów na scenariusz, więc jest bardzo niepewna. H1 w praktyce musi mieć p < 0.0125, bo H7b zajmuje pierwszy krok Holma. Nawet w najkorzystniejszym scenariuszu szansa sukcesu H1 wynosi ok. 1/6.

---

## 3. Błędy i ryzyka w kodzie (plik:linia)

| # | miejsce | problem | wpływ |
|---|---|---|---|
| B1 | `campaign/odra_window.py:388,407` | `calibration_set_id=cal0` jest pobierany raz na początku bloku i przypisywany wszystkim rekordom bloku. Przy zmianie kalibracji w trakcie bloku rekordy dostają błędny tag; zmiana jest odnotowana tylko w `notes` manifestu. | P5 `star_cz52`: 1008 rekordów otagowanych starą kalibracją, choć część poszła po zmianie (F5) |
| B2 | `analysis/prereg_w01.py:81` vs `preregistration.md:56-57` | Plan wymaga „Holm-adjusted **two-sided** p” dla H7a/H7b, a kod używa jednostronnego p/2. To odstępstwo od prerejestracji, antykonserwatywne o czynnik 2, gdy znak się zgadza. | Teraz bez zmiany decyzji (H7b p≈0, H7a p=0.66), ale trzeba to zgłosić jako odstępstwo albo poprawić przed nocą B |
| B3 | `analysis/prereg_w01.py:30-37,129-145` | Brak asercji kompletności: `paired()` robi inner join, a `run()` po cichu pomija brakujące noce i liczy na 16 parach. Częściowy `w01B/cdr.csv` też by wszedł. Liczność rodziny Holma zależy od tego, czy istnieje `w01P5/cdr.csv`. | Ryzyko raportu „konfirmacyjnego” na niepełnych danych |
| B4 | `analysis/depth_regression.py:58-59` | Klastrowany SE z G=8 i referencją normalną (bez `use_t`, bez CR2 / wild bootstrap) oraz bez efektu kalibracji/okna, gdy kalibracja zmienia się w obrębie okna. | p zaniżone o 1–8 rzędów wielkości (F4); zakłócenie kalibracją (F5) |
| B5 | `qem/cdr_fit.py:127-131` | `spread_x_variance` = model shot noise + `var(frames)` targetu, a `var` wartości z ramek już zawiera shot noise, więc shot noise jest liczony podwójnie. Korekta EIV jest za duża (częściej wchodzi cap 4×). | Tylko fit EIV ramienia spread; nagłówkowe OLS bez wpływu |
| B6 | `qem/folding.py:8-11,80-105` | Kontrola `identity` nie jest równoważna szumowo z genuine: T1 po U nie jest „przetwarzane” (F2). Docstring twierdzi co innego. | Błąd interpretacyjny, nie numeryczny |
| B7 | `noisy_sim.py:494-502` + `odra_window.py:181,220,227` | `measure_all()` jest dokładane po routingu, więc clbit q = drut q, a nie kubit logiczny q. `logical_final_wires` zakłada w docstringu, że „clbit q is logical qubit q”. Dla routowanego circular counts są indeksowane drutem fizycznym. | Zerowy dla mean-Z (symetryczna); błąd utajony dla każdej obserwabli niesymetrycznej i dla `w_neg_marg_max` |
| B8 | `prereg_w01.py:94-108` (H4) | „ZNE < raw” porównuje ZNE z 24 576 shotów z raw z jednego obwodu λ1 (8192 shoty). Raw w H4 (0.069/0.158) to nie raw z tabel CDR (0.0737/0.1608). Kryterium „err_zne < err_garbage” porównuje same średnie, bez testu. | Interpretacja/raportowanie; dwa różne „raw” w pracy |
| B9 | `odra_window.py:472-481` | `floor` dla każdego wariantu to garbage λ5 tego punktu, więc dla wariantu garbage `floor_tracking` jest trywialnie |ĉ₁(E₁−f)| względem samego siebie. Identity i garbage współdzielą też punkt λ1 z genuine (korelacja par w teście ZNE<garbage). | Drobne, diagnostyczne |
| B10 | `FLOOR = 1e-4` (prereg, depth_regression) | 1 błąd OLS (star off_copies p18: 5.5e-5) jest obcinany przed logarytmem. | Znak różnicy bez zmian; pomijalne |

Nie znalazłem błędów w: dopasowaniu OLS (`qem/cdr_fit.fit_ols`), współczynnikach Richardsona (15/8, −5/4, 3/8), W_neg, SNR, `qem.zne.probabilities` (obie konwencje są poprawne), konstrukcji twirlu (`B = G A G†`, `evolve(frame="s")`), planie budżetu (`qem/arms.py`) ani w Holmie.

---

## 4. Podsumowanie
- Wszystkie deklarowane liczby nocy A i P5 odtwarzają się z `counts.jsonl` z dokładnością maszynową. **Brak niezgodności (MISMATCH: 0).**
- Budżety są równe (1 032 192 na punkt na ramię; ZNE genuine 24 576). Szkielety CZ zgadzają się w 100%, a ramki natywnego twirlu odtwarzają obwód dokładnie.
- Zastrzeżenia statystyczne: p dla P5 są antykonserwatywne (8 klastrów); w P5 zmieniła się kalibracja i rekordy są źle otagowane; ramiona są zakłócone czasem bloku; pary H3 są skorelowane (wspólny zbiór treningowy).
- Anomalia identity to fizyka (T1 + identyczność bez „przetwarzania” stanu), a nie bug, ale wariant nie jest poprawną kontrolą.
- Moc H1 po nocy B: ≈0% (B jak 12 CZ), ≈16–17% (B jak 39 CZ), ≈0.6% (mieszanka).
