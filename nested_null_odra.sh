#!/bin/bash
# Nested noise controls on the ODRA calibration (review F6).
#   theta=0      -> device null  (measured T1/T2, p_1q, p_2q=0.0203, readout)
#   theta=0.02   -> same + weak coherent over-rotation on every CZ
#   theta=0.05   -> same + stronger
# Models differ by EXACTLY one term, so "excess r2 decay over the null" is meaningful.
# Protocol matched to the ODRA hardware twirl campaign: 4 eval points, 8192 shots,
# n_train=10, n_twirl=6, same ladder. Free -- simulator only.
cd /Users/karinaleskiewicz/QEM || exit 1
export KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1
CAL=calibrations/odra_20260803.json
PTS="optimal:star optimal:linear optimal:circular optimal:all_to_all"
COMMON="--sim --device odra --calibration $CAL --arms raw cdr --twirl-arms cdr \
        --points $PTS --eval-points 4 --shots 8192 --n-train 10 --n-twirl 6"
LOG=nested_null.log
: > "$LOG"
run_set() {
  local label=$1 nwin=$2; shift 2
  for w in $(seq 1 "$nwin"); do
    echo ">>> $label w$w $(date)" >> "$LOG"
    # seed FIXED across windows: it drives seed_transpiler, so varying it would change
    # the routing and put each window at a different CZ count. Window-to-window spread
    # then comes from Aer shot sampling alone (the sim path does not seed the simulator),
    # which is the honest null -- simulation cannot reproduce device drift.
    python run_garnet_twirl.py $COMMON "$@" --window-id "${label}w${w}" --seed 42 \
      --out "nested_${label}_w${w}.csv" >> "$LOG" 2>&1
  done
  python aggregate_twirl_windows.py nested_${label}_w*.csv --out "nested_${label}_banded.csv" >> "$LOG" 2>&1
}
run_set cal00 3
run_set cal02 3 --sim-coh 0.02
run_set cal05 3 --sim-coh 0.05
echo "=== DONE $(date) ===" >> "$LOG"
