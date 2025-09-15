#!/usr/bin/env bash
set -euo pipefail

# Slow exit script to exercise timeouts via --sleep-ms and --repeat
# Flags: --repeat N, --sleep-ms X, --exit-code C

REPEAT=20
SLEEP_MS=200
EXIT_CODE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --repeat) REPEAT="${2:-20}"; shift 2;;
    --sleep-ms) SLEEP_MS="${2:-200}"; shift 2;;
    --exit-code) EXIT_CODE="${2:-0}"; shift 2;;
    --) shift; break;;
    *) shift;;
  esac
done

sleep_s() { perl -e "select(undef,undef,undef,$SLEEP_MS/1000)" 2>/dev/null || sleep 0; }

for i in $(seq 1 "$REPEAT"); do
  echo "slow-exit: tick $i/$REPEAT"
  sleep_s
done

exit "$EXIT_CODE"

