# Recenzja: „Gdzie mitygacja błędów przestaje się opłacać — ZNE, CDR i twirling Pauliego na IQM ODRA 5”

Recenzent: zewnętrzny, krytyczny (QEM / statystyka). Data: 2026-10-25.
Zakres: gałąź `paper-odra-campaign` (HEAD `41fea80`, tag `prereg-v1` = `ecaa139`), dane `runs/odra_campaign/w01A`, `w01P5`, pilotaże `runs/odra_pilot/*`, archiwalne CSV w katalogu głównym, skrypt `prezentacja_teoria/prezentacja_teoria.tex`, tekst slajdów (`deck_text.md`), szkic `spec/draft_artykul_QEM_ODRA.md`.
Noc B (`w01B`) traktuję jako niekompletną: do 25.10 zapisano 400 z ~12 000 rekordów, potem ODRA przestała odpowiadać (`runs/odra_campaign/w01.log`).
Wszystkie liczby poniżej przeliczyłem sam z `cdr.csv`, `zne.csv` i `counts.jsonl`, wyłącznie offline. Nie uruchamiałem nic, co łączy się z IQM, i nie zmieniałem żadnego pliku w repozytorium.

---

## 1. Werdykt (streszczenie)

W obecnej formie to **solidny warsztat eksperymentalny bez potwierdzonego wyniku głównego**. Pre-rejestrowana hipoteza H1 (twirling obniża błąd CDR przy równym budżecie) na połowie danych daje p = 0,35, a znak efektu jest przeciwny na dwóch szczeblach. Moja symulacja mocy daje szansę na jej potwierdzenie po nocy B na poziomie ~15% (próg Holma), a ~57% tylko przy optymistycznym założeniu i bez korekty. Publikowalne jest to, co faktycznie stoi:

- infrastruktura kontroli: równy budżet, `off_copies`, garbage folding na obwodzie natywnym, scalanie 1q;
- replikacja degeneracji Köstera–Mauerera na innym urządzeniu IQM;
- negatywny wynik kontroli „identity”;
- rozdzielenie CZ i czasu w P5, ale wyłącznie jako wynik ostrożny.

Realnie: **short paper / workshop** (IEEE QCE 2027 jako short paper, poster albo warsztat; ewentualnie QTML lub warsztat QC przy dużej konferencji) z prawdopodobieństwem przyjęcia ~60–70% po poprawkach. **Full paper na QCE 2027**: ~30–40%, i tylko po przeformułowaniu tezy oraz analizach offline z §8. **IEEE TQE**: ~20–30%. **Quantum**: ~10%. **PRX Quantum**: <5%.

---

## 2. Co badanie faktycznie ustala, a co deklaruje

### 2.1 Co jest ustalone (na danych w01A + w01P5)

1. **Degeneracja Richardsona przy zaniku sygnału, wykryta kontrolą garbage** (39 CZ). λ = 3 i 5 leżą na podłodze ~0,02 dla każdego punktu, niezależnie od znaku ideału (`w01A/zne.csv`, wiersze circular). Genuine 0,112 vs garbage 0,103 (Wilcoxon genuine < garbage: p = 0,84). To replikacja Köstera–Mauerera na ODRZE, nie odkrycie: oni wprowadzili garbage folding i test „zero-cost” na sprzęcie IQM (sprawdziłem abstrakt arXiv:2607.09360).
2. **ZNE przy 12 CZ jest „prawdziwe” tylko w słabym sensie.** Jest lepsze od garbage (p = 0,012), ale **nie** jest lepsze od raw (p = 0,47; 4/8 wygranych). H4 nie jest spełniona na żadnym szczeblu.
3. **Kontrola identity folding jest niepoprawna konstrukcyjnie.** Przy 39 CZ ⟨O⟩(λ = 3, 5) ucieka do 0,41 i 0,57, przy 12 CZ do ~0,2–0,3. To wynik negatywny, ale wartościowy. Uwaga: dało się go przewidzieć przed nocą (§4, W8).
4. **Twirling poprawia liniowość mapy CDR.** Δr² (twirl_native − off_copies) wynosi +0,116 przy 39 CZ (8/8 par) i +0,017 przy 12 CZ (7/8), Wilcoxon na 16 parach p < 0,001. To najmocniejszy i najbardziej spójny z pilotażami (`twirl_pairs_all.csv`, kolumna `d_r2`) efekt w danych. Nie był jednak pre-rejestrowany.
5. **P5: przy stałej liczbie bramek czas trwania silnie podnosi surowy błąd** (×1,43/µs, p < 1e-12). Wynik jest odporny na usunięcie zmienionej kalibracji i na leave-one-point-out (przeliczyłem).

### 2.2 Co jest deklarowane, a nie ma pokrycia (lista do poprawy)

