# Garnet — Run Book kampanii sprzętowej (przed submitem)

Dokument kontrolny: **wszystko, co poleci na Garnet**, metodologia każdego kroku, i **każdy
hiperparametr z uzasadnieniem**. Cel: wydać kredyty świadomie i odtwarzalnie. Budżet:
**3700,50 kredytów**. Zmierzony koszt: **0,0005 kredytu/shot** (0,50 kr za 1000 shotów, smoke).

---

## 0. Kolejność (staged rollout) i budżet

Wszystkie skrypty **zbudowane, zaimportowane, device-generic** (`--device garnet|emerald`).

| Etap | Skrypt | Co waliduje | Koszt (Garnet) |
|---|---|---|---|
| 0. smoke ✅ | `run_garnet_smoke.py` | łączność, kolejność bitów, koszt | 0,50 kr (zrobione) |
| 1. go/no-go | `run_garnet.py --mode gonogo` | pipeline mapping+REM+ZNE, tanio | ~30 kr |
| 2. pełny ZNE ladder | `run_garnet.py --mode full` | drabina optimal-vs-adverse | ~740 kr/okno |
| 3. mirror fidelity | `run_garnet_mirror.py --device garnet` | metryka task-agnostic | ~16 kr |
| 4. CDR (oszczędny) | `run_garnet_cdr.py --device garnet --n-train 40` | 2. metoda QEM | ~225 kr |
| 5. `[[4,2,2]]` | `run_garnet_qec.py --device garnet` | warstwa logical-ish | ~33 kr |

**Budżet 2-urządzeniowy (oba × 3 metody):** Garnet (główne, pasma dryfu na brzegach) ~1748 kr
+ Emerald (walidacja, 1 okno, brzegowe wzorce, 0,00075 kr/shot) ~902 kr = **~2650 kr z 3700,50**,
bufor **~1050 kr**. Kalibracja: 0,0005 kr/shot (Garnet, zmierzone); Emerald ~1,5× (do potwierdzenia
na smoke). **Zasada:** nie idziemy do etapu N+1, dopóki etap N nie przejdzie kryteriów (§4).

---

## 1. Konwencje globalne i hiperparametry (z uzasadnieniem)

Wszystko dziedziczy z Miesiąca 1, chyba że zaznaczono. Każdy parametr jest albo
**statystyczny** (ustawiony precyzją vs koszt), albo **sprzętowy** (zmierzony), albo
**metodologiczny** (uzasadniony teorią).

| Parametr | Wartość | Rodzaj | Uzasadnienie |
|---|---|---|---|
| Urządzenie | Garnet (20 kubitów) | — | Tier B, krata; ODRA (star) była Tier A w M1 |
| Model | `two_curves` L=3, mean-Z, star | metod. | zablokowany w M1 (`LOCKED.json`) |
| Obserwabla | mean-Z $\frac1n\sum Z_q$ | metod. | permutacyjnie niezmiennicza → odporna na kolejność bitów po routingu |
| Metryka główna | $|\langle O\rangle - \langle O\rangle_{\text{ideal}}|$ | metod. | ciągła, czuła; ideał ze statevectora (zamrożony) |
| Metryki wtórne | accuracy, macro-F1 | metod. | na `two_curves` nasycone (~0,90) — patrz raport §3 |
| **shots (pełny)** | **4096** | statyst. | SE mean-Z $\approx 1/\sqrt{5N}\approx0{,}008 \ll$ efekty (0,05–0,4) |
| shots (smoke/go-no-go) | 1000 | statyst. | SE ~0,016 — wystarcza do walidacji; 4× taniej |
| **skale ZNE** | **{1, 3, 5}** | metod. | unitary folding $U(U^\dagger U)^k$, $k=0,1,2$ (Giurgica-Tiron) |
| ekstrapolacja | Richardson + fallback liniowy | metod. | dokładny wielomian przez 3 pkt; clamp $|EV|<1{,}25$ = detektor załamania |
| **punkty ewaluacyjne** | **15** (sprzęt) / 5 (go-no-go) | statyst.+koszt | 30 w symulatorze; na sprzęcie 15 (2× taniej), zbalansowane, seeded |
| **placement optimal** | **[3, 0, 2, 4, 8]** | sprzęt. | zwarty „plus" z ŻYWEJ mapy Garneta (hub 3, spokes dist 1) |
| **placement adverse** | **[0, 16, 12, 5, 18]** | sprzęt. | rozproszony (min-pair spread 15) z żywej mapy |
| wzorce (ladder) | star / linear / circular / all\_to\_all | metod. | drabina routingu; log. 2q 12/12/15/30 |
| **reps** | **1** (sprzęt, na start) | koszt | pasma błędu przez okna dryfu (W4), nie przez powtórki w jednym oknie |
| **REM** | **ON + ablacja on/off** | metod. | REM to klasyczny post-processing na tych samych countach → raw i +REM **za darmo** (0 dodatkowych shotów); readout-cal ściągane przez `pull_garnet.py` (metadane) |
| **DD** | **OFF** | metod. | wynik negatywny na Sparku (M1); nie stosujemy |
| **CDR n\_train** | **40** (sprzęt) / 200 (sym) | koszt | dopasowanie 2-param. stabilne przy 40; 200 by rozwaliło budżet (×5) |
| seed | 42 | metod. | trening + transpiler, odtwarzalność |
| batching | 1 zadanie / (placement, wzorzec) | koszt | amortyzuje ewentualne minimum per-zadanie |

