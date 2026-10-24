#!/usr/bin/env bash
# Full ODRA pilot campaign, unattended.
#
#   bash campaign/run_odra_pilot.sh            # real run (needs IQM_SERVER_URL, IQM_TOKEN)
#   DRY=1 bash campaign/run_odra_pilot.sh      # build everything, submit nothing
#
# - waits (up to MAX_WAIT_H hours) until ODRA answers before every step;
# - every step is retried up to 3 times; twirl and kappa steps resume where they stopped;
# - a step whose output is already complete is skipped, so re-running the script after a
#   crash continues instead of starting over;
# - calibration is fetched at the start and the end; everything goes to the log.
#
# Window p2: the runs that failed on 2026-10-23 (kappa uniform, ladder linear/circular,
# CDR+ZNE on 100 points, depth axis). Window p3: a repeat of p1 for between-window spread.

set -u
cd "$(dirname "$0")/.."
export KMP_DUPLICATE_LIB_OK=TRUE
STAMP=$(date +%Y%m%d_%H%M)
LOG=runs/odra_pilot/campaign_${STAMP}.log
MAX_WAIT_H=${MAX_WAIT_H:-12}
SUBMIT=--submit
[ "${DRY:-0}" = 1 ] && SUBMIT="--no-provenance"
if [ "${DRY:-0}" != 1 ] && { [ -z "${IQM_SERVER_URL:-}" ] || [ -z "${IQM_TOKEN:-}" ]; }; then
  echo "ustaw IQM_SERVER_URL i IQM_TOKEN w tej karcie terminala, potem uruchom ponownie" >&2
  exit 1
fi
mkdir -p runs/odra_pilot

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

odra_up() {
  # a real answer from ODRA = a raw dump with observations; without IQM_SERVER_URL the
  # collector silently writes a placeholder template and exits 0, which is not "up"
  rm -f /tmp/odra_ping_raw.json
  python collect_odra_calibration.py --out /tmp/odra_ping.json --raw-out /tmp/odra_ping_raw.json \
    >/dev/null 2>&1 && grep -q '"observations"' /tmp/odra_ping_raw.json 2>/dev/null
}

wait_for_odra() {
  [ "${DRY:-0}" = 1 ] && return 0
  local waited=0
  until odra_up; do
    if [ $waited -ge $((MAX_WAIT_H * 60)) ]; then
      log "ODRA not reachable for ${MAX_WAIT_H} h -- giving up"; exit 1
    fi
    log "ODRA not answering (HTML/timeout); retry in 10 min"
    sleep 600; waited=$((waited + 10))
  done
}

# rows a finished CSV must have (header excluded)
complete() { [ -f "$1" ] && [ $(($(wc -l < "$1") - 1)) -ge "$2" ]; }

step() {   # step NAME CSV ROWS -- command...
  local name=$1 csv=$2 rows=$3; shift 4
  if complete "$csv" "$rows"; then log "SKIP $name (complete)"; return 0; fi
  for attempt in 1 2 3; do
    wait_for_odra
    log "RUN  $name (attempt $attempt)"
    "$@" >> "$LOG" 2>&1
    if [ "${DRY:-0}" = 1 ]; then log "DRY  $name built"; return 0; fi
    if complete "$csv" "$rows"; then log "DONE $name"; return 0; fi
    log "FAIL $name (attempt $attempt), see log"
  done
  log "GAVE UP $name after 3 attempts -- continuing with the next step"
}

calib() {
  [ "${DRY:-0}" = 1 ] && return 0
  wait_for_odra
  python collect_odra_calibration.py --out "calibrations/odra_${STAMP}_$1.json" \
    --raw-out "calibrations/odra_raw_${STAMP}_$1.json" >> "$LOG" 2>&1 \
    && grep -q '"observations"' "calibrations/odra_raw_${STAMP}_$1.json" 2>/dev/null \
    && log "calibration $1 saved" || log "calibration $1 FAILED"
}