| # | Teza | Gdzie | Problem |
|---|---|---|---|
| C1 | „Przy 39 CZ twirling obniża błąd CDR o ~30% przy tym samym budżecie” (tytuł slajdu) | slajd 25; skrypt §Wyniki, l. 798–799 | n = 8. Test znaków p = 0,035 (jednostronny, post hoc, na podzbiorze, bez Holma), Wilcoxon p = 0,07. Test pre-rejestrowany (pooled): p = 0,35. Tytuł slajdu musi mówić „opisowo, n = 8, nieistotne w teście głównym”. Średnie 0,053 → 0,040 to −25%, nie −30%. |
| C2 | „12 CZ: nie ma czego poprawiać. Błąd CDR ~0,02, blisko szumu shotów” | slajd 25; skrypt l. 800–803; wnioski l. 949 | **Nieprawda.** SE celu w `off_copies` to √(V/(MS)) ≈ 0,002, razy nachylenie 1,2 ≈ 0,0024. Szum fitu przy 20 punktach z rozpiętością ~0,3 to podobny rząd. Razem ~0,004, a błąd `off_copies` wynosi 0,022, czyli ~5–10× więcej. Punkty 6 i 21 mają błąd 0,04 i 0,07 (`w01A/cdr.csv`). To błąd **systematyczny** (niedopasowanie treningu do celu, §4 W6). Prawdziwy powód, dla którego twirling przegrywa przy 12 CZ, jest inny: **wariancja między ramkami**. Dwa niezależne zestawy 6 ramek dla tego samego celu różnią się o RMS ≈ 0,008 (12 CZ) i 0,010 (39 CZ). To 4–5× więcej niż szum shotów. Przy małym obciążeniu twirling kupuje wariancję. |
| C3 | „CDR z twirlingiem ma najmniejszy błąd na obu szczeblach” | slajd 31 pkt 3; skrypt l. 855, 954 | **Nieprawda.** Przy 12 CZ najlepsze jest `spread` (0,012 < 0,015). Przy 39 CZ najlepsze są `twirl_logical:shared_random` (0,025) i `twirl_native:shared_random` (0,032), oba lepsze od `twirl_native:near_target` (0,040). Wybrano ramię, które pasuje do narracji. Co gorsza, najlepsze przy 39 CZ jest ramię z **legacy zbiorem treningowym**, który DATA_NOTES §4 opisuje jako wadliwy. To podważa uzasadnienie projektu `near_target` i musi być jawnie omówione. |
| C4 | „W_neg = 0 i SNR 4 tego nie wykryły — tylko garbage” | slajd 26; skrypt l. 835–853; slajd 31 pkt 2 | Sprzeczność wewnętrzna: skrypt chwilę później pokazuje, że **floor tracking** (0,016 vs 0,17 przy 12 CZ) wykrył degenerację. „SNR nie wykrył” to z kolei **błąd definicji, nie odkrycie**. SNR = \|E(λmax)\|/SE mierzy odległość od zera, a podłoga mean-Z jest przesunięta przez T1 i asymetrię odczytu (f ≈ 0,02). SNR = 4 to po prostu SNR podłogi (`qem/zne.py:331–333`). Poprawnie: \|E(λmax) − f\|/SE. W_neg z kolei z konstrukcji nie widzi degeneracji, gdy rozkłady przy λ = 1, 3, 5 są wszystkie bliskie jednostajnego: p̂ = 1,875p₁ − 0,875u jest ujemne dopiero przy p₁ < 0,47u. To warunek konieczny, nie dostateczny. Trzeba to napisać wprost. |
| C5 | „ZNE uczciwe przy 12 CZ” / mapa reżimów „raw → ZNE → CDR” | slajdy 26, 31 | ZNE przy 12 CZ nie bije raw (p = 0,47). Błąd ZNE ma przy tym **stały dodatni znak**: ZNE − ideał = +0,049, +0,049, +0,044, +0,044, +0,051, +0,039, +0,010, +0,076. To offset odczytu i T1, którego folding nie skaluje. Brak REM (readout error mitigation) systematycznie upośledza ZNE względem CDR, które offset wchłania wyrazem wolnym b. Mapa reżimów porównuje więc „ZNE bez REM” z „CDR”, a to nie jest porównanie metod. |
| C6 | Tabela „raw” 0,074 / 0,161 obok ZNE | slajd 26; skrypt l. 812 | Kolumna raw pochodzi z celów CDR (6×8192 shotów), a ZNE ma własny raw przy λ = 1 (1×8192): 0,069 / 0,158. Mieszanie źródeł; trzeba podać raw ZNE obok ZNE. |
| C7 | „Surowy błąd napędza czas obwodu, a nie liczba CZ” | slajd 27 (tytuł), slajd 31 pkt 4 | Zbyt mocno. (a) Kontrast CZ vs idle jest **w pełni zakłócony porą nocy**. Wszystkie bloki idle i baza `star` szły 21:01–02:36 UTC, wszystkie bloki `cz` 04:21–09:21 UTC. `cz24` (cały) i część `cz52` szły w **nowej kalibracji** z wyższym T1 (QB1 15,6 → 20,8 µs, QB2 12,7 → 17,0 µs; `calibrations/odra_w01P5_{start,end}.json`). To zaniża współczynnik CZ. (b) Wynik zależy od transformacji. Model liniowy: +0,010 na 10 CZ, p = 0,07. Log-model bez punktów z \|ideal\| < 0,1 (p0, p3): **×1,107 na 10 CZ, p < 0,001**. Średnie surowe błędy cz > idle na wszystkich trzech poziomach (0,094/0,090; 0,159/0,112; 0,177/0,147). Uczciwie: „czas dominuje; wpływu CZ przy stałym czasie ta noc nie rozstrzyga”. |
| C8 | „H7b potwierdzona … przejdzie każdy próg Holma” | skrypt l. 876 | Statystycznie tak. Ale „czas” to **czas wyliczony** (ASAP przy t_CZ = 60 ns, t_PRX = 20 ns; `odra_window.py:171–172`), nie zmierzony, a IQM zaokrągla `delay` w górę (`run_hardware.py:103`). Do tego czas jest zakłócony porą nocy (C7a). Interpretacja przyczynowa wymaga zastrzeżenia. |
| C9 | „+10 PRX ×1,12” | slajd 27 | Z próby `all`, czyli z rungami L6/L9/L13 = **innymi klasyfikatorami** z innymi ideałami. Punkty były stratyfikowane po marginesach star L3. To nie jest efekt PRX. Usunąć albo oznaczyć jako zakłócony. |
| C10 | „Modele L6/L9/L13 wypadają gorzej niż wstawki CZ … potwierdza wniosek z pilota” | skrypt l. 893–896 | Jak wyżej: inne funkcje, inne rozkłady ideałów. Do tego obwody treningowe L13 mają **27 PRX wobec 70 w celu** (`counts.jsonl`). CDR jest tam niedopasowane szumowo, więc to nie jest test „PRX vs CZ”. |
| C11 | κ: „Neyman 12,5 ± 1,1” | slajd 28; skrypt tab. κ | **Pominięte drugie okno** Neymana {1,3,5}: `runs/odra_pilot/p3_kappa_n135/kappa.csv` daje **20,7 ± 14,7** (przewidywanie 11,9). Przy S = 4096 bias_rms skacze tam do 0,078, czyli dryf w oknie. Raportować oba okna. Archiwalne `odra_kappa_k7.csv` daje κ{1,3,5,7} = 48 ± 6 (równy podział, przewidywanie 44,6), co warto zestawić z „26 vs ~37” dla Neymana. |
| C12 | McNemar: „przy niezależności od marginesu szansa byłaby rzędu 2⁻³¹” | skrypt l. 934–935; slajd 29 | Hipoteza zerowa to chochoł. Sam skrypt wyprowadza (l. 924–925), że zmiana decyzji jest możliwa **tylko** przy \|Ô − E\| ≥ \|E\|, czyli mechanicznie przy małych marginesach. Ta liczba nic nie testuje; usunąć. Przy 12 CZ CDR **pogarsza** decyzje (b/c = 4/1), co warto powiedzieć wprost. |
| C13 | „Pilot z 3 okien: 11 z 12 par, iloraz 0,51 / 0,54” jako tło dla H1 | slajd 25 notatki; skrypt l. 808 | Pilot dawał przy 12 CZ ilorazy 0,34 (p1 native), 0,22 (p3 native), 0,57 (p1 logical). w01 przy 12 CZ daje **1,41**. To klasyczna klątwa zwycięzcy: hipotezy zbudowane na pilotach (średnie z 4 punktów) przeszacowały efekt. Trzeba to nazwać, a nie tłumaczyć „szumem shotów”. |
| C14 | „Uśredniony kanał staje się kanałem Pauliego. Znika jego część koherentna.” | slajd 13 | Tylko w granicy pełnego uśrednienia (16 Pauli na CZ, M → ∞) i przy błędach 1q niezależnych od bramki. Po scaleniu 1q (`qem/merge1q.py`) ramki zmieniają kąty PRX, więc to założenie nie jest oczywiste. Przy M = 6 zostaje skończona próbka. Napisać „w oczekiwaniu”. |
| C15 | „Dokładne dla szumu depolaryzującego: E = (1−p)O + pf” | slajd 12 | Dokładne dla **globalnego** depolaryzowania. Dla lokalnego szumu na 5 kubitach i obserwabli mean-Z tłumienie zależy od obwodu (wagi Pauliego), więc mapa nie jest wspólna dla treningu i celu. Do tego dochodzą readout i T1. Napisać „dla globalnego”. |
| C16 | „Obwody treningowe: kąty PRX zaokrąglone do Clifforda” (deck) vs „snap a random subset of rotations” (szkic) | slajd 12; `spec/draft_artykul_QEM_ODRA.md` §2.3 | Kod snapuje **wszystkie** rotacje (`qem/cdr_training.py:126–130`), więc trening jest w pełni Cliffordowy, nie near-Clifford w sensie Czarnika. Szkic opisuje inną metodę niż ta, którą zmierzono. |
| C17 | „pre-rejestracja … zanim obejrzeliśmy dane z w01” | slajd 23 | Formalnie prawdziwe, ale slajd nie mówi, że noc A **już się mierzyła**: pierwszy rekord 08:19 UTC, commit planu 08:38 UTC. Nie mówi też, że pierwsza część nocy A szła na **innym, brudnym commicie** (`4b0d849`, `git_dirty: True`; §9 B10). Uczciwe sformułowanie to „pre-analysis plan” (tak jest w `preregistration.md`); slajd powinien to powtórzyć. |
| C18 | Szkic: „pre-registered campaign over 12 calibration windows”, „confirm κ on two devices” | `spec/draft_artykul_QEM_ODRA.md` abstrakt i kontrybucje | Autorka zrezygnowała z 12 okien. Kontrybucje 1–3 trzeba przepisać pod realny zakres: 1 okno, 1 urządzenie dla nowych danych. |
| C19 | „Kontrola dryfu: ID kalibracji przed i po bloku” jako kontrola dryfu | slajd 23 | ID kalibracji wykrywa tylko **rekalibrację**, nie dryf. Zrzuty „start/koniec” w obrębie jednego zestawu są bitowo identyczne (`cmp odra_raw_w01A_start.json odra_raw_w01A_end.json` → identyczne). Dryf T1/TLS między rekalibracjami pozostaje niekontrolowany, a ramiona są blokami oddalonymi o godziny (§4 W3). |

