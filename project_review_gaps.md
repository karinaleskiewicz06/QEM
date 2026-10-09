# Przegląd projektu — „kwiatki" (niewykorzystane / half-done rzeczy merytoryczne)

**Cel:** analog `[[4,2,2]]`-diagnozy, ale dla całego projektu — rzeczy zaimplementowane-ale-nieużyte,
obiecane-ale-niedokończone, albo cicho podkopujące claimy. NIE dług inżynieryjny (ten jest w
`.planning/codebase/CONCERNS.md`). Data: 2026-08-26.

Legenda: ⭐ waga (wartość×pilność). „(free)" = da się zrobić bez kredytów.

> ⚠️ **DO SPRAWDZENIA PRZED WYSŁANIEM PRACY.** Ta lista musi zostać w całości
> zweryfikowana i domknięta zanim praca pójdzie do recenzji/publikacji. Ten sam
> note jest wpięty w `raport_month_2.tex`.

**Status realizacji (2026-08-26):**
- ✅ **#1 crossover — ZROBIONE.** `analyze_crossover.py` → `garnet_crossover_summary.csv`.
  Quality crossover ≈ **39 transpiled CZ** (ZNE taniej i lepiej poniżej; CDR lepiej powyżej,
  ~7× drożej). ZNE gain 3.17×→1.16×. Przy ~96 CZ żadna metoda nie dobija do ciasnego targetu
  (reżim kolapsu). **Statystyka (4 pkt, 1 okno; CZ57 anomalnie dobry) → utwardzić DRIFTEM
  (Faza 4).**
- ⏳ **Effective_shots — sprawdzone, FAŁSZYWY ALARM.** Podejrzenie rozjazdu 8396 vs 83968 było
  artefaktem obcięcia wyświetlania (`cut -c1-120`). `run_garnet_cdr.py:149` liczy
  `cdr_effective_shots(2048,40)=83968`, CSV ma 83968. Poprawnie. (Lekcja: surowy CSV czytać
  przez `csv.DictReader`, nie `column|cut`.)
- ✅ **#2 cross-topology koszt — ZROBIONE.** `analyze_routing_correlation.py`. Ten sam obwód:
  all_to_all ODRA 54 CZ/8 SWAP → Garnet 57/9 → **Emerald 72/14** (transpilacja, zero kredytów).
- ✅ **#3 korelacja SWAP↔degradacja — ZROBIONE.** Garnet (n=8, mierzony błąd): Spearman ρ
  err_raw vs CZ **+0.88** (p=0.004), vs depth +0.88, vs topo_dist +0.79 (p=0.02), vs SWAP +0.71
  (p=0.05). **ODRA (n=4): ρ = +1.00** vs CZ i SWAP. To domyka deliverable §8. → `routing_correlation_summary.csv`.
- ✅ **#5 ODRA częściowo wpięta** — korelacja ODRA dołożona wyżej (bonus). Zostaje: ODRA-ZNE +
  ODRA-mirror na wspólnej figurze method-comparison.
- ⏳ **Następne:** sim-scoping QEC+ZNE combo (§6 qec_logical_directions.md); potem #4 (drugi
  logiczny kubit), #6 banknote, #7 DD-na-kratach, #8 higiena placeholder-kalibracji.

---

