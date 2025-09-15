#!/usr/bin/env bash
set -euo pipefail

# A simple POSIX shell probe to exercise stdout/stderr, timing, truncation, and exit codes.
# Supported flags (validated by server policy):
#   --repeat N           Number of stdout lines
#   --stderr-lines M     Number of stderr lines
#   --sleep-ms X         Delay between lines (milliseconds)
#   --bytes N            Emit N bytes to stdout at end
#   --exit-code C        Final exit code
#   --json               Emit a final JSON line
#   --ping               Include ping-ish ticks in stdout
#   --smoke              Quick defaults (2 out, 1 err)

REPEAT=3
ERRN=1
SLEEP_MS=50
BYTES=0
EXIT_CODE=0
JSON_OUT=0
PING=0
SMOKE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --repeat) REPEAT="${2:-3}"; shift 2;;
    --stderr-lines) ERRN="${2:-1}"; shift 2;;
    --sleep-ms) SLEEP_MS="${2:-50}"; shift 2;;
    --bytes) BYTES="${2:-0}"; shift 2;;
    --exit-code) EXIT_CODE="${2:-0}"; shift 2;;
    --json) JSON_OUT=1; shift;;
    --ping) PING=1; shift;;
    --smoke) SMOKE=1; shift;;
    --) shift; break;;
    *) shift;;
  esac
done

if [ "$SMOKE" = "1" ]; then
  REPEAT=2
  ERRN=1
  SLEEP_MS=50
fi

sleep_s() {
  # Portable sleep for milliseconds
  perl -e "select(undef,undef,undef,$SLEEP_MS/1000)" 2>/dev/null || sleep 0
}

for i in $(seq 1 "$REPEAT"); do
  echo "probe-sh: line $i/$REPEAT"
  if [ "$PING" = "1" ]; then
    echo "probe-sh: ping $i"
  fi
  sleep_s
done

for j in $(seq 1 "$ERRN"); do
  echo "probe-sh: warn $j/$ERRN" >&2
  sleep_s
done

if [ "$BYTES" -gt 0 ]; then
  if command -v head >/dev/null 2>&1; then
    head -c "$BYTES" /dev/zero | tr '\0' 'X'
  else
    python3 - <<PY
import sys
sys.stdout.write('X'*int($BYTES))
sys.stdout.flush()
PY
  fi
  echo
fi

if [ "$JSON_OUT" = "1" ]; then
  printf '{"ok": %s, "repeat": %s, "stderr_lines": %s, "sleep_ms": %s}\n' \
    "$([ "$EXIT_CODE" -eq 0 ] && echo true || echo false)" "$REPEAT" "$ERRN" "$SLEEP_MS"
fi

exit "$EXIT_CODE"

