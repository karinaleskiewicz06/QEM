# Skrypt wystąpienia: „Gdzie mitygacja błędów przestaje się opłacać”

Prezentacja: https://claude.ai/artifact/2F4XsBzd6iHtBBAqM2wpZG (36 slajdów, ok. 25 min + pytania).
Te same teksty są w notatkach prelegenta każdego slajdu.

**Jedno zdanie, które ma zostać w głowie słuchaczy:**
„Sprawdziliśmy na prawdziwym procesorze, do jakiej głębokości mitygacja naprawdę pomaga. Pokazujemy, gdzie przestaje działać i dlaczego.”

**Trzy przekazy (wracaj do nich):**
1. Mitygacja ma termin ważności, a twirling go wydłuża.
2. Część „zysku” z mitygacji to iluzja i umiemy ją wykryć (kontrola garbage, pre-rejestracja).
3. Wiemy, czego symulacja nie widzi: części błędu na bramkach CZ.

---

## Część 0–1: otwarcie (ok. 4 min)

### 1 · Okładka
„Dzień dobry. Opowiem, gdzie mitygacja błędów przestaje się opłacać. Porównujemy trzy techniki: ZNE, CDR i twirling Pauliego na pięciokubitowym procesorze IQM ODRA 5. Porównujemy je uczciwie, przy tej samej liczbie pomiarów, i szukamy punktu, od którego każda z nich przestaje pomagać.”

### 2 · Spis treści
„Plan: najpierw co już wiadomo i czego nie wiadomo. Potem czym jest mitygacja i jak działają metody, z matematyką. Dalej eksperyment, wyniki, a na końcu najważniejsze: dlaczego metody zawodzą tam, gdzie zawodzą.”

### 3 · Stan nauki i luka (NOWY)
- „CDR (Czarnik 2021) uczy się szumu na obwodach Clifforda. vnCDR (Lowe 2021) był w symulacji 1,8× lepszy od CDR.”
- „ZNE z foldingiem (Giurgica-Tiron 2020) działa na płytkich obwodach. Duże pokazy na sprzęcie robił IBM (Kim 2023).”
- „Duże porównania metod (Russo 2023, Bultrini 2023) to głównie symulacje. Nie mówią, przy ilu bramkach CZ metoda przestaje się opłacać.”
- „Teoria (Quek 2024): koszt rośnie wykładniczo, ale bez konkretnego budżetu bramek.”
- **Luka, cztery pytania:**
  1. Przy ilu CZ kończy się zysk, z twirlingiem i bez.
  2. Czy symulator z kalibracji przewiduje błąd po mitygacji.
  3. Czy vnCDR działa na sprzęcie.
  4. Czy mitygacja zmienia decyzje klasyfikatora.
- Uczciwie: „Kontrolę garbage i stałą κ bierzemy z literatury (Köster i Mauerer, Scavino Alfaro) i powtarzamy je na innym urządzeniu.”
- Przejście: „Najpierw krótko, czym jest mitygacja.”

### 4 · Przekładka 01: QEM, a nie QEC
„Pierwsza część: definicja i dlaczego właśnie mitygacja.”

### 5 · Czym jest QEM
„Mitygacja nie dodaje kubitów. Uruchamiamy obwód lub jego warianty wiele razy i łączymy wyniki klasycznie. Nie naprawiamy stanu, tylko estymatę liczby ⟨O⟩. Ceną są pomiary, a koszt rośnie wykładniczo z szumem.”

### 6 · Dlaczego nie QEC
„Korekcja błędów potrzebuje wielu fizycznych kubitów na jeden logiczny, wierności poniżej progu i pomiaru w trakcie obwodu. Pięć kubitów tego nie ma. Sprawdziliśmy to sami kodem [[4,2,2]] na Garnecie: detekcja błędów pogarszała wynik, z 0,22 do 0,79 przy spadającej akceptacji.”

---

## Część 2: metody (ok. 6 min)

### 7 · Przekładka 02
„Druga część: metody, z intuicją i wzorami.”

### 8 · Dwie metody i jedna technika wspierająca
„ZNE celowo wzmacnia szum i ekstrapoluje do zera. CDR uczy się, jak szum zniekształca wynik, na obwodach, które umiemy policzyć. Twirling Pauliego zamienia błąd koherentny w stochastyczny, łatwiejszy dla CDR.”

### 9 · Szum ściska sygnał
„Model roboczy: wynik zmierzony = podłoga + (ideał − podłoga) · e^(−γλ). ZNE idzie po osi λ do zera, a CDR odwraca to ściśnięcie liniowym dopasowaniem. Zapamiętajcie słowo „ściśnięcie”, bo na końcu wyjaśnia, dlaczego decyzje są odporne.”

