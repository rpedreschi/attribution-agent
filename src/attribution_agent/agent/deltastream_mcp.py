"""DeltaStream MCP client.

DeltaStream exposes each materialized view the API token's role can SELECT as an
MCP tool. This is a thin JSON-RPC-over-HTTP client (stdlib only) that lists those
tools and calls them, plus a `query_view` helper that maps the logical view keys
in config.deltastream.views to the live MV tool names.

Transport: HTTP POST to the MCP endpoint, `Authorization: Bearer <API_TOKEN>`,
JSON-RPC 2.0 methods `tools/list` and `tools/call`. Tool results follow the MCP
content convention; rows are parsed from the returned JSON/text.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..config import DeltaStreamConfig


class DeltaStreamMCPError(RuntimeError):
    pass


class DeltaStreamMCPClient:
    def __init__(self, cfg: DeltaStreamConfig, *, timeout: float = 30.0) -> None:
        self.cfg = cfg
        self.timeout = timeout
        self._id = 0

    # -- transport ----------------------------------------------------------

    def _rpc(self, method: str, params: dict | None = None) -> Any:
        if not self.cfg.api_token:
            raise DeltaStreamMCPError("No DeltaStream API token configured.")
        self._id += 1
        rpc_id = self._id
        body = json.dumps({
            "jsonrpc": "2.0", "id": rpc_id, "method": method,
            "params": params or {},
        }).encode()
        # DeltaStream's MCP endpoint speaks Streamable HTTP: a POST may come back
        # as plain JSON or as an SSE (text/event-stream) frame, so accept both.
        req = urllib.request.Request(
            self.cfg.mcp_endpoint, data=body, method="POST",
            headers={
                "Authorization": f"Bearer {self.cfg.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json,text/event-stream",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300] if exc.fp else ""
            raise DeltaStreamMCPError(f"MCP HTTP {exc.code}: {exc.reason} {detail}") from exc
        except urllib.error.URLError as exc:
            raise DeltaStreamMCPError(f"MCP request failed: {exc.reason}") from exc

        payload = _parse_rpc_body(raw, content_type, rpc_id)
        if payload is None:
            raise DeltaStreamMCPError(f"No JSON-RPC response in MCP reply: {raw[:200]}")
        if payload.get("error"):
            raise DeltaStreamMCPError(f"MCP error: {payload['error']}")
        return payload.get("result")

    # -- MCP primitives -----------------------------------------------------

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._rpc("tools/list")
        return (result or {}).get("tools", [])

    def call_tool_raw(self, name: str, arguments: dict | None = None) -> Any:
        """Call an MV tool and return the raw JSON-RPC result (for debugging the
        response shape during bring-up)."""
        return self._rpc("tools/call", {"name": name, "arguments": arguments or {}})

    def call_tool(self, name: str, arguments: dict | None = None) -> list[dict[str, Any]]:
        """Call an MV tool and return its rows as dicts."""
        return _rows_from_result(self.call_tool_raw(name, arguments))

    # -- convenience --------------------------------------------------------

    def query_view(self, view_key: str) -> list[dict[str, Any]]:
        """Query a materialized view by its logical key (config.deltastream.views)."""
        tool = self.cfg.views.get(view_key)
        if not tool:
            raise DeltaStreamMCPError(f"Unknown view key '{view_key}'.")
        return self.query_tool(tool)

    def query_tool(self, tool: str) -> list[dict[str, Any]]:
        """SELECT * from the MV behind an MCP tool, paginated.

        DeltaStream's MV tools take a `clickhouse_sql` SELECT argument, reference
        the relation fully-qualified + double-quoted (DeltaStream is
        case-sensitive), and cap each call at 100 rows — so page with LIMIT/OFFSET.
        """
        rows: list[dict[str, Any]] = []
        page, offset = 100, 0
        while True:
            batch = self.call_tool(tool, {"clickhouse_sql": self.select_sql(tool, page, offset)})
            rows.extend(batch)
            if len(batch) < page:
                break
            offset += page
        return rows

    def select_sql(self, tool: str, limit: int = 100, offset: int = 0) -> str:
        """Build a fully-qualified, double-quoted SELECT for an MV tool. The tool
        name is <database>_<schema>_<relation>; the relation is the remainder
        after the database/schema prefix from config."""
        prefix = f"{self.cfg.database}_{self.cfg.schema_name}_"
        mv = tool[len(prefix):] if tool.startswith(prefix) else tool
        return (f'SELECT * FROM "{self.cfg.database}"."{self.cfg.schema_name}"."{mv}" '
                f'LIMIT {limit} OFFSET {offset}')

    @property
    def available(self) -> bool:
        try:
            self.list_tools()
            return True
        except DeltaStreamMCPError:
            return False


def _parse_rpc_body(raw: str, content_type: str, rpc_id: int) -> dict | None:
    """Extract the JSON-RPC envelope from either a plain-JSON or SSE response.

    SSE frames look like `event: message\\ndata: {json}\\n\\n`; there may be
    several, so pick the one carrying our id (or any result/error).
    """
    raw = raw.strip()
    if not raw:
        return None
    if "text/event-stream" in content_type or raw.startswith("event:") or raw.startswith("data:"):
        candidates: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                candidates.append(obj)
        for obj in candidates:
            if obj.get("id") == rpc_id:
                return obj
        for obj in candidates:
            if "result" in obj or "error" in obj:
                return obj
        return candidates[-1] if candidates else None
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _rows_from_result(result: Any) -> list[dict[str, Any]]:
    """Normalize an MCP tools/call result into a list of row dicts.

    DeltaStream returns structured content; this also tolerates the generic MCP
    shape {"content": [{"type": "text", "text": "<json>"}]} and a bare list.
    """
    if result is None:
        return []
    # Newer structured form.
    if isinstance(result, dict) and isinstance(result.get("structuredContent"), dict):
        rows = result["structuredContent"].get("rows")
        if isinstance(rows, list):
            return rows
    if isinstance(result, dict) and isinstance(result.get("rows"), list):
        return result["rows"]
    # Generic MCP text content carrying JSON.
    if isinstance(result, dict) and isinstance(result.get("content"), list):
        out: list[dict[str, Any]] = []
        for block in result["content"]:
            text = block.get("text") if isinstance(block, dict) else None
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                out.extend(r for r in parsed if isinstance(r, dict))
            elif isinstance(parsed, dict):
                out.append(parsed)
        return out
    if isinstance(result, list):
        return [r for r in result if isinstance(r, dict)]
    return []