---

## 3. Mocne strony metodologiczne

1. **Kontrola równego budżetu z `off_copies`** (`qem/arms.py`). To prawidłowa odpowiedź na typowy błąd literatury („twirling = M-krotne uśrednianie”). Budżet (n_train + 1)·M·S = 1 032 192 jest sprawdzony w kodzie i w danych (`shots_total` w `cdr.csv`).
2. **Trening CDR na obwodzie natywnym celu.** Zgodność szkieletu CZ jest gwarantowana konstrukcyjnie i zweryfikowana w danych: 0 niezgodności (`skeleton_matches_target`) w w01A i w01P5. Diagnoza wad archiwum (DATA_NOTES §1–4: dwie ścieżki kompilacji, niedeterministyczny router, wspólny zbiór treningowy, cichy clamp ZNE) to wzorowa praca forensyczna. Powinna trafić do suplementu.
3. **Folding na obwodzie natywnym, bez retranspilacji**, z barierami. Garbage o identycznym szkielecie i liczbie PRX. Brak clampa; flagi `unphysical` i `fallback_used`.
4. **Pełna proweniencja.** Surowe zliczenia per obwód, QASM3, ramki twirlu, ziarna per obwód, manifest z commitem, kolejnością bloków i ID kalibracji, wznawianie bez duplikatów. Dzięki temu większość poprawek z §8 da się zrobić offline.
5. **Pre-analysis plan z kodem, zamrożony tagiem**, uczciwie opisany jako plan analizy, a nie rejestracja przed zebraniem danych. Zdefiniowana rodzina testów z Holmem, reguły wykluczeń i sensitivity.
6. **Identity insertion (P5)** to dobry pomysł eksperymentalny: ta sama funkcja, rozdzielenie CZ i czasu. Wymaga jedynie lepszej randomizacji.
7. **Stratyfikacja punktów po marginesie** i rotacja zestawów punktów.
8. Uczciwe przyznanie wielu ograniczeń w skrypcie (identity, H4 niespełniona, koszt ZNE vs CDR).

---

## 4. Słabości i zagrożenia trafności (od najpoważniejszych)

**W1 (krytyczne). Moc i heterogeniczność efektu H1.** 8 punktów na szczebel. Logarytmiczne ilorazy twirl/off mają SD ≈ 0,63 (39 CZ) i 1,37 (12 CZ), a znak efektu jest **różny między szczeblami**: star +0,34, circular −0,38. Test zbiorczy na 32 parach jest źle dobrany do hipotezy, która w istocie mówi o interakcji twirl × n_CZ. Szczegóły w §5.

**W2 (krytyczne). Jedno urządzenie, jedno okno, jedna kalibracja na szczebel.** Nie ma żadnej wariancji między oknami. Plan z CLAUDE.md („error bands from ≥2 calibration windows”) nie jest zrealizowany. Noc A i noc B są w różnych zestawach kalibracji (A: `b1b5…`, B: `0642…`), więc porównania między szczeblami 12/39 a 30/57 mieszają kalibrację z liczbą CZ. Garnet wchodzi tylko z archiwum, które miało znane wady (DATA_NOTES §3–4, §6).

