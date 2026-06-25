"""Print the row count of each DeltaStream materialized view over MCP.

A quick health check: are the MVs deployed and populated? Counts every view in
config.deltastream.views via a `SELECT count(*)`, and flags any that error
(usually "not deployed yet") so you can see at a glance what's live.

    python scripts/mv_counts.py
"""
from __future__ import annotations

from attribution_agent.config import load_settings
from attribution_agent.agent.deltastream_mcp import DeltaStreamMCPClient, DeltaStreamMCPError


def _count(client: DeltaStreamMCPClient, tool: str) -> int | str:
    """count(*) on the relation behind an MV tool (cheap — one row back)."""
    prefix = f"{client.cfg.database}_{client.cfg.schema_name}_"
    mv = tool[len(prefix):] if tool.startswith(prefix) else tool
    sql = (f'SELECT count(*) AS "n" '
           f'FROM "{client.cfg.database}"."{client.cfg.schema_name}"."{mv}"')
    rows = client.call_tool(tool, {"clickhouse_sql": sql})
    if not rows:
        return 0
    # tolerate whatever the count column comes back named
    val = next(iter(rows[0].values()), 0)
    try:
        return int(val)
    except (TypeError, ValueError):
        return val


def main() -> None:
    cfg = load_settings().deltastream
    if not cfg.api_token:
        raise SystemExit("No DeltaStream API token configured "
                         "(set DELTASTREAM_API_TOKEN or config/settings.yaml).")
    client = DeltaStreamMCPClient(cfg)

    print(f"MCP endpoint: {cfg.mcp_endpoint}\n")
    width = max(len(k) for k in cfg.views)
    for key, tool in cfg.views.items():
        try:
            n = _count(client, tool)
            print(f"  {key:<{width}}  {n:>8}  ({tool})")
        except DeltaStreamMCPError as exc:
            print(f"  {key:<{width}}  {'ERR':>8}  {exc}")


if __name__ == "__main__":
    main()
