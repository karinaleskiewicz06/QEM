#!/usr/bin/env bash
# ODRA queue, one window after another, in this order:
#   1. w04m  raw decisions of all CZ rungs on 100 points (short, ~2-3 h)
#   2. w01B  rest of night B (resumes where it stopped)
#   3. w03dd CDR with and without DD (last)
#
#   caffeinate -dis bash campaign/run_queue.sh
#
# Each step has its own retries and waits for ODRA; a failed step does not stop the queue.

set -u
cd "$(dirname "$0")/.."
export KMP_DUPLICATE_LIB_OK=TRUE
if [ -z "${IQM_SERVER_URL:-}" ] || [ -z "${IQM_TOKEN:-}" ]; then
  echo "ustaw IQM_SERVER_URL i IQM_TOKEN w tej karcie terminala, potem uruchom ponownie" >&2
  exit 1
fi
mkdir -p runs/odra_campaign
Q=runs/odra_campaign/queue.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$Q"; }

say "1/3 w04m start"
python campaign/margin_odra_window.py --submit --window-id w04m 2>&1 | tee -a runs/odra_campaign/w04m.log
say "1/3 w04m end"

say "2/3 w01B (night B) start"
bash campaign/run_night_b.sh
say "2/3 w01B end"

say "3/3 w03dd (DD) start"
bash campaign/run_dd.sh
say "3/3 w03dd end"