**W3 (wysokie). Randomizacja blokowa z jednym blokiem na warunek nie chroni przed dryfem.** W nocy A ramiona tego samego szczebla są oddalone o godziny: star `off_copies` 12:28 UTC, star `twirl_native:near` 16:58–19:43 UTC, czyli najdłuższy blok z przerwą. W P5 kontrast CZ vs idle pokrywa się z porą nocy i ze zmianą kalibracji (C7). Losowanie kolejności przy n = 1 bloku na warunek to randomizacja jednej realizacji. Dryf jest niezidentyfikowalny. Surowe wartości celów twirlowanych mierzonych w różnych godzinach (star: 0,082 / 0,076 / 0,082) sugerują dryf ≲ 0,006, czyli rzędu szumu ramek. To uspokaja, ale nie wystarcza. Zalecenie: przeplatać ramiona na poziomie jobów (ABAB w obrębie zadania).

**W4 (wysokie). Porównanie ZNE vs CDR: nierówny budżet i brak REM.** ZNE ma 24 576 shotów na punkt, CDR 1 032 192 (42×). Do tego ZNE nie ma readout mitigation, więc stały offset +0,04–0,05 przy 12 CZ jest nieusuwalny (C5). W tej postaci mapy reżimów „raw → ZNE → CDR” nie da się obronić. Oba problemy da się zaadresować **offline** (§8 M3, M4).

**W5 (wysokie). Definicje diagnostyk ZNE.** SNR względem zera zamiast względem podłogi (C4). Podłoga f do floor tracking to **jedna** wartość garbage λ = 5 w tym samym punkcie (`odra_window.py:472–481`). Przy 12 CZ garbage nie jest na podłodze (np. star p21: λ3 = +0,046, λ5 = −0,041), więc floor tracking 0,17 jest tam częściowo artefaktem wyboru f. Do tego bliźniak V jest losowany osobno dla λ = 3 i 5, bo ziarno zawiera `lam{s}` (`odra_window.py:248–250`). Docstring `fold_native` sugeruje, że jest jeden V; to trzeba dopisać w metodach. Próg H4 SNR ≥ 2 w pre-rejestracji opiera się na wadliwej metryce. Trzeba to zgłosić jako odstępstwo przy reinterpretacji.

**W6 (wysokie). Zbiór treningowy CDR nie jest „near-Clifford” i nie jest dopasowany szumowo do celu.**
- Snapowane są **wszystkie** rotacje. Ideały są więc z {−1, −0,8, …, 1}, a przy 39 CZ **78–85% obwodów treningowych ma ideał dokładnie 0** (`counts.jsonl`, rekordy train). Nachylenie wyznacza ~3–4 punkty.
- Rotacje z θ = 0 są **usuwane**: obwód treningowy na star ma **10 PRX wobec 20 w celu**, L13 ma 27 wobec 70, a czas szeregowy jest krótszy o 0,2–0,9 µs. Skoro P5 pokazuje, że czas silnie podnosi błąd (×1,43/µs), trening systematycznie widzi **słabszy** szum niż cel. To jeden z kandydatów na resztkowy błąd 0,02 przy 12 CZ i na rosnący błąd CDR z liczbą CZ.
- Twirlowane cele mają więcej PRX niż nietwirlowane (star: 24,5 vs 20) i dłuższy czas (1,21 vs 1,12 µs). Porównanie twirl vs off nie jest więc „czyste fizycznie”: obciąża twirling na niekorzyść, co trzeba opisać.
- Przy 5 kubitach ograniczenie do Cliffordów jest sztuczne (sami to zauważacie w `spec/notatki_nowosc_CDR_twirling.md` §4). Recenzent zapyta, dlaczego nie użyto prawdziwego near-Clifford (k zachowanych bramek nie-Cliffordowych, ideał ze statevectora).

**W7 (średnio-wysokie). Cztery osobno wytrenowane klasyfikatory na drabinie routingu.** Oś „liczba CZ” jest zakłócona funkcją obwodu: inne rozkłady ideałów, inne marginesy, różna dokładność bezszumowa (0,725 / 0,692 / 0,675 / 0,767). Punkty ewaluacyjne są stratyfikowane po marginesach **star L3**, więc dla circular kwartyle nie mają znaczenia. P5 rozwiązuje to tylko dla star. W artykule „routing ladder” trzeba opisywać jako ladder obciążeń, nie jako czystą manipulację liczbą CZ.

**W8 (średnie). Kontrola identity była błędna z konstrukcji.** Bloki tożsamości są doklejane **po** U, a mierzymy w bazie Z. Błędy diagonalne (CZ, defazowanie) komutują z pomiarem i są niewidoczne. Pary g·g⁻¹ kasują błędy koherentne w pierwszym rzędzie. Zostaje głównie T1, które ciągnie do +1. Dało się to przewidzieć w symulatorze z modelem urządzenia przed nocą. Lepszą kontrolą „ta sama funkcja, ten sam koszt, generyczny szum” byłoby U(W†W)^k z losowym W o tym samym szkielecie. Tego wariantu nie zmierzono, więc w artykule wystarczy uczciwy opis i propozycja.

**W9 (średnie). Pre-analysis, a nie pre-data. Hipotezy z pilotów.** Uczciwie opisane, ale efekt C13 (klątwa zwycięzcy) jest dokładnie tym, przed czym taka rejestracja nie chroni. Dochodzi do tego niezgodność kod–plan dla H7 (B2) i zmiana commitu w trakcie nocy A (B10).

**W10 (średnie). Regresja log ε i błędy bliskie zera.** Dla \|ideal\| ≈ 0 błąd to offset readout/T1, a nie tłumienie, i nie skaluje się multiplikatywnie z CZ. Log-model łączy dwa różne mechanizmy. Wynik H7a zmienia się z ×0,96 (p = 0,68) na ×1,11 (p < 0,001) po wyłączeniu dwóch punktów z \|ideal\| < 0,1. Właściwy model fizyczny to tłumienie s = (E − f)/O_ideal z regresją log s, albo model ze znakiem błędu. FLOOR = 1e-4 rzadko się aktywuje, ale log czyni test wrażliwym na przypadkowo małe błędy.

**W11 (średnie). Wielokrotne porównania poza rodziną.** Rodzina Holma ma 5 testów. Deck i skrypt raportują jednak kilkanaście dalszych p-wartości (test znaków per szczebel, Wilcoxon per szczebel, McNemar per szczebel, H4 per warunek, sensitivity, EIV) bez korekty i bez oznaczenia jako eksploracyjne. Każdą p-wartość spoza rodziny trzeba oznaczyć „exploratory, uncorrected”.

