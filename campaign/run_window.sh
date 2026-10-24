#!/usr/bin/env bash
# One campaign window = night A then night B, unattended.
#
#   bash campaign/run_window.sh w01 0        # window w01, point set 0
#   DRY=1 bash campaign/run_window.sh w01 0  # plan only
#
# Each night: calibration, then campaign/odra_window.py with --resume, retried up to 5 times
# with a wait for ODRA in between, then calibration again. Window w uses point set
# (w-1) mod 3; pass it explicitly.

set -u
cd "$(dirname "$0")/.."
export KMP_DUPLICATE_LIB_OK=TRUE
WIN=${1:?window id, e.g. w01}
SET=${2:?point set 0, 1 or 2}
LOG=runs/odra_campaign/${WIN}.log
mkdir -p runs/odra_campaign
MODE=--submit
[ "${DRY:-0}" = 1 ] && MODE=--dry-run

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

odra_up() {
  python collect_odra_calibration.py --out /tmp/odra_ping.json --raw-out /tmp/odra_ping_raw.json \
    >/dev/null 2>&1
}

wait_for_odra() {
  [ "${DRY:-0}" = 1 ] && return 0
  local waited=0
  until odra_up; do
    [ $waited -ge 720 ] && { log "ODRA unreachable for 12 h -- giving up"; exit 1; }
    log "ODRA not answering; retry in 10 min"; sleep 600; waited=$((waited + 10))
  done
}

calib() {
  [ "${DRY:-0}" = 1 ] && return 0
  wait_for_odra
  python collect_odra_calibration.py --out "calibrations/odra_${WIN}$1.json" \
    --raw-out "calibrations/odra_raw_${WIN}$1.json" >> "$LOG" 2>&1 \
    && log "calibration $1 saved" || log "calibration $1 FAILED"
}

for NIGHT in A B; do
  ID=${WIN}${NIGHT}
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
log "=== KONIEC $WIN ==="
grep -E "DONE|FAIL|WARNING|calibration .* (saved|FAILED)" "$LOG"
