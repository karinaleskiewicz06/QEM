#!/usr/bin/env bash
# Night B of window w01 (30 CZ linear, 57 CZ all_to_all): the missing rows of deck slides 25-26.
#
#   bash campaign/run_night_b.sh
#
# Waits until window w02vn has finished (ODRA runs one window at a time), archives the stale
# partial night B from 2026-11-03 (moved, not deleted), takes a fresh start calibration, runs
# night B with --resume (saved after every 100-circuit job, up to 8 attempts with a wait for
# ODRA in between), end calibration, then the CSVs and the slide numbers.

set -u
cd "$(dirname "$0")/.."
export KMP_DUPLICATE_LIB_OK=TRUE
ID=w01B
LOG=runs/odra_campaign/${ID}.log
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
    [ $waited -ge 1440 ] && { log "ODRA unreachable for 24 h -- giving up"; exit 1; }
    log "ODRA not answering; retry in 10 min"; sleep 600; waited=$((waited + 10))
  done
}

calib() {
  local raw="calibrations/odra_raw_${ID}_$1.json"
  if grep -q '"observations"' "$raw" 2>/dev/null; then log "calibration $1 already taken"; return 0; fi
  wait_for_odra
  python collect_odra_calibration.py --out "calibrations/odra_${ID}_$1.json" --raw-out "$raw" \
    >> "$LOG" 2>&1 && grep -q '"observations"' "$raw" 2>/dev/null \
    && log "calibration $1 saved" || log "calibration $1 FAILED"
}

# 1. one window at a time
said=0
while pgrep -f "vncdr_window.py|run_vncdr.sh" >/dev/null; do
  [ $said = 0 ] && { echo "[$(date '+%F %T')] czekam, aż skończy się w02vn ..."; said=1; }
  sleep 120
done

# 2. archive the stale partial night B (400 circuits from 2026-11-03, older calibration)
if [ ! -f runs/odra_campaign/.w01B_fresh ]; then
  stamp=aborted_20261103
  [ -d runs/odra_campaign/w01B ] && mv runs/odra_campaign/w01B "runs/odra_campaign/w01B_$stamp"
  for f in calibrations/odra_raw_w01B_start.json calibrations/odra_w01B_start.json; do
    [ -f "$f" ] && mv "$f" "${f%.json}_$stamp.json"
  done
  touch runs/odra_campaign/.w01B_fresh
fi

# 3. night B
calib start
for attempt in 1 2 3 4 5 6 7 8; do
  wait_for_odra
  log "RUN $ID (night B, point set 0, attempt $attempt)"
  if python campaign/odra_window.py --submit --window-id "$ID" --night B --point-set 0 \
       --chunk 100 --resume >> "$LOG" 2>&1; then
    log "DONE $ID"; break
  fi
  log "FAIL $ID attempt $attempt (see log); resuming"
done
calib end

# 4. CSVs and the slide numbers
python campaign/odra_window.py --analyse runs/odra_campaign/$ID >> "$LOG" 2>&1
python campaign/slide_numbers.py | tee runs/odra_campaign/slide_numbers.txt
log "=== KONIEC $ID ==="