### 10 · ZNE: folding i Richardson
„Folding: U → U(U†U)^k, czyli ta sama funkcja z λ razy większym szumem dla λ = 1, 3, 5. Richardson z wagami 15/8, −5/4, 3/8. Folding robimy na obwodzie natywnym, żeby kompilator nie skasował U†U.”

### 11 · ZNE wymienia obciążenie na wariancję
„ZNE zmniejsza obciążenie, ale mnoży wariancję o κ. Dla {1,3,5} κ ≈ 14,7. Poniżej progowego budżetu S* ZNE szkodzi, powyżej pomaga. To jest falsyfikowalne i to zmierzyliśmy (slajd 29).”

### 12 · Gdy sygnał zniknie
„Jeśli obwody λ = 3 i 5 nie niosą sygnału, Richardson daje 15/8 · E₁ − 7/8 · f, czyli zwykłe przeskalowanie raw. Dlatego mamy trzy kontrole: garbage-folding (ten sam koszt, zniszczony sygnał), ujemną masę W_neg i SNR. Progi są zamrożone w pre-rejestracji.” **Ten wzór wróci na slajdzie 32.**

### 13 · CDR
„Obwody treningowe: kąty zaokrąglone do Clifforda, ten sam szkielet CZ co cel. Ideał liczymy klasycznie, mierzymy na ODRZE i dopasowujemy prostą. Dla szumu depolaryzującego to jest dokładne. Błąd koherentny psuje liniowość i r² spada.” **To wróci na slajdzie 33.**

### 14 · Twirling Pauliego
„Losowa ramka Pauliego wokół każdej CZ. Bez szumu obwód liczy to samo, a po uśrednieniu kanał błędu staje się kanałem Pauliego. Cena: M ramek, każdą mierzymy osobno, dlatego porównujemy przy równym budżecie.”

### 15 · Logiczny vs natywny
„Różnica tylko w kolejności: ramki przed transpilacją albo po niej. Natywny twirluje też CZ ze SWAP-ów.”

### 16 · Scalanie bramek
„Bez scalania twirling wydłuża obwód 2,4–2,8 razy w bramkach PRX, a po scaleniu tylko 1,2–1,35 razy. To był nasz pierwszy, ujemny wynik twirlingu natywnego, i stąd poprawka.”

### 17 · Równy budżet
„Każde ramię CDR wydaje dokładnie tyle samo pomiarów. Kluczowa kontrola to off_copies, czyli te same kopie bez twirlingu: daje taką samą redukcję wariancji. Różnica off_copies vs twirl to czysty efekt twirlingu.”

### 18 · Spread
„Ten sam budżet, ale 120 różnych obwodów po jednej ramce zamiast 20 po sześć. Regresja widzi więcej punktów.”

---

## Część 3: eksperyment (ok. 3 min)

### 19 · Przekładka 03
„Trzecia część: na czym i jak mierzyliśmy.”

### 20 · Pytanie badawcze
„Mitygacja kosztuje pomiary, więc porównujemy metody, licząc ten koszt. Szukamy granicy opłacalności wzdłuż rosnącej liczby CZ: 12, 30, 39, 57.”

### 21 · ODRA 5
„Gwiazda z hubem: każda bramka dwukubitowa przechodzi przez QB3, więc routing jest drogi, a każdy SWAP to trzy CZ. Błąd CZ 0,7–1,2%, T2* 3–6 µs.”

### 22 · Zbiór danych
„Two curves w 8 wymiarach, wersja trudna, w której wiele punktów leży blisko granicy. To ważne dla pytania o decyzje.”

### 23 · Obciążenie
„Ta sama architektura klasyfikatora, cztery wzorce splątania: 12, 30, 39 i 57 CZ po kompilacji na gwiazdę. Każdy wzorzec ma własne wytrenowane wagi.”

### 24 · Metodologia
„Wszystkie metody jednego szczebla w tej samej nocy i kalibracji. 8 punktów na okno, losowana kolejność bloków. Plan analizy i kod zamrożone w gicie (tag prereg-v1) przed analizą.”

---

## Część 4: wyniki (ok. 6 min)

### 25 · Przekładka 04: Wyniki
„Okno w01 jest kompletne: noc A, noc B i noc P5. Do tego w02vn (vnCDR) i w04m (1300 surowych decyzji). Okno z DD jeszcze trwa.”

