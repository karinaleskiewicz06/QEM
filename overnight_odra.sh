#!/bin/bash
# Nocna kampania ODRA -- CALOSC w jednym przebiegu, po kolei. ODRA nie jest rozliczana kredytami
# Resonance, wiec jedynym ograniczeniem jest CZAS (~5,9 min na zgloszenie, 100 obwodow/zgloszenie).
#
# HARMONOGRAM (kolejnosc nieprzypadkowa):
#   A. trening osi glebokosci -- CZYSTO KLASYCZNY, startuje OD RAZU i liczy sie rownolegle do
#      pierwszej kampanii QPU, ktora i tak przez wiekszosc czasu czeka w kolejce;
#   1. kampania twirlingowa (logiczna)  ~3,1 h  -- n z 9 do 20+, plus retencja sygnalu ze sprzetu;
#   2. os glebokosci L=6,9,13           ~0,6 h  -- najwyzsza wartosc naukowa na minute QPU;
#                                                  stoi po kroku 1, zeby trening zdazyl sie skonczyc;
#   3. kappa dla {1,3,5,7}              ~3,5 h;
#   4. twirling natywny                 ~3,1 h  -- najdluzszy, wiec na koniec: jesli noc sie urwie,
#                                                  tracimy najmniej.
#   RAZEM ~10,3 h pracy QPU.
#
# ODPORNOSC: kroki sa niezalezne -- blad jednego nie przerywa reszty. Kampanie twirlingowe i kappa
# ida z --resume, wiec czesciowy plik jest DOKANCZANY, a nie liczony od nowa. Skrypt mozna
# bezpiecznie uruchomic ponownie po awarii.
#
# NOC 1 (wszystko):
#   caffeinate -is ./overnight_odra.sh
#
# NOC 2 (drugie okno dryfu -- tylko kampanie twirlingowe, ~6,2 h; glebokosc i kappa sa juz zrobione):
#   WINDOW=o2 SKIP="depth kappa" caffeinate -is ./overnight_odra.sh
#
# Skracanie nocy (spacja-rozdzielone etykiety): SKIP="native kappa" caffeinate -is ./overnight_odra.sh
# Podglad w trakcie:  tail -f overnight_odra_<okno>.log

cd /Users/karinaleskiewicz/QEM || exit 1
export KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1
WINDOW="${WINDOW:-o1}"          # etykieta okna kalibracyjnego (noc 1 = o1, noc 2 = o2, ...)
LOG="overnight_odra_${WINDOW}.log"
SKIP="${SKIP:-}"

say() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
skipped() { case " $SKIP " in *" $1 "*) return 0;; *) return 1;; esac; }

: > "$LOG"
say "=== NOCNA KAMPANIA ODRA -- okno ${WINDOW} -- start $(date) ==="
[ -n "$SKIP" ] && say "pomijam na zadanie: $SKIP"

# --------------------------------------------------------------------------- #
# Kontrola wstepna: lepiej pasc TERAZ niz o 3 nad ranem na braku tokenu        #
# --------------------------------------------------------------------------- #
# Wybor interpretera. Venv ma iqm-client, ale nie ma qiskit_machine_learning; anaconda ma komplet.
# Zamiast wymagac, zeby uzytkowniczka pamietala, z ktorego terminala odpalic -- skrypt sam znajduje
# pierwszego Pythona, ktory ma WSZYSTKIE 7 modulow. PY_BIN=... nadpisuje wybor recznie.
pick_python() {
  local cand c
  for c in "$PY_BIN" python python3 /opt/homebrew/anaconda3/bin/python3 /usr/bin/python3; do
    [ -z "$c" ] && continue
    command -v "$c" >/dev/null 2>&1 || continue
    if "$c" - <<'PYCHK' >/dev/null 2>&1
import importlib
for m in ("iqm.iqm_client","qiskit","qiskit_aer","torch",
          "qiskit_machine_learning","qml_benchmarks","sklearn"):
    importlib.import_module(m)
PYCHK
    then cand="$c"; break; fi
  done
  echo "$cand"
}
PY_BIN="$(pick_python)"
if [ -z "$PY_BIN" ]; then
  say "BLAD: zaden interpreter nie ma kompletu 7 modulow."
  say "  sprawdzone: python, python3, /opt/homebrew/anaconda3/bin/python3, /usr/bin/python3"
  say "  wskaz recznie:  PY_BIN=/sciezka/do/python WINDOW=$WINDOW ./overnight_odra.sh"
  exit 1
