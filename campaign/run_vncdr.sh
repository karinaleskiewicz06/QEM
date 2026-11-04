#!/usr/bin/env bash
# Run window w02vn (interleaved two-axis vnCDR) on ODRA, unattended.
#
#   bash campaign/run_vncdr.sh            # window id w02vn
#   bash campaign/run_vncdr.sh w02vn
#
# Calibration dump at start (unless already taken), the window with --resume retried up to
# 5 times with a wait for ODRA in between, calibration dump at the end, then the
# pre-registered analysis.

set -u
cd "$(dirname "$0")/.."
export KMP_DUPLICATE_LIB_OK=TRUE
WIN=${1:-w02vn}
LOG=runs/odra_campaign/${WIN}.log
if [ -z "${IQM_SERVER_URL:-}" ] || [ -z "${IQM_TOKEN:-}" ]; then
  echo "ustaw IQM_SERVER_URL i IQM_TOKEN w tej karcie terminala, potem uruchom ponownie" >&2
  exit 1
fi
mkdir -p runs/odra_campaign calibrations

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

odra_up() {
  rm -f /tmp/odra_ping_raw.json
  python collect_odra_calibration.py --out /tmp/odra_ping.json --raw-out /tmp/odra_ping_raw.json \
    >/dev/null 2>&1 && grep -q '"observations"' /tmp/odra_ping_raw.json 2>/dev/null
}

wait_for_odra() {
  local waited=0
  until odra_up; do
    [ $waited -ge 720 ] && { log "ODRA unreachable for 12 h -- giving up"; exit 1; }
    log "ODRA not answering; retry in 10 min"; sleep 600; waited=$((waited + 10))
  done
}

calib() {
  local raw="calibrations/odra_raw_${WIN}_$1.json"
  if grep -q '"observations"' "$raw" 2>/dev/null; then log "calibration $1 already taken"; return 0; fi
  wait_for_odra
  python collect_odra_calibration.py --out "calibrations/odra_${WIN}_$1.json" --raw-out "$raw" \
    >> "$LOG" 2>&1 && grep -q '"observations"' "$raw" 2>/dev/null \
    && log "calibration $1 saved" || log "calibration $1 FAILED"
}

calib start
for attempt in 1 2 3 4 5; do
  wait_for_odra
  log "RUN $WIN (attempt $attempt)"
  if python campaign/vncdr_window.py --submit --window-id "$WIN" --resume >> "$LOG" 2>&1; then
    log "DONE $WIN"; break
  fi
  log "FAIL $WIN attempt $attempt (see log); resuming"
done
calib end
log "=== KONIEC $WIN ==="
grep -E "DONE|FAIL|PRIMARY|SUCCESS|NOT SUPPORTED|calibration .* (saved|FAILED|taken)" "$LOG"
