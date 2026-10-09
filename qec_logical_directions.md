# Logical-ish arm — kierunki, pomysły i rozważania (scratchpad badawczy)

**Cel dokumentu:** utrwalić burzę mózgów wokół gałęzi `[[4,2,2]]` / „logical-ish", żeby nie
zniknęła. To notatnik roboczy, nie spec. Data: 2026-08-26.

---

## 0. Diagnoza stanu obecnego `[[4,2,2]]` (co realnie robi teraz)

Obecnie na sprzęcie (`run_garnet_qec.py`) leci **tylko Opcja C** — detection-wrapped mirror z
**losowym Cliffordem** jako payload:

```
encode |00>_L  →  random_clifford_payload(L)  →  payload†  →  measure(4 data)  →  post-select ZZZZ
```

Metryki: `err_bare→err_detected`, `survival` (bare→detected), `acceptance`. Placement optimal vs
adverse, layers 1–4.

**Trzy słabości (dlaczego to „wąskie", choć działa):**
1. **Nie dotyka klasyfikatora** — losowe Cliffordy, nie VQC.
2. **Pół kodu** — `postselect_z_parity` sprawdza tylko `ZZZZ` → łapie tylko błędy typu-X;
   stabilizator `XXXX` (błędy typu-Z) nietknięty.
3. **Redundancja z mirror-yardstick** — payload to `U†U = identyczność`, więc to prawie to samo
   co `garnet_mirror_results.csv` (survival), tylko z doklejoną post-selekcją. Nowego wnosi
   głównie: „a jak wyrzucimy złe shoty, to o tyle lepiej".

**Werdykt:** nie zepsute, ale niedowykorzystane i w dużej mierze powiela mirror. Nie zarabia na
miejsce jako osobna metoda — dopóki nie dodamy: Opcji A, obu baz, lub złożenia z ZNE.

---

## 1. Największe niewykorzystane rzeczy (już w kodzie / za darmo)

### 1a. Opcja A (surrogate) nigdy nie poszła na sprzęt ⭐⭐⭐
`qec422.py` ma `build_encoded_surrogate` (arm „task-facing" — łączy detekcję z dokładnością
klasyfikacji), ale `run_garnet_qec.py` odpala tylko Opcję C (mirror z losowym Cliffordem). Cała
triangulacja A+C z design-doca ma na sprzęcie tylko połowę. Uruchomienie A dałoby claim
„detekcja odzyskuje X% dokładności traconej przez routing" — bezpośredni kontrapunkt do negatywu
ZNE (który dokładności nie odzyskał). Brakujący, najciekawszy kawałek.

### 1b. „Tylko ZZZZ = pół kodu" — ❌ SKORYGOWANE (2026-08-26): to był FAŁSZYWY kwiatek
Pierwotnie: „`postselect_z_parity` sprawdza tylko `ZZZZ` → łapie tylko X-błędy → pół mocy".
**Weryfikacja statevector obaliła to:** obserwabl badania jest **Z-bazowy** (mean-Z, hub-Z,
logiczne Z̄1, survival=P(0000)+P(1111)). Test wstrzyknięcia błędów (błąd na kubicie obserwabla):
- **X-błąd** → PSUJE ⟨Z̄1⟩ (−1) i jest wykryty przez `ZZZZ` → `ZZZZ` działa.
- **Z-błąd** (fazowy) → NIE psuje ⟨Z̄1⟩ (pomiar w Z jest ślepy na fazy) → `XXXX` odrzucałby
  shoty za błąd, który i tak nie wpływa na wynik = czysty koszt acceptance, zero zysku.

**Wniosek: dla obserwabla Z-bazowego `ZZZZ`-only to KOMPLET, nie połowa.** `XXXX` sensowny tylko
gdyby obserwabl był X-bazowy albo chciano pełnej wierności stanu (obie bazy) — czego badanie nie
robi. **Decyzja: NIE dodajemy `XXXX`.** (Lekcja: claim sprawdzony sanity-checkiem obalił sam
siebie — dokładnie po to jest weryfikacja.)

### 1c. Acceptance to DARMOWY trzeci yardstick jakości urządzenia ⭐⭐
`acceptance ≈ (1−p)^waga` → bezpośrednio mierzy fizyczny error-rate na zrouterowanym bloku, per
placement. Masz to już w danych. Reframe: acceptance = druga task-agnostyczna miara wierności
(obok mirror survival). Cross-check: czy error-rate z acceptance zgadza się z mirror survival i z
nachyleniem ⟨O⟩-błędu na CZ? Trzy niezależne sondy się zgadzają = mocny argument. Czysta
reanaliza — zero kredytów.

## 2. Nowa fizyka do „pobawienia się"

### 2a. Pseudo-próg / crossover logical-vs-physical ⭐⭐⭐
Znajdź koszt CZ, przy którym `err_detected` przecina `err_bare`, per placement. Dane już to
obejmują (optimal L1: 0.42→0.22 wygrana → adverse L4: 0.98→0.97 nic). Sformułuj breakdown-frontier
JAKO pseudo-próg — spina język QEC z całym paperem. Głównie reanaliza.

### 2b. Detekcja + ZNE = czy metody się składają? ⭐⭐  ← WYBRANY KIERUNEK
Post-selekcja najpierw, potem ekstrapolacja na zaakceptowanych shotach. Czy near-term metody
komponują się, czy zmniejszona liczba shotów rozwala wariancję ZNE? Naprawdę nowe, publikowalne
pytanie („do they stack?"). Wymaga skromnego runu. Szczegóły w §5.

### 2c. Pareto acceptance↔błąd (miękka post-selekcja) ⭐⭐
Zamiast binarnie keep/discard — przemiataj surowość post-selekcji i narysuj front Pareto
koszt↔błąd. `[[4,2,2]]` daje pokrętło między tanie-brudne a drogie-czyste. Gdzie jest optimum
shots-to-target? Naturalny dom osi shots-to-target.

### 2d. Prawdziwa logiczna bramka 2-kubitowa ⭐
Realnie użyj transwersalnego logicznego CNOT₁₂ / H⊗H (to „2" w `[[4,2,2]]`) i zmierz wierność
prawdziwie logicznej operacji vs routing — bardziej „logical-ish" niż losowy mirror.

---

## 3. Opcja A — dwa warianty surrogate (i ich haczyk)

`[[4,2,2]]` trzyma **2 logiczne kubity**, a VQC ma **5** → nie da się wiernie zakodować dokładnego
5-kubitowego klasyfikatora. Stąd wybór surrogate:

- **Wariant „struktura-wierny" (rekomendacja):** 2-log-kubitowy ansatz o strukturze badania
  (L warstw: Clifford-rotacje + logiczny CNOT₁₂), kąty snapowane, budowany **wyłącznie z
  {Pauli, CNOT₁₂, H⊗H}** → prawdziwa operacja logiczna, ideal ⟨Z̄₁⟩ liczony dokładnie
  (stabilizator). Metryka: logiczny ⟨Z̄⟩-błąd vs CZ. „Dokładność" tylko zgrubna (kilka
  Clifford-preparowalnych wejść). Caveat: generyczny obwód o *kształcie* zadania, nie „ten"
  klasyfikator.
- **Wariant „snap prawdziwego VQC":** weź realny 5q VQC, znajdź jego 2-log-kubitowy rzut,
  zakoduj. Bliżej klasyfikatora, ale rzut 5→2 jest arbitralny i traci strukturę entanglera —
  podwójny „surrogate gap" (rzut + snap) do obrony.

**Głębsza prawda o „accuracy":** dokładność wymaga danych przez `RX(x)` (non-Clifford). Snapping
do π/2 **zabija zależność od danych** → z A dostajesz logiczny ⟨O⟩-błąd, nie pełną krzywą
accuracy. To ten sam kompromis co w całym projekcie (⟨O⟩-błąd główny, accuracy wtórna).

---

## 4. Dlaczego NIE pełny kod / magic states (fundamentalne)

VQC potrzebuje **non-Cliffordowych, zależnych od danych** rotacji `RY(x)`. Żaden kod nie zrobi
logicznej bramki non-Clifford za darmo — potrzeba magic-state injection / T-gadgetów. Na tym
sprzęcie to się **nie spina o rzędy wielkości**:

1. **Distylacja wymaga działającego QEC pod spodem.** Obwód distylacji to dziesiątki bramek 2q
   przy ~1% błędu — bez korekcji pod spodem wnosi więcej błędu niż usuwa. Zbiega dopiero poniżej
   progu; kody dystansu 2–3 przy ~1% są na/powyżej progu.
2. **T-injection wymaga fast feed-forward** (zmierz ancillę → warunkowa poprawka S → leć dalej).
   IQM tych urządzeń nie daje. Bez tego → post-selekcja gałęzi bez poprawki → koszt `0.5^(#T)`.
3. **Dowolny kąt to zabójca:** `RY(x)` = synteza Clifford+T długości O(log 1/ε) bramek T na
   rotację; data-reupload ma taką rotację na cechę×warstwę → setki/tysiące T.
4. **Budżet kubitów:** 15-do-1 = 15+ kubitów na stan magiczny × footprint kodu → dziesiątki
   tysięcy kubitów. Masz 20 (Garnet) / 54 (Emerald).

**Mini-wersja (gdyby chcieć dotknąć non-Clifforda uczciwie):** jedno wstrzyknięcie T bez
distylacji, z post-selekcją gałęzi bez poprawki (0.5 acceptance) — demonstracja pojedynczej
logicznej bramki non-Clifford pod routingiem. Nie uruchamia VQC, ale dotyka luki.

---

## 5. „Logical-ish bez pełnego kodowania" — dwa warianty (główny insight)

Kluczowe rozróżnienie: **non-Cliffordowe rotacje** zmuszają do magic states; **Cliffordowy
entangler + SWAP-y** (routing) to co jest drogie i psuje wynik. To dwie różne rzeczy. Więc:
uruchom prawdziwy fizyczny VQC (rotacje non-Clifford lecą normalnie), a błędy w routing-ciężkim
regionie łap **świadkiem** i post-selekcjonuj. „Logical-ish" siedzi w post-selekcji, nie w
enkodowaniu. (Nazwa w literaturze: **symmetry verification** — McArdle i in.; **flag qubits** —
Chao–Reichardt; **Pauli Check Sandwiching** — Gonzales i in. 2023.)

### Co znaczy „wykryj złe shoty i wyrzuć je"
Każdy shot = jeden bitstring. Znajdź wielkość o znanej idealnej wartości; policz ją w każdym
shocie; jeśli zła → w tym shocie zaszedł wykrywalny błąd → wyrzuć shot. ⟨O⟩ liczysz z przyjętych.
`acceptance` = ułamek przyjętych. Łapie tylko błędy zmieniające sprawdzaną wielkość (dystans 2).

### Wariant 1 — Pauli-check / symmetry verification (lekki, 1 ancilla)
Nie kodujesz nic. Dokładasz 1 kubit-świadka wokół Cliffordowego entanglera:
1. Ancilla w `|+⟩`.
2. Przed entanglerem: kontrolowana Pauli `P` na wybranych kubitach.
3. Za entanglerem: kontrolowana `Q = U_ent·P·U_ent†` (Pauli, bo `U_ent` Cliffordowy → liczysz
   klasycznie).
4. Pomiar ancilli w X. Idealnie → +1 deterministycznie. Błąd antykomutujący ze sprawdzeniem →
   ancilla −1 → flaga → shot do kosza.

Bilans: +1 kubit, kilka bramek 2q, kara acceptance. **Działa na PRAWDZIWYM VQC.** Najtańsza
„logical-ish na realnym modelu".

### Wariant 2 — `[[4,2,2]]` owija tylko Cliffordowy entangler (cięższy, mocniejszy)
Rotacje fizyczne, entangling ladder logicznie. Per warstwa:
`encode → logiczny entangler (transwersalny) → decode → RY(x)/RY(θ) fizyczne → …`, post-selekcja
parzystości na każdym decode. Chronisz dokładnie tę część, o której jest paper (routing = Clifford).
Mocniejsza detekcja, ale ×4 kubity + encode/decode co warstwę (sam dokłada routing → ryzyko
samobójczego narzutu na ~1% sprzęcie).

### Rekomendacja (do złożenia z ZNE)
**Do czystego eksperymentu „czy detekcja składa się z ZNE" — Wariant 1** (lekki, prawdziwy VQC,
acceptance nie załamuje się pod foldingiem, mało confoundów). Wariant 2 ryzykuje, że narzut
kodowania przekroczy korzyść i nie wiadomo, czy złożenie zawiodło przez fizykę czy przez własny
narzut. Opcja 2 ma sens, gdy celem jest „wiarygodność QEC", nie „czyste złożenie".

---

## 6. Detekcja + ZNE — pełny rozpis (wybrany kierunek, §2b)

**Pipeline (detect-then-extrapolate).** Dla każdej skali ZNE `s ∈ {1,3,5}`:
1. Zfolduj payload `U → U(U†U)^k` (`fold_global`).
2. Uruchom z detekcją/świadkiem.
3. Post-selekcja → przyjęte shoty + `acceptance(s)`.
4. Policz ⟨O⟩ na przyjętych → `⟨O⟩_det(s)`.
5. Ekstrapoluj `{(s, ⟨O⟩_det(s))}` do s→0 (Richardson).

**Pytania badawcze:**
1. Czy złożenie bije każdą z osobna? Post-selekcja zdejmuje błędy wykrywalne, ZNE resztę → jeśli
   komplementarne, `err(det+zne) < min(err_det, err_zne)`.
2. Czy kara za shoty to zabija? Przy s=3,5 folded ma więcej błędów → `acceptance(s)` spada →
   wariancja ZNE na przyjętym podzbiorze rośnie. Koszt = `shots × n_scales × 1/⟨acceptance⟩`.
3. Bias vs wariancja na osi routingu.

**Dlaczego publikowalne:** literatura prawie nie składa *detekcji* z *mitygacją*. Wynik czysty w
każdą stronę (składają się / walczą o te same błędy / kara shotowa wygrywa).

**Feasibility:** klocki istnieją (`fold_global`, `build_detection_mirror`/`build_encoded_surrogate`
+ `postselect_z_parity`, `extrapolate`). Prototyp w SIM 100% za darmo; potem 1 tani punkt na
sprzęcie. Na oś shots-to-target wchodzi przez mnożnik `n_scales/acceptance`.

---

## 7. Status decyzji / następny krok

**POSTĘP (2026-08-26):**
- ✅ **Kompozycja det+ZNE utwardzona (multi-seed):** na bloku `[[4,2,2]]`, p2q=0.01, det+ZNE bije
  ZNE w **10/10 seedach** (L1: zne 0.39→det+zne 0.11; L2: 0.67→0.42). Sygnał ≠ szum. Rozmiar
  zawyżony przez mirror (czysty target |00⟩_L). Skrypt: `scope_qec_zne.py`.
- ✅ **Wariant 1 (Pauli-check) zbudowany i ZWALIDOWANY na PRAWDZIWYM VQC** (`pcs_vqc_scope.py`):
  L=Z⊗⁵ (CZ-sandwich) wokół Cliffordowych entanglerów star. Prawdziwy statevector: P(anc=0)=1.0
  bez szumu → obwód poprawny. Z szumem (p2q=0.01): ⟨O⟩-błąd **raw 0.124 → check+PS 0.099** (~20%),
  acceptance ~0.62. **Uczciwa liczba na klasyfikatorze** (nie zawyżona jak mirror).
  - ⚠️ Lekcja: `DeviceCalibration(p_2q=0)` NIE jest bezszumowy (ma placeholder 1q/odczyt/T1T2) —
    do sanity używać czystego `Statevector`, nie „p2q=0".
- ❌ **det+ZNE na PRAWDZIWYM VQC — NEGATYW (sim closure, `scope_detzne_vqc.py`, 2026-08-26):**
  Na jedynym poprawnym wzorcu (star, sanity OK): raw 0.055 → **check 0.137 (SZKODZI)**, zne 0.031
  (najlepsze), check+zne 0.123. Narzut świadka (dodatkowe CZ + routing ancilli na gwieździe) >
  zysk z post-selekcji. Wcześniejsze pcs_vqc „0.124→0.099" mierzyło raw z już-obciążonej-ancillą
  wersji = nieuczciwy baseline. **Kompozycja NIE przenosi się z bloku [[4,2,2]] (gdzie mirror
  pochlebiał) na klasyfikator.** DODATKOWO: `L=Z⊗ⁿ` komutuje tylko z gwiazdą → dla linear/circular/
  all_to_all check jest NIEWAŻNY (sanity FAIL) — trzeba checka per-pattern. **Wniosek: NIE na
  Garneta jak jest — potwierdziłoby negatyw. Sim uratował kredyty.** Opcje: (a) przyjąć uczciwy
  negatyw; (b) lżejszy/per-pattern check + re-scope w sim; (c) hardware-target = to co DZIAŁAŁO
  (blok [[4,2,2]] mirror composition, ale to nie klasyfikator).
- ❌❌ **RE-SCOPE (lżejszy check, BEZ routingu) — NEGATYW POTWIERDZONY jako fundamentalny:**
  per-pattern check (Clifford R) + zero routingu, star (sane OK): raw 0.061 → **check 0.096
  (nadal SZKODZI)**, zne 0.043. Winny NIE routing, tylko **sam narzut bramek checka**: pełny check
  = ~6n≈30 zaszumionych CZ na ancilli vs ~12 CZ w VQC → potraja liczbę 2q → wnosi więcej szumu niż
  post-selekcja usuwa; korzyść post-selekcji dla ⟨mean-Z⟩ jest mała. Lżejszy check nie uratuje
  (korzyść bazowa ujemna). **DECYZJA: przyjmujemy negatyw dla ścieżki VQC.** Wynik z [[4,2,2]]-bloku
  (10/10) był pochlebiony czystym targetem mirror-a. Pozostała opcja hardware'owa dla POZYTYWNEJ
  kompozycji: det+ZNE na [[4,2,2]]-bloku (task-agnostic).
- 📌 **Osobny wątek do scopingu (free):** `[[5,1,3]]` d=3 (najmniejszy korygujący, NIE największy)
  — koszt routingu Garnet/Emerald + czy w symulacji jest pod/nad pseudo-progiem. Przewidywanie:
  nad progiem → korekcja nie płaci (czysty negatyw w tezie).

--- (poprzedni plan, zrealizowany) ---
- **Następny krok:** DARMOWY sim-scoping Wariantu 1 i 2 + ich złożenia z ZNE na hard-VQC
  (Garnet + Emerald placement): ile CZ/głębokości dokłada każdy, jak acceptance spada pod
  foldingiem, czy `det+zne` bije samo ZNE. Zero kredytów. Liczby rozstrzygają Wariant 1 vs 2.
- **Tanie reanalizy do zrobienia niezależnie:** §1c (acceptance jako sonda) + §2a (pseudo-próg)
  na istniejących CSV — zero kredytów, natychmiastowa wartość.

---
*Notatnik roboczy — nie commitowany automatycznie (klucz z hasłem). Data: 2026-08-26.*

---

## 8. Circuit Twirling (ODDZIELNY POZYTYW — kierunek na jutro, 2026-08-26)

Nowy wątek po negatywie QEC+ZNE-na-VQC. Twirling (randomized compiling) zamienia błędy
**koherentne** (systematyczna miskalibracja) w stochastyczne → przywraca założenia ZNE/CDR.
Sim-scope z wstrzykniętym koherentnym błędem `rz(coh)` po każdym CX (`coh` = rad/CX, knob).

**Wyniki sim (coh=0.15, p2q=0.005, star VQC, real classifier):**
- `twirl_zne_scope.py`: raw 0.091→twirl 0.062; ZNE 0.079→**twirl+ZNE 0.035** (~2.2× lepiej). SANITY OK.
- `twirl_cdr_scope.py`: **CDR untwirled 0.109 (GORSZY niż raw!) r²=0.81 → twirl+CDR 0.015 r²=0.99.**
  twirl+CDR to NAJLEPSZA kombinacja (bije twirl+ZNE ~2×). Twirling pomaga CDR BARDZIEJ niż ZNE.

**KLUCZOWE połączenie z danymi hardware:** `garnet_cdr` r² leci **0.99→0.69 przy 96 CZ** — to
sygnatura błędu koherentnego łamiącego dopasowanie CDR. Twirling = przewidywana naprawa. Więc to
NIE sztuczny sim — realny sygnał w danych Garneta.

**Przekaz do paperu:** „circuit twirling przywraca skuteczność ZNE i liniowość CDR pod koherentnym
szumem routingu — wyjaśnia i naprawia obserwowany kolaps r² przy wysokim koszcie 2q."

**Zastrzeżenia:** sim z wstrzykniętym coh (ale sygnatura r² obserwowalna w realu); twirl+CDR bardzo
drogie (N_twirl × n_train × shots); zysk skaluje się z frakcją koherentną Garneta (nieznaną → test).
Twirling nie ma jeszcze w kodzie — sprawdzić API `qiskit-iqm`/Resonance jak włączyć na sprzęcie.

**PLAN NA JUTRO (hardware, Garnet):**
1. Sprawdzić jak `qiskit-iqm`/Resonance eksponuje twirling (flaga w submit? ile instancji?).
2. Minimalny test: **twirl on/off × {ZNE, CDR}** na 1 punkcie wysokiego kosztu (adverse all_to_all,
   96 CZ). Metryki: ⟨O⟩-błąd + **CDR r²** (hipoteza: r² wraca z 0.69 w kierunku ~0.9).
3. Jak sim: twirl+CDR najlepszy, twirl+ZNE też pomaga → pozytyw na klasyfikatorze.
   Koszt: oszacować przed submitem (twirl mnoży shoty). Submit robi użytkownik (token+hasło).

Skrypty sim: `twirl_zne_scope.py`, `twirl_cdr_scope.py` (+ `scope_detzne_vqc.py` negatyw QEC-na-VQC).

---

## 9. Twirling na Garnet — REALIZACJA PLANU (2026-08-26, gotowe do submitu)

**Krok 1 — API:** IQM Resonance (iqm-client 34.0.3) **NIE ma twirlingu serwerowego** (tylko
`dd_mode`/`dd_strategy` = dynamical decoupling). Sprawdzone: `check_twirling_api.py` + grep dir()
w iqm.iqm_client / iqm.qiskit_iqm → puste. → **twirling CLIENT-SIDE.**

**Krok 2 — kod (gotowe, zwalidowane):**
- `iqm_resonance.run_circuits(..., compilation_options=None)` — teraz przyjmuje opcje (DD też tędy).
- `run_garnet_twirl.py` — client-side twirl on/off × {CDR, ZNE} na adverse all_to_all (~96 CZ).
  Twirl na **natywnym CZ po transpilacji**: `A` losowe, `B=CZ·A·CZ†` (frame='s'). **Zwalidowane:**
  noiseless twirled ⟨O⟩ == ideał (54 CZ, wiele instancji). `--dry-run` domyślnie (bezpieczny).
- Uśrednienie po M instancjach twirla; koszt = M× shotów.

**Krok 3 — submit (użytkownik, venv py3.11, token):** rekomendacja Config B ~45 cr:
`python run_garnet_twirl.py --submit --arms cdr zne --eval-points 3 --n-train 8 --n-twirl 5 --shots 1024`
Tańsze: CDR-only E3/nt8/M6 ~39 cr; najtaniej E2/nt6/M5 ~18 cr.
**Metryki:** err + cdr_r2, twirl on vs off. Hipoteza OK jeśli r²(twirl) > r²(notwirl) (~0.69→~0.9)
i err(twirl) < err(notwirl). Bonus knob dostępny: `dd_mode` (DD nigdy nie testowany na kratach, gap #7).

---

## 10. PILOT TWIRLING NA GARNECIE — WYNIKI (2026-08-26, real hardware)

Wariant lean CDR+ZNE (E3, shots1024, n_train10, M6, **twirl LOGICZNY**), 3 punkty CZ.
Bugi po drodze (naprawione): URL base, serializacja Pauli→natywne r, layout (twirl logiczny przez
transpile_for_backend), odczyt (perqubit_z_from_counts jak run_garnet). Tryb `--sim` dodany do
walidacji całego pipeline za darmo.

**CDR — HIPOTEZA POTWIERDZONA (r² restored, zysk rośnie z CZ):**
| CZ | r² OFF | r² ON | Δr² | err OFF→ON |
|----|--------|-------|-----|-----------|
| 12 (opt star) | 0.957 | 0.986 | +0.029 | 0.040→0.024 |
| 57 (opt a2a)  | 0.820 | 0.939 | **+0.119** | 0.051→0.026 |
| 96 (adv a2a)  | 0.837 | 0.909 | **+0.072** | 0.069→0.056 |
r² OFF spada z CZ (koherencja); twirl przywraca na każdym punkcie, mocno przy wysokim CZ; err
CDR spada wszędzie. **Realny, sprzętowy pozytyw twirl+CDR.**

**ZNE — MIESZANE (twirl pomaga @12, szkodzi @57/96):**
err OFF→ON: 12: 0.083→0.048 (lepiej); 57: 0.053→0.093 (gorzej); 96: 0.048→0.118 (gorzej).
Prawdopodobnie: twirl logiczny słabnie przy routingu + folding ZNE potraja głębokość (twirl-gate'y
foldowane) → więcej szumu; lub słaba statystyka. Do rozwiązania w §9b (natywny twirl + więcej stat).

**DECYZJA:** twirl+CDR wystarczająco mocny → iść w pełną §9b (natywny twirl, unitarity RB, drift,
15-30 eval pts, M=20, shots=8192). twirl+ZNE osobny wątek do rozstrzygnięcia. Dane: `garnet_twirl_results.csv`.

### 10a. Zagadka ZNE — rozwiązana (sim, 2026-08-26)
Hardware: twirl+ZNE pomaga @12 CZ, szkodzi @57/96. Sim (all_to_all VQC, coh=0.15, 3 eval-pts,
shots1024 = ustawienia pilota, 6 seedów): twirl+ZNE **robustnie POMAGA** 0.161→0.095, **6/6 seedów**
(std 0.005). Sim NIE odtwarza odwrócenia. Wniosek: różnica = **frakcja koherentna**. Sim ZNE-samo
słabe (0.16) bo duże wstrzyknięte coh; hardware ZNE-samo już dobre (0.048 @96CZ) → mniej koherencji
na Garnecie dla ZNE → narzut twirla przeważa. **CDR znacznie bardziej wrażliwe na koherencję niż
ZNE** (fit liniowy pęka przy małej koherencji; ekstrapolacja ZNE odporniejsza) → dlatego twirl
wygrał dla CDR a nie ZNE. NIE fundamentalna porażka — kompozycja działa (sim 6/6), opłaca się gdy
frakcja koherentna duża. **§9b unitarity RB zmierzy frakcję i ilościowo przewidzi kiedy twirl+ZNE
się opłaca** — to jest ten upgrade „przewidziane==zmierzone".

### 10b. §9b START — unitarity RB zbudowany (2026-08-26)
`run_garnet_urb.py` — 2-kubitowy URB na parze CZ (estymator: shifted purity p'=(Σ⟨σ_k⟩²)/(d−1)
po 15 traceless Pauli via 9 baz; fit A·u^(m−1)+B; Wallman 1503.07865 / forest-benchmarking).
Tryby: --sim (walidacja, z --coh model szumu koherentnego na cz), --submit, dry-run.
**ZWALIDOWANY:** PURE depol u=0.928 vs PURE koherentny u=0.9997 → poprawnie odróżnia koherencję.
Ważna lekcja: walidacja musi porównywać CZYSTO koherentny vs CZYSTO depol (nie sumę — unitarna
dodana do depol nie zmienia purity). Koherentny błąd w ramce lab (rz w obwodzie) jest twirlowany
przez losowe Clifordy → URB go nie widzi; musi być na bramce (noise model). Hardware: 
`python run_garnet_urb.py --submit --pair 3 0 --lengths 1 2 4 8 16 --k-seqs 10 --shots 1024` (~90-180 cr).
Wynik u → frakcja koherentna CZ Garneta → przewidywanie zysku twirla (predicted==measured).
Pozostałe §9b: natywny twirl (layout preservation, nie da się zwalidować bez backendu), pełna
drabina M=20/shots=8192, pasma driftu, M-sweep, DD ablacja.

### 10c. URB uzupełniony o RB + wynik wstępny (2026-08-26)
`run_garnet_urb.py` uzupełniony: teraz mierzy URB (unitarity u) ORAZ standardowy RB (decay p).
Werdykt koherencji = u vs p²: stochastyczny u≈p², koherentny u>p². ZWALIDOWANY w sim: depol
u=0.933/p=0.971/p²=0.943 (u−p²=−0.01, stochastyczny); koherentny u=1.0/p²=0.948 (u−p²=+0.05,
frakcja ~1). Hardware wstępnie (stary run, tylko URB): Garnet CZ (3,4) **u=0.9356** — niemal
identyczne z sim-depol u=0.933 → **prawdopodobnie CZ w większości STOCHASTYCZNA na poziomie
bramki**. Re-run z RB potrzebny dla p i werdyktu. WAŻNA SUBTELNOŚĆ: jeśli gate stochastyczny a
twirl+CDR pomógł → koherencja jest na poziomie OBWODU (routing/idle/crosstalk), nie bramki →
§9b potrzebuje CIRCUIT-level probe koherencji (twirl on/off na zrouterowanym mirrorze), nie tylko
gate-level URB. Komenda re-run: `python run_garnet_urb.py --submit --pair 3 4 --lengths 1 2 4 8 16 --k-seqs 10 --shots 1024` (~105 cr).

### 10d. URB+RB wynik hardware — KLUCZOWY: drift > sygnał koherentny (2026-08-26)
Garnet CZ (3-4), URB+RB: u=0.843, p=0.908, p²=0.824, **u−p²=+0.019** (nominalnie ~11% koherencji).
ALE dwa runy dały u=0.936 vs 0.843 → **drift 0.09 >> sygnał koherentny 0.019** → gate-level werdykt
NIEROZSTRZYGNIĘTY z pojedynczych pomiarów. Wnioski: (1) frakcja koherentna CZ MAŁA (~10%) i w
granicach niepewności driftu; (2) drift znaczący → potwierdza konieczność pasm driftu (BRKD-01);
(3) mała koherencja bramki pasuje do umiarkowanego zysku twirla z pilota (spójne); (4) zysk
twirl+CDR prawdopodobnie wzmacniany koherencją na poziomie OBWODU (routing/idle/crosstalk), nie
samej bramki. §9b doprecyzowane: URB×≥3 okna driftu (wiarygodne u z pasmami) + CIRCUIT-level probe
koherencji (twirl on/off na zrouterowanym mirrorze vs CZ) = właściwy predyktor dla twirl+CDR (H3).

### 10e. DECYZJA: twirling skupia się na CDR, NIE ZNE (2026-08-26)
NIE rezygnujemy z ZNE jako metody (zostaje na osi crossover ZNE/CDR). Rezygnujemy z KOMBINACJI
twirl+ZNE jako osobnego wyniku. Powody: (i) ekstrapolacja ZNE jest ODPORNA na koherencję (nie
opiera się na fit liniowym, w przeciwieństwie do CDR którego fit koherencja łamie — H4) → twirl
mało zyskuje; (ii) URB+RB: frakcja koherentna gate-level mała i drift-swamped (u−p²~0.02 vs drift
~0.09), a sim pokazuje zysk twirl+ZNE tylko przy DUŻEJ koherencji — czego Garnet nie ma; (iii) na
sprzęcie twirl+ZNE SZKODZIŁ przy wysokim CZ (narzut > zysk). Wniosek: twirling wnosi wartość tam
gdzie metoda WRAŻLIWA na koherencję (CDR), nie odporna (ZNE). §9b = twirl+CDR + drift + circuit-level
coherence probe; pomijamy gate-URB×drabina (drift zaciera sygnał). Zapisane też w raport_month_2.tex.

### 10f. Circuit-level coherence probe — NEGATYW (mirror kasuje koherencję, 2026-08-26)
Próba circuit-level probe (`scope_circuit_coherence.py`): twirl on/off na zrouterowanym mirrorze
U·U† vs CZ. **Nie działa:** gap twirla ~0/ujemny nawet przy coh=0.15, bo **mirror KASUJE błąd
koherentny** (U† odwraca U, systematyczna nad-rotacja w przód/tył się znosi — dlatego URB używa
losowych ciągów, nie mirrorów). Ta sama pułapka co „mirror flatters detection". WNIOSEK: czyste
zmierzenie circuit-level frakcji koherentnej jest trudne (gate-URB modest+drift; mirror kasuje;
pełny 5q-URB za drogi; właściwe narzędzie = CYCLE BENCHMARKING warstwy bramek+crosstalk = duży
build). H3 (predicted==measured) TRUDNIEJSZE niż zakładano. Solidny wynik = twirl+CDR (zmierzony)
+ gate-level koherencja (URB modest+drift); ilościowa predykcja circuit-level = przyszły kierunek
(cycle benchmarking). scope_circuit_coherence.py zostaje jako zapis (mirror-probe nie używać).
