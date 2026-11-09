# Jak zaprezentować artykuł (ok. 15 minut)

Artykuł: `paper_draft/v3/main.pdf`. Prowadzisz słuchaczy przez PDF, rysunek po rysunku.

## Jedno zdanie na start
„Szum na procesorze kwantowym w pierwszym przybliżeniu ściska wynik ku zeru. Mitygacja działa
dokładnie tak długo, jak długo to ściśnięcie jest jedyną szkodą i da się je zmierzyć. Z tego jednego
obrazu wynika, gdzie zawodzi ZNE, jak długo opłaca się CDR i dlaczego dokładność klasyfikatora się
nie zmienia.”

## Trzy rzeczy, które słuchacz ma zapamiętać
1. **Szum to głównie ściśnięcie, i da się je przewidzieć z kalibracji.** Odwrócenie przewidzianej
   prostej, bez żadnych pomiarów treningowych, zmniejsza błąd ponad dwa razy.
2. **Każda metoda zawodzi z jasnego powodu:** ZNE, gdy obwody ze wzmocnionym szumem tracą sygnał;
   CDR, gdy pojawia się reszta związana z bramkami CZ; twirling tę resztę usuwa.
3. **Dla klasyfikatora mitygacja nie zmienia dokładności,** bo zmienia decyzje tylko przy granicy,
   gdzie klasyfikator i tak zgaduje.

---

## Przejście przez artykuł

### Strona 1: tytuł, abstrakt, wstęp (2 min)
- **Problem:** kubity łączą się tylko z sąsiadami, więc kompilator dokłada bramki CZ, które nic nie
  liczą. Ten sam klasyfikator kosztuje od 12 do 57 CZ.
- **Pytanie:** do ilu bramek mitygacja się opłaca i co daje klasyfikatorowi.
- **Luka (4 braki):** pomiar na sprzęcie przy równym koszcie i z kontrolą; wyjaśnienie, co psuje
  metody; testy zapisane przed analizą; ocena decyzji, a nie tylko ⟨O⟩.
- Pokaż listę 6 wkładów. Powiedz: „wszystko wynika z jednego modelu, zaraz go pokażę”.

### Setup (1 min)
- ODRA: 5 kubitów w gwiazdzie, każda bramka między kubitami zewnętrznymi idzie przez hub.
- Drabina 12 / 30 / 39 / 57 CZ. Każda metoda dostaje tyle samo pomiarów.
- **Kontrola garbage** dla ZNE: ten sam koszt i szum, ale obwody nie wiedzą nic o wyniku.
- Testy zapisane w gicie przed liczeniem błędów.

### Sekcja III: model (1 min)
- Napisz na tablicy albo pokaż równanie (1): zmierzony = s · idealny + c + r.
- s: ile wyniku przetrwało. c: przesunięcie od odczytu. r: wszystko inne.
- „Gdyby r = 0, mitygacja to po prostu podzielenie przez s. Każda metoda to inny sposób zgadnięcia s.”
- Uczciwie: to przybliżenie, a nie teoria; że szum przeskalowuje wynik, jest znane.

### Rys. 1: ściśnięcie (1,5 min)
- (a) 100 punktów na każdym szczeblu leży na prostej. s spada z 0,85 do 0,24.
- (b) s maleje głównie z **czasem trwania** obwodu: czas wyjaśnia 81% zmian.
- Jedyna hipoteza potwierdzona po poprawce: +1 µs przy tych samych bramkach daje 1,43 raza większy błąd.

### Rys. 2 i Tabela I: prosta z symulatora (2 min)
- „Skoro symulator z kalibracji przewiduje s, mitygujemy za darmo: liczymy prostą w symulacji i
  przykładamy do wyniku ze sprzętu.”
- Błąd mniejszy w 85 ze 112 przypadków, średnio 0,41 raza. Remis z CDR (1,15, nieistotne) przy 1/21
  kosztu.
- **Tabela I, ważna puenta:** uśrednienie kubitów nic nie psuje, ale wzór na liczbie bramek i
  czasie wypada dużo gorzej. Liczy się harmonogram obwodu, czyli kto kiedy czeka, a nie liczba bramek.
- Uczciwie: to analiza dodatkowa, wymyślona po obejrzeniu danych; trzeba ją powtórzyć w
  zaplanowanym eksperymencie.

### Rys. 3 i Tabela II: ZNE (2 min)
- (a) przy 12 CZ krzywe prawdziwego ZNE idą w stronę ideału, garbage nie. ZNE działa.
- (b) przy 39 CZ przy λ = 5 wszystkie punkty dają to samo. Obwód zapomniał, co liczył.
- Wtedy ZNE to tylko mnożenie wyniku przez 1,9, i garbage robi dokładnie to samo.
- **Predykcja z modelu bez dopasowania:** 0,67 i 0,75 wobec zmierzonych 0,70 i 0,76 przy 39 i 57 CZ.
- Powód liczbowy: przy 39 CZ sygnał przy λ = 5 to ok. 0,0005, a szum pomiaru 0,005.

### Rys. 4: CDR (1,5 min)
- (a) CDR bez twirlingu bije wynik bez mitygacji wszędzie, ale przewaga maleje i znika ok. 63 CZ
  (ekstrapolacja).