**W12 (średnie). Pseudoreplikacja w H3.** Ramiona `shared_random` używają legacy zbioru treningowego (`odra_window.py:207–209` → `cdr.near_clifford_training_circuits` z tym samym ziarnem). Obwody treningowe 1…n−1 są **identyczne dla wszystkich 8 punktów** (DATA_NOTES §4). Fity w obrębie szczebla są silnie skorelowane, więc 16 par H3 to efektywnie znacznie mniej niezależnych obserwacji. Ponadto H3 porównuje twirling logiczny z natywnym tylko na tym wadliwym zbiorze (twirl_logical nie ma wariantu near_target), więc wynik nie przenosi się na ramię główne.

**W13 (niższe). Niekompletny faktoryzm.** `arms.py` opisuje 2×2 (twirling × różnorodność) × zbiór treningowy, ale `DEFAULT_ARMS` (`odra_window.py:92–93`) nie zawiera `spread_off` ani `off_copies:shared_random`. Efektów „dźwigni różnorodności” i twirlingu na `shared_random` nie da się zidentyfikować. H6 (`spread` vs `twirl_native`) miesza obie dźwignie.

**W14 (niższe). Specyfika obserwabli mean-Z.** Podłoga ≠ 0 (T1 i asymetria odczytu: e₁→₀ 2–5% vs e₀→₁ 0,1–0,7%), ideały Cliffordowe dyskretne, często zero. Wyniki CDR i ZNE są w dużej mierze własnością tej obserwabli. Decyzja to znak mean-Z, więc offset odczytu wprost przesuwa granicę decyzyjną.

**W15 (niższe). Słabe zadanie ML.** Dokładność bezszumowa 0,675–0,767. Argument „mitygacja zmienia decyzje” ma słabą wagę praktyczną, gdy klasyfikator idealny myli się w ~30% przypadków. Lepiej mówić tylko o zgodności z decyzją idealną, jak w skrypcie.

---

## 5. Przegląd statystyczny

### 5.1 Czy testy są właściwe
- **Wilcoxon na log ε dla par** jest rozsądny jako test główny (odporny, skala względna). Para to jednak (szczebel, punkt), a efekt jest heterogeniczny między szczeblami (W1), więc test zbiorczy uśrednia przeciwne znaki. Hipoteza merytoryczna („twirling pomaga coraz bardziej z liczbą CZ”) wymaga **modelu z interakcją**: log ε ~ arm × log(n_CZ) + (1 \| punkt) + (1 \| szczebel).
- **Geometryczny iloraz z bootstrapem po parach** (`prereg_w01.py:ratio_ci`) jest OK. Przy 4 szczeblach trzeba jednak robić bootstrap **klastrowany po szczeblu** (lub po punkcie), bo pary w szczeblu dzielą kalibrację i blok czasowy.
- **OLS z efektami stałymi punktu i SE klastrowanymi po punkcie** (P5) przy **8 klastrach** daje zaniżone SE: sandwich CR1 przy G = 8 jest anty-konserwatywny. Należy użyć wild cluster bootstrap (Webb) albo CR2 z poprawką Bell–McCaffrey, ewentualnie raportować oba. Dla H7b (p ~ 1e-13) nic to nie zmieni, dla współczynników CZ po CDR (p = 0,002) już może.
- **McNemar** jest poprawny formalnie, ale przy 16–32 punktach i 1 zmianie bezużyteczny (C12).
- **κ** jest liczone z regresji na 5 budżetach i 10 powtórzeniach w jednym oknie. Niepewność ±1,1 nie zawiera wariancji między oknami. Rozrzut między oknami (12,5 vs 20,7) pokazuje, że prawdziwa niepewność jest znacznie większa.

### 5.2 Moc dla H1 (n = 32), oszacowana z obserwowanych efektów
Symulacja (20 000/4000 powtórzeń; dane nocy A ustalone, noc B losowana z obserwowanych różnic log-ilorazów). Próg po Holmie: H7b ma p ≈ 1e-13, więc H1 będzie najpewniej drugim najmniejszym p, a próg wynosi 0,05/4 = 0,0125.

| scenariusz dla nocy B (30, 57 CZ) | P(p < 0,05) | P(p < 0,0125) |
|---|---|---|
| jak circular (39 CZ): d̄ = −0,38, SD 0,63, d_z = −0,61 | 0,57 | 0,15 |
| jak średnia z nocy A (d̄ ≈ −0,02) | 0,07 | 0,008 |
| prospektywnie: 1 szczebel jak star + 3 jak circular | 0,54 | 0,32 |

Wymagana liczba par przy 80% mocy (Wilcoxon, ARE ≈ 0,955): d_z = 0,6 → ~17 par (α = 0,05) lub ~27 (α = 0,0125), **ale tylko na szczeblach, gdzie efekt istnieje**. Dla d_z = 0,3: 72 / 111 par. Wniosek: **H1 w obecnym projekcie ma niską moc i najpewniej nie zostanie potwierdzona**. Trzeba to zapowiedzieć przed analizą nocy B, żeby nie wyglądało na reakcję na wynik. Rozsądnie jest dopisać jako *zgłoszone odstępstwo / analizę eksploracyjną* model z interakcją arm × n_CZ i r² jako drugą miarę.

### 5.3 Co dodać (offline)
1. **Bootstrap CI** (klastrowany po punkcie i po szczeblu) dla każdej różnicy średnich błędów i ilorazu. Raportować CI zamiast samych p.
2. **Model mieszany** log ε ~ arm × n_CZ + (1 \| eval_point) + (1 \| rung), z CI z bootstrapu parametrycznego. Analogicznie dla r² i nachylenia a.
3. **Wielkości efektu**: iloraz geometryczny z CI, mediana różnicy, Hodges–Lehmann, d_z.
4. **Dekompozycja wariancji** estymatora CDR na szum shotów, szum ramek i niedopasowanie modelu. Ramki można odtworzyć z zapisanych M = 6 powtórzeń, a resampling ramek i shotów z `counts.jsonl` daje rozkład błędu przy tej samej konfiguracji. To wprost wyjaśnia C2.
5. **Krzywe błąd vs budżet przez podpróbkowanie zliczeń** (thinning histogramów; zliczenia per obwód są zapisane). CDR przy S' < S, M' < M, n' < n_train, a w szczególności przy budżecie ZNE (24 576 shotów/punkt, np. n_train = 20, M = 1, S ≈ 1170). To jedyny uczciwy sposób na porównanie ZNE vs CDR przy równym koszcie bez nowych nocy.
6. **Raportowanie wszystkich ramion** (5 ramion × 2 fity) w jednej tabeli z CI. Bez wybierania „CDR + twirl” jako zwycięzcy.
7. **Model tłumienia w P5**: log((E − f)/O_ideal) na \|O_ideal\| > 0,1, model liniowy na ε i model ze znakiem, plus trend czasowy (godzina bloku) i dummy kalibracji. Raportować wszystkie jako sensitivity.