### 26 · Twirling i CDR (dawny slajd 25)
- „Przy 12 CZ nie ma czego poprawiać, bo błąd CDR wynosi około 0,02.”
- „Im głębszy obwód, tym większy zysk: przy 39 CZ ×0,68, a przy 57 CZ błąd spada z **0,152 do 0,053**, prawie trzykrotnie.”
- „Uczciwie: test zarejestrowany przed analizą daje 20 z 32 par, **p = 0,092**. To trend, nie dowód, bo mamy 8 punktów na szczebel.”
- „Logiczny i natywny twirling dają to samo.”

| CZ | bez twirl. | z twirl. | wygrane | iloraz |
|---|---|---|---|---|
| 12 | 0,022 | 0,015 | 4/8 | 1,41 |
| 30 | 0,076 | 0,053 | 4/8 | 0,93 |
| 39 | 0,053 | 0,040 | 7/8 | 0,68 |
| 57 | 0,152 | 0,053 | 5/8 | 0,34 |

### 27 · Która metoda kiedy (dawny slajd 26)
- „Najważniejsza kolumna to garbage. Przy 12 CZ ZNE bije garbage, więc tam jest prawdziwe.”
- „Od 30 CZ ZNE i garbage są równe: 0,064 i 0,068, 0,112 i 0,103, 0,170 i 0,161. Zysk ZNE to tam artefakt.”
- „CDR z twirlingiem trzyma około **0,05 aż do 57 CZ**, ale za około 42× więcej shotów.”

| CZ | raw | ZNE | garbage | CDR+tw | spread |
|---|---|---|---|---|---|
| 12 | 0,074 | 0,045 | 0,137 | 0,015 | 0,012 |
| 30 | 0,110 | 0,064 | 0,068 | 0,053 | 0,056 |
| 39 | 0,161 | 0,112 | 0,103 | 0,040 | 0,068 |
| 57 | 0,223 | 0,170 | 0,161 | 0,053 | 0,137 |

### 28 · Co napędza degradację (P5)
„Do obwodu dokładamy albo pary CZ dające identyczność, albo przerwy o tej samej długości. Surowy błąd napędza **czas** obwodu, ×1,43 na µs, i to jedyna potwierdzona hipoteza z pre-rejestracji (H7b). Sama liczba CZ nie jest istotna. Po CDR obraz się odwraca: zostaje część od CZ (×1,34 na 10 CZ).”
Na pytania: przy 8 klastrach i bardziej konserwatywnej korekcie p dla H7b jest na granicy, około 0,05.

### 29 · Stała κ
„Pilot: zmierzona κ zgadza się z przewidywaną (15,8 vs 14,66; Neyman 12,5 vs 11,6), więc podział Neymana obniża próg opłacalności ZNE. Otwarte pytanie: {1,3,5,7}.”

### 30 · Decyzje klasyfikatora
„Mitygacja zmienia decyzje tylko blisko granicy. W pilocie wszystkie zmiany są w połowie punktów najbliżej granicy. W w01 na 32 punktach: raw 29/32, CDR z twirlingiem 31/32, czyli 2 naprawione, 0 zepsutych.”

---

## Część 4b: dlaczego (ok. 4 min), czyli to, co wzmacnia pracę

### 31 · Wyniki negatywne są twarde (NOWY)
„Ktoś zapyta: czyli nic nie działa? Wynik negatywny jest mocny, jeśli spełnia cztery warunki, a nasze je spełniają:
1. Testy zamrożone przed analizą.
2. Kontrola pozytywna: ten sam potok wykrywa efekty, gdy są. CDR bije raw w 27/32 parach (p = 0,00002), a czas obwodu ma p ≈ 10⁻¹².
3. Kontrola zerowa: garbage.
4. Symulacja przewidziała zysk vnCDR z mocą 84–100%, a na sprzęcie go nie ma (1,21; p = 0,63).
Uczciwie: twirling to słaby wynik zerowy, bo 8 punktów to za mało, więc nie mówię, że twirling nie działa.”

### 32 · Dlaczego ZNE zawodzi (NOWY)
„Tabela z ODRY (w04m, 100 punktów): s to ile sygnału zostaje. Przy 12 CZ 0,85, przy 57 CZ 0,24. ZNE potrzebuje obwodów λ = 3 i 5, które mają 3 i 5 razy więcej CZ:
- przy 12 CZ to 36 i 60 CZ, więc sygnał jest i ZNE działa;
- przy 39 CZ to 117 i 195 CZ, więc sygnału nie ma.
Wtedy Richardson to tylko 15/8 · raw, dokładnie to, co robi garbage. Druga przyczyna: odczytu nie foldujemy, więc ZNE zostawia błąd odczytu (+0,03, ściśnięcie 0,96).
**ZNE działa tylko tam, gdzie obwody ze wzmocnionym szumem wciąż niosą sygnał.**”