fi
say "interpreter: $PY_BIN"

fail=0
[ -z "$IQM_SERVER_URL" ] && { say "BLAD: brak IQM_SERVER_URL (np. https://odra5.e-science.pl/)"; fail=1; }
[ -z "$IQM_TOKEN" ]      && { say "BLAD: brak IQM_TOKEN"; fail=1; }
# UWAGA: sprawdzamy KOMPLET modulow, lacznie z tymi, ktorych potrzebuje tylko trening osi
# glebokosci. W oknie o1 skrypt ruszyl z venva bez qiskit_machine_learning -- kontrola tego nie
# wylapala, bo sprawdzala tylko cztery moduly, i cala os glebokosci przepadla po cichu.
"$PY_BIN" - <<'PY' >> "$LOG" 2>&1 || fail=1
import importlib, sys
brak = []
for m in ("iqm.iqm_client", "qiskit", "qiskit_aer", "torch",
          "qiskit_machine_learning", "qml_benchmarks", "sklearn"):
    try:
        importlib.import_module(m)
    except Exception as e:
        brak.append(f"{m} ({type(e).__name__})")
print("interpreter:", sys.executable)
if brak:
    print("BRAKUJACE MODULY:", ", ".join(brak))
    sys.exit(1)
print("importy OK -- komplet 7 modulow")
PY
[ "$fail" = 1 ] && { say "PRZERWANO przed startem -- napraw powyzsze i uruchom ponownie."
                     say "  (jesli brakuje qiskit_machine_learning: uruchom z interpretera anaconda,"
                     say "   ktory ma komplet -- /opt/homebrew/anaconda3/bin/python3)"; exit 1; }
say "kontrola wstepna OK (zmienne srodowiskowe + importy)"

# Gdyby gdzies jeszcze chodzil recznie odpalony submit -- poczekaj, dwa rownoczesne zgloszenia
# do ODRY tylko by sie przeplotly i spowolnily nawzajem.
waited=0
while pgrep -f "run_garnet_twirl.py.*--submit|run_odra_cdr.py.*--submit|zne_shot_boundary.py.*--submit" >/dev/null 2>&1; do
  [ "$waited" = 0 ] && say "wykryto inny submit na ODRE -- czekam, az sie skonczy (sprawdzam co 2 min)"
  waited=$((waited+1)); sleep 120
done
[ "$waited" -gt 0 ] && say "QPU zwolnione po ~$((waited*2)) min"

done_already() { [ -s "$1" ] && [ "$(wc -l < "$1")" -ge 2 ]; }

# step  <etykieta> <plik> <skip-jesli-istnieje: yes|no> <komenda...>
step() {
  local label=$1 out=$2 guard=$3; shift 3
  if skipped "$label"; then say "POMIJAM $label (SKIP)"; return 0; fi
  if [ "$guard" = yes ] && done_already "$out"; then
    say "POMIJAM $label -- $out juz kompletny"; return 0
  fi
  say ">>> START $label  -> $out"
  local t0=$SECONDS
  if "$@" >> "$LOG" 2>&1; then
    say "<<< OK    $label  ($(( (SECONDS-t0)/60 )) min)"
  else
    say "<<< BLAD  $label  ($(( (SECONDS-t0)/60 )) min) -- ide dalej, szczegoly w $LOG"
  fi
}

TW_PTS="optimal:star optimal:linear optimal:circular optimal:all_to_all"

# --------------------------------------------------------------------------- #
# A. trening osi glebokosci (CPU, rownolegle do kroku 1 na QPU)                #
# --------------------------------------------------------------------------- #
MODELS=trained_models_hard
if skipped depth; then
  say "POMIJAM trening osi glebokosci (SKIP depth)"
elif [ -f "$MODELS/two_curves_d8_q5_deg8_star_mean_L13_weights.npy" ]; then
  say "POMIJAM trening osi glebokosci -- wagi L=6/9/13 juz sa"