---

## 6. Nowość i pozycjonowanie wobec literatury

- **ZNE / folding** (Temme i in. 2017; Giurgica-Tiron i in. 2020): metoda standardowa; nowością jest tylko wykonanie na obwodzie natywnym z kontrolami.
- **Degeneracja ZNE i garbage folding** (Köster & Mauerer, arXiv:2607.09360; **sprawdzone**: „Benchmarking Error Mitigation: Artefactual Improvements in Zero-Noise Extrapolation”, lipiec 2026, sprzęt IQM; wprowadzają garbage folding, test „zero-cost” i checklistę). **Tu nowości nie ma.** Jest replikacja na innym urządzeniu IQM, wariant garbage o identycznym szkielecie i liczbie PRX, obserwacja, że W_neg jest ślepe na degenerację, oraz negatywny wynik kontroli identity. To wartościowa *replikacja + doprecyzowanie*, i tak trzeba ją nazwać.
- **κ i alokacja Neymana** (Scavino Alfaro, arXiv:2605.08251; **sprawdzone**: „A finite-shot mean-squared-error boundary for Richardson zero-noise extrapolation”, v2 z 15.10.2026; teoria progu oraz IBM hardware, 75/101 instancji). Pomiar κ na ODRZE to **replikacja** z małym n; rozbieżność dla {1,3,5,7} jest ciekawa, ale słabo udokumentowana (C11).
- **CDR** (Czarnik i in. 2021) i warianty treningu (Czarnik i in. 2204.07109 — rozłożony rozkład treningowy, rząd wielkości mniej shotów; Lowe i in. vnCDR; Bultrini i in. UNITED; Zhang i in. CPDR 2412.09518). „Spread” (120 × 1 zamiast 20 × 6) jest bliski idei „widely-spread training distribution” Czarnika 2022. Nowość „spread” jest dyskusyjna i na sprzęcie nie działa (H6: p = 0,55; przy 39 CZ spread jest **gorszy**: 0,068 vs 0,040).
- **Twirling / randomized compiling** (Wallman & Emerson 2016; Hashim i in. 2021). **Twirling + CDR na sprzęcie** ma prace pokrewne (Sundar i in. 2025, arXiv:2507.09479: pseudotwirling + per-kubitowe współczynniki Clifforda; Farrell i in. 2023, ODR po twirlu). Nie zweryfikowałem pełnych tekstów pod kątem kontroli równego budżetu. Teza „pierwszy pomiar twirlu w CDR z kontrolą shot-matched” jest możliwa, ale ryzykowna; formułować jako „to our knowledge”.
- **Granice kosztu** (Takagi i in. 2022; Quek i in. 2024): tło teoretyczne, poprawnie cytowane.
- **EIV w CDR**: według własnego przeglądu autorki (`spec/notatki_nowosc_CDR_twirling.md` §1) nowe w kontekście QEM. Na danych różnice EIV–OLS są małe, a EIV jest niestabilne przy spread (39 CZ: 0,098 vs 0,068). Pomysł znany w statystyce, wkład techniczny mały.

**Co jest naprawdę nowe (i warte artykułu):**
1. Protokół porównania metod QEM na sprzęcie z **kontrolą równego budżetu** wewnątrz CDR, z kompletną proweniencją. To wkład metodologiczny i reprodukcyjny.
2. **Identity insertion z dopasowanym czasem (CZ·CZ vs delay)** jako sposób rozdzielenia czynników degradacji, z wynikiem „czas dominuje” na ODRZE. Nie znam pracy, która robi to w kontekście QEM (nie sprawdziłem wyczerpująco).
3. **Empiryczna dekompozycja tego, kiedy twirling pomaga CDR**: poprawa r² (liniowości) jest stabilna, ale przy małej głębokości przewagę zjada wariancja ramek. To ciekawa i obronna obserwacja mechanistyczna, *jeśli* zostanie pokazana dekompozycją wariancji (§5.3 pkt 4).
4. **Katalog pułapek** (dwie ścieżki kompilacji, niedeterministyczny router psujący szkielet CDR, wspólny zbiór treningowy, cichy clamp, identity folding niewidoczny w bazie Z, SNR względem zera). To realna wartość dla społeczności benchmarkującej QEM i dobry materiał na „lessons learned”.

---

## 7. Rekomendacje miejsc publikacji

| miejsce | szansa (moja ocena) | czego wymaga |
|---|---|---|
| **IEEE QCE 2027, short paper / poster / warsztat** (np. warsztat o benchmarkingu QEM) | 60–70% | Przeformułowana teza (protokół + pułapki + P5 + replikacja K&M), poprawione C1–C19, CI, uczciwy wynik H1. Wystarczą dane w01 + noc B. |
| **IEEE QCE 2027, full paper** (track Quantum Algorithms/Software lub Benchmarking) | 30–40% | Jak wyżej oraz: M1–M8 z §8 (zwłaszcza ZNE + REM offline, krzywe budżetowe z podpróbkowania, model z interakcją, dekompozycja wariancji, symulacja potwierdzająca mechanizmy). Recenzent QCE zaakceptuje 1 urządzenie, jeśli wkład to protokół i pułapki, a nie „ogólna mapa reżimów”. |
| **IEEE TQE** (rozszerzona wersja) | 20–30% | Pełna wersja z drugim urządzeniem lub drugim oknem; drugie okno daje wariancję między oknami. Bez tego recenzent TQE zarzuci brak uogólnienia. |
| **Quantum** | ~10% | Wymagałoby albo nowej teorii (np. analitycznego modelu „kiedy twirling pomaga CDR przy skończonym M” z walidacją), albo znacznie szerszych danych. Obecny wkład jest zbyt inkrementalny. |
| **PRX Quantum** | <5% | Poza zasięgiem: jedno 5-kubitowe urządzenie, 8 punktów na szczebel, brak wyniku głównego, replikacje znanych efektów. PRXQ oczekuje wyniku o szerokim znaczeniu. |
| alternatywnie: *Quantum Science and Technology*, *EPJ Quantum Technology*, *ACM TQC* (Transactions on Quantum Computing; metodologia benchmarków) | 30–45% | Pełna wersja „benchmarking protocol + pitfalls + ODRA case study”. Te pisma dobrze przyjmują rzetelne prace metodologiczne i reprodukcyjne. |