**Kluczowe kompromisy sprzętowe vs symulator:** mniej punktów (15 vs 30), mniej reps (1 vs 5),
mniejsze n\_train CDR (40 vs 200) — wszystkie podyktowane budżetem; pasma błędu i dryf
zbieramy osobno przez powtórzenie drabiny w innym oknie kalibracyjnym.

---

## 2. Opis każdego kodu

### `run_garnet_smoke.py` — Etap 0 (zrobione) ✅
1 obwód (star, punkt 0), placement optimal, 1000 shotów. Weryfikuje łączność, kolejność bitów
(pomiar dodany PRZED transpilacją → bity w kolejności logicznej), i mierzy koszt. **Wynik:**
$\langle O\rangle=-0{,}708$ vs ideał $-0{,}801$ (błąd 0,093), 2q=12 (natywne, 0 SWAP), 0,50 kr.

### `run_garnet.py` — Etapy 1–2 (mapping ladder + ZNE)
Sedno kampanii. Dla każdego (placement, wzorzec):
- buduje obwód VQC per punkt ewaluacyjny, **składa (fold) na poziomie logicznym** przy skalach
  {1,3,5} (bariery chronią $U^\dagger U$ przed optymalizacją),
- dodaje pomiar (kolejność logiczna), transpiluje pod ŻYWY backend z `initial_layout` = placement,
- **batchuje wszystko w jedno zadanie**, wykonuje,
- liczy $\langle O\rangle$ z tych samych countów na dwa sposoby: **raw** (bez REM) i **+REM**
  (korekta klasyczna) → ekstrapolacja Richardsona na wartościach z REM → **+ZNE**,
- raportuje ablację **raw → +REM → +ZNE**, accuracy, macro-F1 vs zamrożony ideał; zapis CSV.
  Ablacja REM on/off jest **darmowa** (ten sam pomiar).

`--mode gonogo`: 2 wzorce × 2 placementy × 5 pkt × 3 skale × 1000 shotów = **60 tys. shotów ≈ 30 kr**.
`--mode full`: 4 × 2 × 15 × 3 × 4096 = **1,47 mln shotów ≈ 737 kr**.

**Co mierzymy:** czy błąd $\langle O\rangle$ rośnie z transpilowanym CZ (drabina), o ile placement
adverse podbija koszt vs optimal, i gdzie ZNE przestaje pomagać — teraz na realnym Garnecie.

### `run_garnet_mirror.py` — Etap 3 (do zbudowania)
Mirror fidelity $P(|0\rangle^5)$ (task-agnostic) per wzorzec × placement. 8 obwodów × 4096. ~16 kr.

### CDR na Garnecie — Etap 4
`run_cdr.py` przez adapter Resonance, `--n-train 40`, 2 wzorce × 2 placementy, 15 pkt, 2048 shotów.
~225 kr. Porównanie ZNE-vs-CDR na sprzęcie + na osi shots-to-target.

### `[[4,2,2]]` na Garnecie — Etap 5
Blok 4-kubitowy (Option C mirror), 4 warstwy × 2 placementy, 8192 shotów. ~33 kr. Logiczny
$\langle O\rangle$-błąd + fidelity + akceptacja (bez/z detekcją).

---

## 3. Kryteria bramek (go/no-go)

Po **Etapie 1** sprawdzamy, zanim wydamy ~740 kr na Etap 2:
1. **Poprawność:** dla taniego star, $\langle O\rangle$ mierzone blisko ideału (błąd $\lesssim 0{,}15$)
   — potwierdza pipeline (smoke już to pokazał: 0,093).
2. **Drabina:** błąd raw rośnie z transpilowanym CZ (star < all\_to\_all).
3. **Placement:** adverse ma wyższy transpilowany CZ i wyższy błąd niż optimal przy tym samym wzorcu.
4. **ZNE:** przy tanim koszcie ZNE obniża błąd (err\_zne < err\_raw); przy drogim może zanikać.
5. **Koszt:** realny koszt Etapu 1 zgodny z ~30 kr (drugi punkt kalibracji — potwierdza brak
   ukrytego minimum per-zadanie). Jeśli koszt istotnie wyższy → przeliczamy budżet przed Etapem 2.

Jeśli którekolwiek zawodzi → diagnoza, nie wydajemy na pełną kampanię.

---

## 4. Czego NIE robimy (i dlaczego)

- **Emeralda nie symulujemy** ($2^{54}$) — cross-topology tylko ze sprzętu.
- **Reps > 1 na start** — pasma błędu z okien dryfu (taniej i naukowo właściwsze niż powtórki w
  jednym oknie).
- (REM jest ON + ablacja on/off — darmowa, patrz §1.)
- **DD off** — udokumentowany wynik negatywny (M1).
- **CDR n\_train 200 na sprzęcie** — za drogie; 40 wystarcza dla 2-param. dopasowania.

---

## 5. Ślad odtwarzalności

Każdy wynik → skrypt → CSV:
`run_garnet.py --mode full` → `garnet_full_results.csv` (device, placement, pattern,
transpiled\_cz, err\_raw, err\_zne, acc/F1, n\_points, shots). Placementy zablokowane w
`topology.HARDWARE_PLACEMENTS` (z żywej mapy, `calibrations/garnet.json`). Adapter:
`iqm_resonance.py` (base URL + `quantum_computer` + token z env). Model: `LOCKED.json`.