TW="--eval-points 4 --shots 8192 --n-train 10 --n-twirl 6 --campaign odra_pilot"
KB="--budgets 256 512 1024 2048 4096 --reps 10 --eval-points 4 --campaign odra_pilot"
P=runs/odra_pilot

log "=== ODRA pilot campaign ${STAMP} (DRY=${DRY:-0}) ==="
calib start

# ---- window p2: what failed on 2026-10-23 -------------------------------------
step "p2 kappa uniform {1,3,5}" $P/p2_kappa_u135/kappa.csv 5 -- \
  python zne_shot_boundary.py $SUBMIT --device odra --resume --points optimal:star $KB \
    --window-id p2_kappa_u135 --out $P/p2_kappa_u135/kappa.csv
step "p2 twirl logical linear+circular" $P/p2_logical/twirl_logical.csv 8 -- \
  python run_garnet_twirl.py $SUBMIT --device odra --resume \
    --points optimal:linear optimal:circular --arms raw cdr zne --twirl-arms cdr $TW \
    --window-id p2_logical --out $P/p2_logical/twirl_logical.csv
step "p2 twirl native linear+circular" $P/p2_native/twirl_native.csv 4 -- \
  python run_garnet_twirl.py $SUBMIT --device odra --native-twirl --resume \
    --points optimal:linear optimal:circular --arms cdr --twirl-arms cdr $TW \
    --window-id p2_native --out $P/p2_native/twirl_native.csv
step "p2 CDR+ZNE 100 points, 4 rungs" $P/p2_cdr100/cdr_zne_100pt.csv 4 -- \
  python run_odra_cdr.py $SUBMIT --zne --patterns star linear circular all_to_all \
    --eval-points 100 --n-train 100 --shots 8192 --campaign odra_pilot \
    --window-id p2_cdr100 --out $P/p2_cdr100/cdr_zne_100pt.csv
for L in 6 9 13; do
  step "p2 depth L$L" $P/p2_depth_L$L/cdr_zne.csv 1 -- \
    python run_odra_cdr.py $SUBMIT --zne --patterns star --layers $L \
      --eval-points 100 --n-train 100 --shots 8192 --campaign odra_pilot \
      --window-id p2_depth_L$L --out $P/p2_depth_L$L/cdr_zne.csv
done

# ---- window p3: repeat of p1 ---------------------------------------------------
step "p3 twirl logical star+all_to_all" $P/p3_logical/twirl_logical.csv 8 -- \
  python run_garnet_twirl.py $SUBMIT --device odra --resume \
    --points optimal:star optimal:all_to_all --arms raw cdr zne --twirl-arms cdr $TW \
    --window-id p3_logical --out $P/p3_logical/twirl_logical.csv
step "p3 twirl native star+all_to_all" $P/p3_native/twirl_native.csv 4 -- \
  python run_garnet_twirl.py $SUBMIT --device odra --native-twirl --resume \
    --points optimal:star optimal:all_to_all --arms cdr --twirl-arms cdr $TW \
    --window-id p3_native --out $P/p3_native/twirl_native.csv
step "p3 kappa Neyman {1,3,5}" $P/p3_kappa_n135/kappa.csv 5 -- \
  python zne_shot_boundary.py $SUBMIT --device odra --resume --allocation neyman \
    --points optimal:star $KB --window-id p3_kappa_n135 --out $P/p3_kappa_n135/kappa.csv
step "p3 kappa Neyman {1,3,5,7}" $P/p3_kappa_n1357/kappa.csv 5 -- \
  python zne_shot_boundary.py $SUBMIT --device odra --resume --allocation neyman \
    --scales 1 3 5 7 --points optimal:star $KB \
    --window-id p3_kappa_n1357 --out $P/p3_kappa_n1357/kappa.csv

calib end
log "=== KONIEC ==="
grep -E "DONE|SKIP|GAVE UP|FAILED" "$LOG"
