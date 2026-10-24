#!/usr/bin/env bash
# Run the nights of a window in any order, unattended.
#
#   bash campaign/run_nights.sh w01 0 A P5 B
#   DRY=1 bash campaign/run_nights.sh w01 0 A P5 B
#
# For each night: wait until no odra_window.py of that night is still running (so a night
# started elsewhere is not run twice), calibration unless already taken, odra_window.py with
# --resume retried up to 5 times with a wait for ODRA in between, calibration again. A
# night that is already complete costs one quick --resume pass that skips every block.

set -u
cd "$(dirname "$0")/.."
export KMP_DUPLICATE_LIB_OK=TRUE
WIN=${1:?window id, e.g. w01}
SET=${2:?point set 0, 1 or 2}
shift 2
if [ $# -eq 0 ]; then NIGHTS_TO_RUN=(A B); else NIGHTS_TO_RUN=("$@"); fi
LOG=runs/odra_campaign/${WIN}.log
if [ "${DRY:-0}" != 1 ] && { [ -z "${IQM_SERVER_URL:-}" ] || [ -z "${IQM_TOKEN:-}" ]; }; then
  echo "ustaw IQM_SERVER_URL i IQM_TOKEN w tej karcie terminala, potem uruchom ponownie" >&2
  exit 1
fi
mkdir -p runs/odra_campaign
MODE=--submit
[ "${DRY:-0}" = 1 ] && MODE=--dry-run

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

odra_up() {
  rm -f /tmp/odra_ping_raw.json
  python collect_odra_calibration.py --out /tmp/odra_ping.json --raw-out /tmp/odra_ping_raw.json \
    >/dev/null 2>&1 && grep -q '"observations"' /tmp/odra_ping_raw.json 2>/dev/null
}

wait_for_odra() {
  [ "${DRY:-0}" = 1 ] && return 0
  local waited=0
  until odra_up; do
    [ $waited -ge 720 ] && { log "ODRA unreachable for 12 h -- giving up"; exit 1; }
    log "ODRA not answering; retry in 10 min"; sleep 600; waited=$((waited + 10))
  done
}

wait_not_running() {   # a night already running elsewhere (e.g. started by run_window.sh)
  local id=$1 said=0
  while pgrep -f "odra_window.py .*--window-id $id( |$)" >/dev/null; do
    [ $said = 0 ] && { log "waiting for the running $id to finish"; said=1; }
    sleep 60
  done
}

calib() {   # calib NAME -- skipped if a real calibration of that name already exists
  [ "${DRY:-0}" = 1 ] && return 0
  local raw="calibrations/odra_raw_${WIN}$1.json"
  if grep -q '"observations"' "$raw" 2>/dev/null; then log "calibration $1 already taken"; return 0; fi
  wait_for_odra
  python collect_odra_calibration.py --out "calibrations/odra_${WIN}$1.json" --raw-out "$raw" \
    >> "$LOG" 2>&1 && grep -q '"observations"' "$raw" 2>/dev/null \
    && log "calibration $1 saved" || log "calibration $1 FAILED"
}

for NIGHT in "${NIGHTS_TO_RUN[@]}"; do
  ID=${WIN}${NIGHT}
  wait_not_running "$ID"
  calib "${NIGHT}_start"
  for attempt in 1 2 3 4 5; do
    wait_for_odra
    log "RUN $ID (night $NIGHT, point set $SET, attempt $attempt)"
    if python campaign/odra_window.py $MODE --window-id "$ID" --night "$NIGHT" \
         --point-set "$SET" --resume >> "$LOG" 2>&1; then
      log "DONE $ID"; break
    fi
    log "FAIL $ID attempt $attempt (see log); resuming"
  done
  calib "${NIGHT}_end"
done
log "=== KONIEC $WIN (${NIGHTS_TO_RUN[*]}) ==="
grep -E "DONE|FAIL|WARNING|calibration .* (saved|FAILED|taken)" "$LOG"