## 🔴 1. Headline crossover NIE jest liczony, tylko rysowany ⭐⭐⭐ (free)
**To prawdopodobnie największy kwiatek.** Core Value projektu to: *„która metoda płaci do jakiego
budżetu 2q i która pęka pierwsza"*. Ale:
- `make_method_comparison.py` tylko **rysuje** krzywe (`axA.plot(...)`) — zero liczenia przecięcia.
- `shots_to_target.compare_methods` i `shots_to_target.shots_to_target_curve` (funkcje, które
  liczą crossover / interpolują „koszt do targetu") są **zdefiniowane, ale nigdzie nie wołane.**

**Skutek:** centralny wynik paperu jest teraz **oceniany na oko z wykresu**, nie policzony jako
punkt przecięcia + niepewność. To dokładnie ta metryka, którą recenzent zapyta „a gdzie liczba?".
**Fix (free):** wepnij `shots_to_target_curve`/`compare_methods` w analizę → policz per-metoda
próg CZ i crossover na istniejących CSV.

## 🔴 2. Emerald routing-koszt JUŻ policzony (za darmo), nieużyty ⭐⭐⭐ (free)
`routing_ladder_emerald{,_optimal,_adverse}.csv` istnieją — z **transpilacji**, bez sprzętu:
Emerald all_to_all = **72 CZ / 14 SWAP** vs Garnet 57 CZ / 9 SWAP vs ODRA. Czyli **oś kosztu
cross-topology dla wszystkich 3 topologii masz już za darmo.** Brakuje tylko strony *błędu*
(sprzęt). Reframe: część historii cross-topology (jak topologia napędza koszt routingu) jest
gotowa bez wydania kredytu.

## 🟠 3. Korelacja topo_dist ↔ SWAP ↔ degradacja — obiecana, niesyntezowana ⭐⭐ (free)
`methodology_month_2.md` §8 + „definition of done" wymieniają korelację topo-odległość↔SWAP↔spadek
jakości. Dane kosztowe są (`routing_ladder_*.csv`: logical_2q, transpiled_cz, swaps, depth),
dane błędu są (`garnet_full_results.csv`). Ale **nikt ich nie połączył w korelację/figurę.** To
domknięcie deliverable'u — czysta reanaliza.

## ❌ (WYCOFANE) „Tylko ZZZZ = pół kodu" — FAŁSZYWY kwiatek, skorygowane 2026-08-26
Pierwotnie podejrzewałam, że post-selekcja tylko na `ZZZZ` wyciska pół mocy kodu. **Test
statevector to obalił:** obserwabl badania jest Z-bazowy, a błędy Z (fazowe) nie psują obserwabla
Z-bazowego → `XXXX` byłby zmarnowaną acceptance. `ZZZZ`-only to KOMPLET dla tego badania.
Szczegóły w `qec_logical_directions.md §1b`. **Nie dodajemy XXXX.**

## 🟠 4. Drugi logiczny kubit `[[4,2,2]]` (`Z_LOGICAL2`) — martwy ⭐⭐
`Z_LOGICAL2 = (0,2)` jest **zdefiniowany i NIGDZIE nie użyty** (grep: tylko linia definicji). Czyli
„2" w `[[4,2,2]]` leży odłogiem — pełna redundancja z ideą #2d (prawdziwa logiczna bramka
2-kubitowa). Powiązane: `qec_logical_directions.md` §2d.

## 🟠 5. ODRA słabo wpięta w cross-method M2 ⭐⭐ (free, częściowo)
ODRA ma wyniki M1: ZNE (linear/richardson/exp) + REM + DD (`hardware_results.csv`, 8 wierszy) +
mirror (`two_curves_mirror_fidelity.csv`) + routing ladders. To jest **punkt gwiazdy** dla całej
historii cross-topology, ale M2-framing traktuje go jako legacy i nie kładzie na wspólnej osi
shots-to-target z Garnet. **Użytkownik wprost prosił: „pamiętaj o ODRze".** Fix (free): dołóż
ODRA-ZNE + ODRA-mirror do figury method-comparison i do korelacji z §3.

## 🟡 6. banknote_study — cała druga baza z realnym sprzętem, na ławce ⭐ (decyzja, nie przeoczenie)
`banknote_study/` ma ~10 CSV, w tym **hardware CV, ZNE, mirror** (prawdziwe wyniki sprzętowe).
Formalnie „out of scope" dla M2 (PROJECT.md). To niezależna kotwica generalizacji (druga
task/dane) z gotowymi danymi — tani wzmacniacz „task-agnostic", *jeśli* kiedyś zechcesz. Świadoma
decyzja, nie bug — ale warto pamiętać, że dane już są.

## 🟡 7. DD tylko na ODRze (M1), nigdy na kratach ⭐ (free sim)
DD był negatywem M1 na ODRze (gwiazda, krótkie idle). Na kratach łańcuchy SWAP dają **dużo dłuższy
idle** → DD mógłby zachować się inaczej. Nikt nie sprawdził na Garnet/Emerald. Tani sim-probe.
(Minor — M1 był świadomym negatywem.)

## 🟡 8. Placeholder-kalibracja krat może cicho wejść w claimy ilościowe ⭐ (higiena)
`synthesize_lattice_calibration` daje PLACEHOLDER (Spark-class) liczby dla Garnet/Emerald, gdy nie
podasz `--calibration`. To jawnie oznaczone, ale anti-pattern z `CLAUDE.md` ostrzega: łatwo
przypadkiem użyć placeholdera w liczbach do paperu. Higiena: pilnować, że każdy sim-vs-hardware
używa realnej kalibracji, nie placeholdera.

---

## Priorytet (moja rekomendacja)
1. **#1 (crossover liczony)** — largest, free, to jest Core Value. Zrób najpierw.
2. **#2 + #3 (Emerald-koszt + korelacja SWAP)** — free, domyka cross-topology i „definition of done".
3. **#5 (ODRA na wspólnej osi)** — free, użytkownik prosił.
4. Reszta (#4, #6, #7, #8) — opcjonalne / higiena / powiązane z gałęzią logiczną.

**Wniosek:** `[[4,2,2]]` nie był wyjątkiem — jest kilka miejsc, gdzie **dane/kod już są, a wynik
nie jest wyciągnięty**. Dobra wiadomość: prawie wszystkie fixy są **za darmo** (reanaliza), bo
kampania sprzętowa jest dalej, niż sugerują dokumenty.

---
*Przegląd: 2026-08-26. Towarzyszy `qec_logical_directions.md`.*
