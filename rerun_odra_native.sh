#!/bin/bash
# Re-run the NATIVE twirl arm on ODRA after the gate-overhead fix (review F3/F8).
#
# The original native run wrapped every post-transpilation CZ with Pauli gates emitted
# as separate `r` pulses: +130% single-qubit gates and 2x depth versus the OFF arm.
# Its "twirled" arm was really a much longer circuit, which is why the measured gain
# was negative. twirl_native now fuses the wrappers (Optimize1qGatesDecomposition,
# no layout/routing stage), cutting the overhead to +22-41% with the CZ count and the
# ideal expectation value unchanged.
#
# Same ladder, shots, n_train and n_twirl as the logical-twirl campaign, so the two
# arms stay directly comparable. ODRA is not metered in Resonance credits.
#
#   export IQM_TOKEN=...  IQM_SERVER_URL=...
#   ./rerun_odra_native.sh
cd /Users/karinaleskiewicz/QEM || exit 1
export KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1
: "${IQM_TOKEN:?ustaw IQM_TOKEN}" "${IQM_SERVER_URL:?ustaw IQM_SERVER_URL}"
PTS="optimal:star optimal:linear optimal:circular optimal:all_to_all"
LOG=odra_native_fixed.log
: > "$LOG"
for w in o1 o2; do
  echo ">>> okno $w $(date)" >> "$LOG"
  python run_garnet_twirl.py --submit --device odra --native-twirl --resume \
    --arms cdr --twirl-arms cdr --points $PTS \
    --eval-points 4 --shots 8192 --n-train 10 --n-twirl 6 \
    --window-id "$w" --out "odra_twirl_native_fixed_${w}.csv" >> "$LOG" 2>&1
  echo "    okno $w gotowe $(date)" >> "$LOG"
done
python aggregate_twirl_windows.py odra_twirl_native_fixed_o*.csv \
  --out odra_twirl_native_fixed_banded.csv >> "$LOG" 2>&1
echo "=== DONE $(date) ===" >> "$LOG"
