#!/bin/bash
# Overnight FREE sim bundle (methodology §9c). Brackets the hardware twirl+CDR result with matched-
# shots sim regimes, each aggregated into drift-banded Δr² + trend. Calibrated 2026-09-04:
#   NULL      (depolarizing)        -> twirl does NOT help: Δr² ≈ 0, flat/negative trend
#   coh=0.05  (moderate coherent)   -> twirl HELPS, Δr² grows with CZ; OFF r² 0.94->0.83 == the
#                                      hardware regime (garnet_cdr collapse 0.99->0.69). PRIMARY.
#   coh=0.10  (stronger coherent)   -> twirl helps MORE -> Δr² scales with the coherent fraction.
# Exact (b) params, so this also validates the full pipeline end-to-end before spending credits.
# Outputs night_*.csv in repo root; progress + aggregated tables in overnight_sims.log.
cd /Users/karinaleskiewicz/QEM || exit 1
export KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1
LOG=overnight_sims.log
: > "$LOG"
echo "=== overnight sims START $(date) ===" >> "$LOG"
PTS="optimal:star optimal:all_to_all adverse:all_to_all"
COMMON="--arms raw cdr zne --twirl-arms cdr --points $PTS --eval-points 4 --shots 1024 --n-train 10 --n-twirl 6"

run_set() {  # $1=label $2=n_windows $3..=extra flags (e.g. --sim-coh 0.05)
  local label=$1 nwin=$2; shift 2
  echo "--- $label ($nwin windows) $(date) ---" >> "$LOG"
  local w
  for w in $(seq 1 "$nwin"); do
    echo ">>> $label w$w $(date)" >> "$LOG"
    python run_garnet_twirl.py --sim "$@" $COMMON --window-id "${label}w${w}" \
      --out "night_${label}_w${w}.csv" >> "$LOG" 2>&1
  done
  python aggregate_twirl_windows.py night_${label}_w*.csv --out "night_${label}_banded.csv" >> "$LOG" 2>&1
}

run_set null  5                    # depolarizing null
run_set coh05 5 --sim-coh 0.05     # PRIMARY positive control (hardware-matching regime)
run_set coh10 3 --sim-coh 0.10     # stronger coherence -> Δr² scales

echo "=== overnight sims DONE $(date) ===" >> "$LOG"
echo "READ: null Δr²≈0 flat; coh05 Δr²>0 growing with CZ (== hardware regime); coh10 larger Δr²." >> "$LOG"
echo "Banded outputs: night_null_banded.csv, night_coh05_banded.csv, night_coh10_banded.csv" >> "$LOG"