---

## 8. Co zrobić

### 8.1 Minimum, żeby było publikowalne (priorytet malejący)

| # | zadanie | koszt | QPU? |
|---|---|---|---|
| **M1** | Dokończyć noc B i uruchomić `analysis/prereg_w01.py` **bez zmian**. Wynik H1/H3/H6 zaraportować taki, jaki wyjdzie, z CI. Przed uruchomieniem dopisać do `preregistration.md` (jako zgłoszone odstępstwo, z datą) analizę mocy i model z interakcją arm × n_CZ jako *eksploracyjne*. | 0,5 dnia | noc B (już w planie) |
| **M2** | Poprawić tezy C1–C19 w decku, skrypcie i szkicu. Główna teza: „protokół i pułapki + replikacja K&M + P5”, a nie „mapa reżimów raw → ZNE → CDR”. | 1 dzień | nie |
| **M3** | **ZNE + REM offline**: macierze przypisań per kubit z `calibrations/odra_raw_w01*.json` (error_0_to_1 / error_1_to_0), tensorowa inwersja na zapisanych zliczeniach ZNE (oraz raw CDR dla spójności). Raportować ZNE z REM i bez. Usuwa C5. | 1 dzień | nie |
| **M4** | **Krzywe błąd vs budżet przez thinning zliczeń**: CDR przy budżecie ZNE i pośrednich, ZNE przy mniejszych budżetach. Daje uczciwe porównanie przy równym koszcie (W4) i „shots-to-target”. | 2–3 dni | nie |
| **M5** | Diagnostyki ZNE: SNR względem f; f jako średnia z wielu garbage lub z λ = 5 genuine przy głębokich szczeblach; floor tracking jako diagnostyka podstawowa (z cytatem K&M); jawny opis ślepoty W_neg. | 1 dzień | nie |
| **M6** | P5: sensitivity (model tłumienia, \|ideal\| > 0,1, model liniowy, trend czasowy, dummy kalibracji, wild cluster bootstrap). Przeformułować H7a na „nierozstrzygnięte”. Jawnie opisać pełne zakłócenie CZ vs idle porą nocy. | 1–2 dni | nie |
| **M7** | Dekompozycja wariancji CDR (shoty / ramki / model) przez resampling ramek i shotów; to wyjaśnienie wyniku przy 12 CZ. Δr² jako miara mechanistyczna (eksploracyjna). | 2 dni | nie |
| **M8** | Raport niedopasowania trening–cel: frakcja ideałów = 0, PRX i czas treningu vs celu, zakres ideałów treningu vs celu; omówić wpływ na błąd CDR. Raportować wszystkie ramiona, w tym fakt, że `shared_random` wygrywa przy 39 CZ. | 1 dzień | nie |
| **M9** | Zweryfikować spójność obwodów nocy A między commitami `4b0d849` (dirty) i `ecaa139`: odtworzyć plan na obu i porównać z `qasm3` w `counts.jsonl` (§9 B10). Bez tego recenzent zakwestionuje integralność nocy A. | 0,5–1 dnia | nie |
| **M10** | Symulacja z `sim/device_model.py` (kalibracja w01) odtwarzająca jakościowo: dryf identity do +1, offset ZNE z odczytu, poprawę r² przez twirling przy ZZ, rolę czasu w P5. Bez tej walidacji mechanizmy są tylko hipotezami. | 2–3 dni | nie |

Łącznie ~2–3 tygodnie pracy offline. Żadnych nowych nocy poza B.

### 8.2 „Nice to have”

| # | zadanie | koszt | QPU? |
|---|---|---|---|
| N1 | **Jedna noc P5 z przeplataniem** cz/idle/base na poziomie jobów (ABAB) i, jeśli to możliwe, w jednym zestawie kalibracji. To jedyna nowa noc, którą uważam za *naprawdę uzasadnioną*, i tylko jeśli teza „CZ vs czas” ma zostać w artykule jako wynik. Inaczej wystarczy przeformułowanie z M6. | 1 noc (~10 h) | tak |
| N2 | Prawdziwe near-Clifford CDR (k zachowanych bramek nie-Cliffordowych, ideał ze statevectora) w symulacji modelu urządzenia vs obecny w pełni Cliffordowy trening; ewentualnie mała noc na 39/57 CZ. | 2 dni sym. (+1 noc opcjonalnie) | opcjonalnie |
| N3 | Kontrola U(W†W)^k z losowym W o tym samym szkielecie, w miejsce identity: najpierw w symulacji, ewentualnie dopiąć do istniejącej nocy. | 1 dzień sym. | opcjonalnie |
| N4 | Drugie okno (np. na zestawie punktów 1) dla 12 i 39 CZ, co daje choć jedną wariancję między oknami. Wymagane, jeśli celem jest TQE. | 1–2 noce | tak |
| N5 | Per-kubitowe CDR (Z_i osobno; zero kosztu shotów) jako ablacja; odporne na ideały = 0 dla mean-Z. | 1 dzień | nie |
| N6 | Rozszerzyć κ: wspólny model z obu okien Neymana i z archiwum k7; omówić, dlaczego {1,3,5,7} wychodzi poniżej przewidywania. | 1 dzień | nie |
| N7 | Archiwum Garnet przeliczyć tylko tam, gdzie ścieżka była poprawna (twirl campaigns: stały layout); reszty nie używać ilościowo. | 1 dzień | nie |

---

## 9. Błędy i problemy w kodzie lub danych