### 33 · Dlaczego CDR bez twirlingu słabnie (NOWY)
„CDR zakłada prostą. r² bez twirlingu spada z 0,97 do 0,35 przy 57 CZ, a z twirlingiem zostaje 0,72. Dwa niezależne dowody, że winne są CZ:
1. Symulator z kalibracji trafia błąd raw (×1,04), ale błąd po CDR zaniża **×1,88**, a po twirlingu znów się zgadza.
2. Przy tej samej długości obwodu nadwyżka po CDR rośnie przy CZ (+0,037), a przy czekaniu prawie nie (+0,006), p = 0,0003.
Wniosek: ten błąd zależy od konkretnego obwodu, więc obwody Clifforda go nie uczą, a twirling go uśrednia. vnCDR dokłada folding, więc dziedziczy problem ZNE. To nasza interpretacja.”
**Mechanizm, dokładnie tymi słowami:** „twirling działa empirycznie, a mechanizm wykracza poza prosty błąd ZZ na CZ”.

### 34 · Dlaczego decyzje są odporne (NOWY)
„Prawie dowód: raw ≈ s · ideał + c, więc znak zmienia się tylko, gdy |ideał| < |c|/s, czyli przy granicy. CDR to a · raw + b, więc dla decyzji tylko przesuwa próg z 0 do −b/a. Dane:
- ODRA, 1300 decyzji: zmienione 91, mediana ich marginesu 0,053 wobec 0,331 dla wszystkich;
- symulacja na 3 zbiorach: 132 naprawione, 32 zepsute;
- dokładność względem etykiet bez zmian (0,735 → 0,727).
Wniosek dla QML: dokładność jest dużo bardziej odporna niż ⟨O⟩.”

---

## Część 5: zamknięcie (ok. 2 min)

### 35 · Przekładka 05
„Na koniec wnioski.”

### 36 · Wnioski
„Cztery rzeczy:
1. Bez twirlingu zysk CDR maleje ×0,75 na +10 CZ, a z twirlingiem zostaje 3,6–4,6× do 57 CZ.
2. ZNE działa tylko, gdy obwody λ = 3, 5 niosą sygnał, a vnCDR nie powtórzył zysku z symulacji.
3. Symulacja trafia raw, ale zaniża błąd po CDR ×1,9, a ta część siedzi na CZ.
4. Decyzje zmieniają się tylko przy granicy.
Limitacje mówię sama: 8 punktów na szczebel, jedno urządzenie, jedno okno, w nocy B zmiana kalibracji. Co dalej: DD + CDR (pomiar trwa), powtórka w drugim oknie, więcej punktów, artykuł. Dziękuję.”

---

## Pytania, które mogą paść

| Pytanie | Odpowiedź |
|---|---|
| Ile punktów? | 8 na szczebel w głównych porównaniach (32 pary). 100 na szczebel w teście decyzji (w04m) i w pilocie. |
| Czy twirling działa? | Trend rośnie z głębokością, przy 57 CZ prawie 3× mniejszy błąd. Test zarejestrowany: p = 0,092, więc nie potwierdzamy. Za mało punktów. |
| Czy to nie jest znany wynik dla ZNE? | Kontrola garbage pochodzi od Köstera i Mauerera. My ją powtarzamy na innym urządzeniu i dokładamy wyjaśnienie z pomiaru sygnału s. |
| Dlaczego nie korekta odczytu? | Na ODRZE jest możliwa i po niej ZNE przy 12 CZ spada z 0,045 do 0,016, ale to analiza eksploracyjna. Do artykułu. |
| Co z DD? | Pomiar trwa, nie wyciągamy wniosków. |
| Czy pre-rejestracja była przed danymi? | Przed analizą. Noc A już się zaczęła, gdy zamroziliśmy plan. Mówimy to w artykule. |
| Czy to ZZ crosstalk? | Nie twierdzimy tego. Dopasowanie samego kąta koherentnego nie odtwarza sprzętu. Twirling działa empirycznie, a mechanizm wykracza poza prosty błąd ZZ na CZ. |
| Czemu kalibracja to problem? | W nocy B kalibracja zmieniła się między ramionami przy 57 CZ. Pre-rejestracja wymaga analizy wrażliwości, którą robimy. |
