#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:7060}"
AUTH="${TSM_TOKEN:-}"
HDRS=("Content-Type: application/json")
[ -n "$AUTH" ] && HDRS+=("Authorization: Bearer $AUTH")

echo "[E2E] Healthz"
curl -sS "$BASE/healthz" | jq .

echo "[E2E] MCP initialize"
curl -sS -H "${HDRS[0]}" ${HDRS[1]:+ -H "${HDRS[1]}"} \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"e2e","version":"1"}}}' \
  "$BASE/mcp" | jq .

echo "[E2E] MCP tools/list"
curl -sS -H "${HDRS[0]}" ${HDRS[1]:+ -H "${HDRS[1]}"} \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  "$BASE/mcp" | jq '.result.tools | map(.name)'

PROBE_PY="/home/alex/Projects/Reusable-MCP/Test-Start-MCP/scripts/probe.py"
PROBE_SH="/home/alex/Projects/Reusable-MCP/Test-Start-MCP/scripts/probe.sh"

echo "[E2E] MCP run_script (probe.py)"
curl -sS -H "${HDRS[0]}" ${HDRS[1]:+ -H "${HDRS[1]}"} \
  -d "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"run_script\",\"arguments\":{\"path\":\"$PROBE_PY\",\"args\":[\"--smoke\"],\"timeout_ms\":15000}}}" \
  "$BASE/mcp" | jq '.result.structuredContent'

echo "[E2E] REST run_script (probe.sh)"
curl -sS -H "${HDRS[0]}" ${HDRS[1]:+ -H "${HDRS[1]}"} \
  -d "{\"path\":\"$PROBE_SH\",\"args\":[\"--repeat\",\"3\",\"--stderr-lines\",\"1\",\"--sleep-ms\",\"50\"],\"timeout_ms\":5000}" \
  "$BASE/actions/run_script" | jq .

echo "[E2E] SSE run_script_stream (probe.sh)"
curl -sS -N "$BASE/sse/run_script_stream?path=$(python3 -c 'import urllib.parse;print(urllib.parse.quote("'$PROBE_SH'"))')&args=%5B%22--repeat%22%2C%223%22%2C%22--stderr-lines%22%2C%221%22%2C%22--sleep-ms%22%2C%2250%22%5D" | head -n 10

echo "[E2E] list_allowed"
curl -sS -H "${HDRS[0]}" ${HDRS[1]:+ -H "${HDRS[1]}"} -d '{}' "$BASE/actions/list_allowed" | jq .

echo "[E2E] get_stats"
curl -sS -H "${HDRS[0]}" ${HDRS[1]:+ -H "${HDRS[1]}"} -d '{}' "$BASE/actions/get_stats" | jq .

# Optional: Demonstrate preflight enforcement (requires server with TSM_REQUIRE_PREFLIGHT=1)
if [ "${TSM_REQUIRE_PREFLIGHT:-0}" = "1" ]; then
  echo "[E2E] Preflight enforcement demo"
  SESS="sess-e2e"
  # Choose probe.sh as target
  TARGET="$PROBE_SH"
  echo "- run_script without preflight (should 428)"
  curl -sS -H "${HDRS[0]}" ${HDRS[1]:+ -H "${HDRS[1]}"} -H "X-TSM-Session: $SESS" \
    -d "{\"path\":\"$TARGET\",\"args\":[\"--smoke\"]}" \
    "$BASE/actions/run_script" | jq .
  echo "- check_script (records preflight)"
  curl -sS -H "${HDRS[0]}" ${HDRS[1]:+ -H "${HDRS[1]}"} -H "X-TSM-Session: $SESS" \
    -d "{\"path\":\"$TARGET\",\"args\":[\"--smoke\"]}" \
    "$BASE/actions/check_script" | jq .
  echo "- run_script after preflight (should succeed)"
  curl -sS -H "${HDRS[0]}" ${HDRS[1]:+ -H "${HDRS[1]}"} -H "X-TSM-Session: $SESS" \
    -d "{\"path\":\"$TARGET\",\"args\":[\"--smoke\"]}" \
    "$BASE/actions/run_script" | jq .
fi

echo "[E2E] DONE"