- (b) r² spada dużo szybciej: przy 57 CZ wynosi 0,35, a CDR wciąż jest 1,5 raza lepszy.
- Dlaczego (równanie 2): r² spada, gdy maleje s, nawet jeśli prosta jest dobra. Nie oceniajcie CDR
  progiem na r², tylko porównaniem z wynikiem bez mitygacji.

### Rys. 5 i Tabela III: co poza ściśnięciem (1,5 min)
- Ten sam obwód, dodane pary CZ albo czekanie tej samej długości.
- (a) Błąd bez mitygacji rośnie podobnie w obu przypadkach: to czas.
- (b) Po CDR czekanie prawie nie zostawia błędu, a pary CZ tak. Ta reszta rośnie z liczbą CZ.
- Symulator z kalibracji tej reszty nie widzi (zaniża błąd CDR 1,9 raza).

### Rys. 6: twirling (1 min)
- Z twirlingiem błąd CDR ≤ 0,053 aż do 57 CZ, r² wraca, symulator znów się zgadza.
- Test zapisany przed analizą nie przeszedł (20/32 par, p = 0,09): trend jest, za mało punktów i ramek.
- (b) Twirlowanie bramek z routingu nic nie daje, więc reszta to nie prosty błąd każdej bramki CZ.

### Sekcja F: wyniki negatywne (0,5 min)
- vnCDR: symulacja przewidywała połowę błędu, na sprzęcie bez poprawy.
- DD: nie pomogło, kierunek w stronę pogorszenia.

### Rys. 7: decyzje (1,5 min)
- (a) Szum zmienia decyzje tylko przy granicy (mediana marginesu 0,053 wobec 0,331).
- (b) Tam klasyfikator bez szumu ma rację tylko w 44% przypadków, czyli zgaduje.
- Wzór (3): zmiana dokładności = odsetek zmian × (2q − 1). Przy q ≈ 0,5 to prawie zero.
- W symulacji: CDR naprawia 132 decyzje, psuje 32, a dokładność bez zmian (0,735 → 0,727).
- Puenta dla QML: mitygacja ma sens, gdy liczy się wartość (prawdopodobieństwo, energia), a przy
  klasyfikacji lepiej poprawić margines.

### Sekcje V–VIII: dlaczego, dyskusja, ograniczenia (1 min)
- Pokaż sekcję V „Why the methods behave as they do”: każda metoda ma jedno zdanie wyjaśnienia.
- Reguła w 5 krokach z Dyskusji.
- Ograniczenia: jedno urządzenie, 8 punktów na szczebel, zmiana kalibracji w nocy, część analiz
  dodatkowa.

---

## Pytania, które mogą paść

| pytanie | odpowiedź |
|---|---|
| Czy model ściśnięcia jest nowy? | Sam pomysł przeskalowania nie. Nowe jest to, że jedna zmierzona liczba tłumaczy porażki trzech rzeczy i przewiduje wynik ZNE bez dopasowania. |
| Czy twirling działa? | Na średnich tak, wyraźnie. Test zapisany przed analizą nie przeszedł, bo 8 punktów i 6 ramek to za mało. Nie mówimy, że nie działa. |
| Czy reszta r to błąd ZZ? | Nie prosty: żaden stały kąt na każdej CZ nie odtwarza sprzętu. Kandydaci: wpływ bramki na czekających sąsiadów, ucieczka ze stanów 0/1, błędy w trójkach CZ tworzących SWAP. |
| Czemu prosta z symulatora nie jest głównym wynikiem? | Jest dodatkowa, wymyślona po obejrzeniu danych, i tańsza, ale nie lepsza od CDR. Służy jako dowód, że ściśnięcie jest przewidywalne. Następny krok to zaplanowany test. |
| 8 punktów to mało. | Tak, to główne ograniczenie. Dlatego mówimy o kierunkach i mechanizmach, a słabe wyniki nazywamy słabymi. Przegląd decyzji ma 1300 decyzji. |
| Czy to działa na innych procesorach? | Nie wiemy. Starsze pomiary na Garnecie i Emeraldzie pokazują ten sam kształt, ale przy innej liczbie bramek. To pierwszy punkt dalszych prac. |
| Co z DD? | W planie: „nie wykryto różnicy” (p = 0,065). Kierunek: pogorszenie, a r² CDR spada. |
| Kalibracja zmieniła się w nocy? | Tak, przy 30 i 57 CZ. Rejestrujemy to; analiza wrażliwości jest do zrobienia. Wnioski z eksperymentu wstawiania nie zmieniają się po usunięciu dotkniętych wariantów. |

## Czego nie mówić
- „Twirling nie działa” albo „twirling udowodniony”: oba są nieprawdą.
- „Mitygacja za darmo bije CDR”: jest remis przy dużo niższym koszcie.
- „Przyczyną jest błąd koherentny”: mówimy, że reszta jest związana z CZ i routingiem, a mechanizmu
  nie rozstrzygamy.
- „CDR zawodzi przy 63 CZ”: to ekstrapolacja poza zmierzony zakres.
