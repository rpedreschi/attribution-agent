#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Window 2: wait until the live pipeline has data, then serve the dashboard JSON.
# Run this alongside demo_up.sh (which streams in window 1). Usage:
#   bash scripts/demo_serve.sh [port]     (default port 8787)
PORT="${1:-8787}"

echo "==> waiting for the pipeline to populate (won-revenue rows)…"
for i in $(seq 1 30); do
  n="$(python - <<'PY'
try:
    from attribution_agent.config import load_settings
    from attribution_agent.agent.deltastream_mcp import DeltaStreamMCPClient
    c = DeltaStreamMCPClient(load_settings().deltastream)
    print(len(c.query_view("won_revenue_by_account")))
except Exception:
    print(0)
PY
)"
  if [ "${n:-0}" -gt 0 ]; then echo "    ready — $n won accounts in the views"; break; fi
  echo "    not ready yet (${i}/30); sleeping 10s"; sleep 10
done

echo "==> serving board view at http://localhost:$PORT/board.json"
echo "    open: ui/index.html?api=http://localhost:$PORT/board.json"
exec python -m attribution_agent.api.board_view --source mcp --serve "$PORT"