else
  say ">>> START trening osi glebokosci (CPU, w tle kroku 1)"
  "$PY_BIN" train_star_depth.py --layers 6 9 13 >> "$LOG" 2>&1 &
  TRAIN_PID=$!
  say "    trening w tle, PID $TRAIN_PID"
fi

# --------------------------------------------------------------------------- #
# 1. kampania twirlingowa, twirl LOGICZNY  (~3,1 h)                            #
# --------------------------------------------------------------------------- #
# --resume: czesciowy odra_twirl_o1.csv jest DOKANCZANY, nie liczony od nowa.
# Ramie ZNE loguje przy okazji retention_R -> retencja sygnalu zmierzona na SPRZECIE.
step twirl "odra_twirl_${WINDOW}.csv" no \
  "$PY_BIN" run_garnet_twirl.py --submit --device odra --resume \
    --arms raw cdr zne --twirl-arms cdr --points $TW_PTS \
    --eval-points 4 --shots 8192 --n-train 10 --n-twirl 6 \
    --window-id "$WINDOW" --out "odra_twirl_${WINDOW}.csv"

# --------------------------------------------------------------------------- #
# 2. os glebokosci: ten sam CZ, ZERO routingu  (~12 min na przebieg)           #
# --------------------------------------------------------------------------- #
# Ramie Z ROUTINGIEM jest juz zmierzone (odra_full_100pt.csv: r2 = 0,809 / 0,792 / 0,598
# przy 27 / 36 / 54 CZ). Te przebiegi dostarczaja ramienia BEZ routingu przy 24 / 36 / 52 CZ.
if [ -n "$TRAIN_PID" ]; then
  say "czekam na koniec treningu (PID $TRAIN_PID) przed osia glebokosci..."
  wait "$TRAIN_PID" && say "trening zakonczony OK" || say "trening BLAD -- os glebokosci zostanie pominieta"
fi
for L in 6 9 13; do
  step depth "odra_depth_L${L}.csv" yes \
    "$PY_BIN" run_odra_cdr.py --submit --patterns star --layers "$L" \
      --eval-points 100 --n-train 100 --shots 8192 --out "odra_depth_L${L}.csv"
done

# --------------------------------------------------------------------------- #
# 3. kappa, trzeci zbior wezlow {1,3,5,7}  (~3,5 h)                            #
# --------------------------------------------------------------------------- #
# Siatka rozszerzona w gore, bo kappa=44,56 przesuwa prog do S* ~ 2772; domyslna siatka
# (do 4096) postawilaby przejscie na samym brzegu -- ten sam blad, co przy kappa=4.
step kappa odra_kappa_k7.csv no \
  "$PY_BIN" zne_shot_boundary.py --submit --device odra --resume --scales 1 3 5 7 \
    --points optimal:star optimal:all_to_all \
    --budgets 256 512 1024 1536 2048 3072 4096 6144 8192 \
    --out odra_kappa_k7.csv

# --------------------------------------------------------------------------- #
# 4. twirling NATYWNY -- obejmuje CZ pochodzace ze SWAP-ow  (~3,1 h)           #
# --------------------------------------------------------------------------- #
step native "odra_twirl_native_${WINDOW}.csv" no \
  "$PY_BIN" run_garnet_twirl.py --submit --device odra --native-twirl --resume \
    --arms cdr --twirl-arms cdr --points $TW_PTS \
    --eval-points 4 --shots 8192 --n-train 10 --n-twirl 6 \
    --window-id "${WINDOW}n" --out "odra_twirl_native_${WINDOW}.csv"

# --------------------------------------------------------------------------- #
# Podsumowanie                                                                 #
# --------------------------------------------------------------------------- #
say ""
say "=== PODSUMOWANIE ==="
for f in "odra_twirl_${WINDOW}.csv" odra_depth_L6.csv odra_depth_L9.csv odra_depth_L13.csv \
         odra_kappa_k7.csv "odra_twirl_native_${WINDOW}.csv"; do
  if done_already "$f"; then say "  OK    $f ($(( $(wc -l < "$f") - 1 )) wierszy)"
  else say "  BRAK  $f"; fi
done