| id | plik:linia | problem | wpływ |
|---|---|---|---|
| B1 | `qem/zne.py:331–333` (`snr`) | SNR = \|E(λmax)\|/SE względem zera, a nie względem podłogi f ≠ 0 (T1 + asymetria odczytu). Przy 39 CZ SNR ≈ 4 mierzy podłogę. | Kryterium H4(iv) w pre-rejestracji jest wadliwe; teza „SNR nie wykrył” to artefakt definicji. |
| B2 | `analysis/prereg_w01.py:74–77` vs `preregistration.md` tabela H7a/H7b | Kod liczy p **jednostronne** (p/2 w kierunku zarejestrowanym), plan mówi „Holm-adjusted **two-sided** p < 0.05”. Niezgodność w zamrożonym planie. | Dla wniosków bez znaczenia (H7b p ~ 1e-13, H7a i tak nieistotne), ale trzeba zgłosić jako odstępstwo i wybrać jedną wersję. |
| B3 | `campaign/odra_window.py:403–407` | Każdy rekord dostaje `calibration_set_id=cal0` (odczyt **przed** blokiem). Zmiana w trakcie bloku jest niewidoczna na poziomie rekordów: wszystkie rekordy `star_cz52` mają `b1b5…`, choć kalibracja zmieniła się w trakcie (05:50–06:50 UTC). | Sensitivity „po rekordzie” jest niemożliwa; trzeba odczytywać ID per job. |
| B4 | `campaign/odra_window.py:472–481` | `floor` = jedna wartość garbage λ = 5 w tym samym punkcie. Przy płytkich obwodach garbage nie jest na podłodze. | Floor tracking przy 12 CZ jest częściowo artefaktem wyboru f. |
| B5 | `campaign/odra_window.py:248–250` | Ziarno garbage zawiera `lam{s}`, więc V przy λ = 3 i λ = 5 są różne; docstring `qem/folding.py:116–117` mówi o „one V for all k blocks” (prawda tylko w obrębie jednego obwodu). | Nie błąd, ale trzeba to opisać w metodach; zwiększa wariancję garbage. |
| B6 | `qem/cdr_training.py:126–130` | Snapowane są **wszystkie** rotacje (pełny Clifford), a rotacje z θ = 0 są usuwane → trening ma ~50% PRX celu (star 10 vs 20; L13 27 vs 70) i krótszy czas. Szkic artykułu (§2.3) opisuje „random subset”. | Niedopasowanie szumu trening–cel; rozbieżność opis–kod. |
| B7 | `campaign/odra_window.py:206–209` | Ramiona `shared_random` używają legacy wspólnego zbioru treningowego, który DATA_NOTES §4 uznaje za wadliwy. | Pseudoreplikacja w H3; ramię „wadliwe” wygrywa przy 39 CZ (C3). |
| B8 | `qem/provenance.py:130, 328` (`estimate_duration_s`) | Pole `duration_s` w rekordach to suma szeregowa bramek, **ignoruje `delay`**: dla `star_idle*` daje 1,12 µs, tyle co baza. Regresja używa poprawnego `duration_sched_s`, ale pole w rekordzie jest mylące. | Ryzyko błędnego użycia w przyszłych analizach. |
| B9 | `campaign/odra_window.py:171–172, 345` | t_CZ = 60 ns, t_PRX = 20 ns zakodowane na sztywno w trybie `--submit` (nie z kalibracji). W tej kampanii zgadzają się z kalibracją (`gates.cz…duration = 6e-08`), ale IQM zaokrągla `delay` w górę (`run_hardware.py:103`), więc dopasowanie czasu idle jest przybliżone. | Drobne; zapisać w metodach, odczytywać z kalibracji. |
| B10 | `runs/odra_campaign/w01A/manifest.json` (`previous_attempts`) | Pierwsza próba nocy A (start 07:57 UTC; rekordy od 08:19) działała na commicie **`4b0d849`, `git_dirty: True`**, a wznowienie (19:31 UTC) na `ecaa139`. Między nimi wszedł commit P5 (`941bfab`), który zmienił `build_plan` (np. `duration_sched_s` brak w większości rekordów nocy A). Bloki poprzedniej próby nie mają zapisanego `blocks`. Wszystkie trzy okna mają `git_dirty: True` (2 pliki), bez listy plików. | Integralność nocy A wymaga weryfikacji (M9). Proweniencja „brudnego” drzewa powinna zapisywać diff. |
| B11 | `calibrations/odra_20261024_start.json` | `collected_at = 2026-10-23T16:13`, nie 24.10. Plik ma mylącą nazwę. | Drobne; poprawić nazwę lub dopisać notę. |
| B12 | `campaign/odra_window.py:92–93` vs `qem/arms.py:13–24` | Docstring obiecuje faktoryzm 2×2 × zbiór treningowy; domyślne ramiona pomijają `spread_off` i `off_copies:shared_random`. | Efekty dźwigni niezidentyfikowalne (W13). |
| B13 | deck slajd 26 / skrypt l. 812 | Kolumna „raw” z celów CDR obok ZNE z własnym raw λ = 1 (0,074 vs 0,069; 0,161 vs 0,158). | Niespójna tabela. |
| B14 | `qem/folding.py:80–105` (`identity_block`) | Konstrukcja identity daje szum niewidoczny w bazie Z (W8). | Kontrola nieważna; nie używać do wniosków (skrypt to już robi). |

Kontrole, które **przeszły**: budżet 1 032 192 shotów na punkt w każdym ramieniu; 0 niezgodności szkieletu CZ (near_target, twirl_native); liczby CZ drabiny 12/39 oraz P5 24/36/52 zgodne z manifestem; ZNE bez `fallback_used` i bez `unphysical` w w01A; tag `prereg-v1` wskazuje na `ecaa139`, a `analysis/prereg_w01.py` i `preregistration.md` nie zmieniły się po tagu (`git diff prereg-v1 HEAD`).

---

### Źródła sprawdzone w sieci
- Köster, Mauerer, *Benchmarking Error Mitigation: Artefactual Improvements in Zero-Noise Extrapolation*, [arXiv:2607.09360](https://arxiv.org/abs/2607.09360). Sprawdzony tylko abstrakt.
- Scavino Alfaro, *A finite-shot mean-squared-error boundary for Richardson zero-noise extrapolation*, [arXiv:2605.08251](https://arxiv.org/abs/2605.08251). Sprawdzony tylko abstrakt.
- Czarnik i in., *Improving the efficiency of learning-based error mitigation*, [arXiv:2204.07109](https://arxiv.org/html/2204.07109v2).
- Prace pokrewne z wyszukiwania: [Qermit volumetric benchmarking, arXiv:2204.09725](https://arxiv.org/pdf/2204.09725); [Sopena i in., arXiv:2103.12680](https://www.arxiv.org/abs/2103.12680) (CDR vs ZNE na sprzęcie, bez kontroli budżetu, wg snippetu).

Nie weryfikowałem pełnych tekstów Sundar i in. 2025, Farrell i in. 2023 ani Hashim i in. 2021 pod kątem kontroli shot-matched. Teza o pierwszeństwie wymaga tej weryfikacji.