# Pasma dryfu: jesli sa >=2 okna, policz sparowane Delta z odchyleniem miedzyokiennym.
nwin=$(ls odra_twirl_o*.csv 2>/dev/null | grep -v native | grep -v banded | wc -l | tr -d " ")
if [ "$nwin" -ge 2 ]; then
  say "agreguje $nwin okien dryfu -> odra_twirl_banded.csv"
  "$PY_BIN" aggregate_twirl_windows.py $(ls odra_twirl_o*.csv | grep -v native | grep -v banded) \
    --out odra_twirl_banded.csv >> "$LOG" 2>&1 \
    && say "  OK -- pasma dryfu policzone" || say "  BLAD agregacji, szczegoly w $LOG"
else
  say "tylko $nwin okno dryfu -- pasma policze sie po drugiej nocy (WINDOW=o2)"
fi

say ""
say "Zysk z twirlingu: LOGICZNY vs NATYWNY (natywny obejmuje tez SWAP-y)"
"$PY_BIN" - <<'PY' 2>&1 | tee -a "$LOG"
import csv, os
from collections import defaultdict
def delta(path):
    if not os.path.exists(path): return {}
    d = defaultdict(dict)
    for r in csv.DictReader(open(path)):
        if r.get("arm") == "cdr" and r.get("cdr_r2"):
            d[int(r["transpiled_cz"])][str(r["twirl"]).lower() == "true"] = float(r["cdr_r2"])
    return {cz: v[True] - v[False] for cz, v in d.items() if True in v and False in v}
import glob
def delta_all(pat, exclude=None):
    """Sredni Delta r^2 po wszystkich oknach pasujacych do wzorca."""
    acc = defaultdict(list)
    for f in sorted(glob.glob(pat)):
        if exclude and exclude in f: continue
        if "banded" in f: continue
        for cz, d in delta(f).items(): acc[cz].append(d)
    return {cz: sum(v)/len(v) for cz, v in acc.items()}, {cz: len(v) for cz, v in acc.items()}
lo, nlo = delta_all("odra_twirl_o*.csv", exclude="native")
na, nna = delta_all("odra_twirl_native_o*.csv")
if lo or na:
    print(f"  (usrednione po oknach: logiczny {nlo}, natywny {nna})")
    print(f"  {'CZ':>4}  {'d_r2 logiczny':>14}  {'d_r2 natywny':>14}  przyrost")
    for cz in sorted(set(lo) | set(na)):
        a, b = lo.get(cz), na.get(cz)
        f = lambda x: f"{x:+.4f}" if x is not None else "   brak"
        g = f"{b-a:+.4f}" if (a is not None and b is not None) else ""
        print(f"  {cz:>4}  {f(a):>14}  {f(b):>14}  {g}")
    print("\n  Dodatni przyrost = owijanie SWAP-ow faktycznie dokłada zysku")
    print("  -> obecny wynik w raporcie jest dolnym ograniczeniem, i wiemy juz o ile.")
else:
    print("  (brak danych twirlingowych)")

print("\nOs glebokosci: r2 BEZ routingu wobec r2 Z routingiem (ten sam koszt CZ)")
routing = {}
if os.path.exists("odra_full_100pt.csv"):
    for r in csv.DictReader(open("odra_full_100pt.csv")):
        routing[int(r["transpiled_cz"])] = float(r["cdr_r2"])
any_depth = False
print(f"  {'CZ':>4}  {'bez routingu':>13}  {'z routingiem':>13}  roznica")
for L in (6, 9, 13):
    f = f"odra_depth_L{L}.csv"
    if not os.path.exists(f): continue
    for r in csv.DictReader(open(f)):
        any_depth = True
        cz, d = int(r["transpiled_cz"]), float(r["cdr_r2"])
        if routing:
            near = min(routing, key=lambda k: abs(k - cz))
            print(f"  {cz:>4}  {d:>13.4f}  {routing[near]:>13.4f}  "
                  f"{d - routing[near]:+.4f}  (porownano z {near} CZ)")
        else:
            print(f"  {cz:>4}  {d:>13.4f}  {'brak':>13}")
if any_depth:
    print("\n  Dodatnia roznica = routing szkodzi BARDZIEJ niz sama liczba bramek")
    print("  -> teza pracy jest specyficzna dla routingu, nie tylko dla kosztu dwukubitowego.")
else:
    print("  (brak danych osi glebokosci)")
PY
say ""
say "=== KONIEC $(date) ==="
