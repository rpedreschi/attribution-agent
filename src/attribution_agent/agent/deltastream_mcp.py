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
        body = json.dumps({
            "jsonrpc": "2.0", "id": self._id, "method": method,
            "params": params or {},
        }).encode()
        req = urllib.request.Request(
            self.cfg.mcp_endpoint, data=body, method="POST",
            headers={
                "Authorization": f"Bearer {self.cfg.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read())
        except urllib.error.URLError as exc:
            raise DeltaStreamMCPError(f"MCP request failed: {exc}") from exc
        if "error" in payload:
            raise DeltaStreamMCPError(f"MCP error: {payload['error']}")
        return payload.get("result")

    # -- MCP primitives -----------------------------------------------------

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._rpc("tools/list")
        return (result or {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> list[dict[str, Any]]:
        """Call an MV tool and return its rows as dicts."""
        result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        return _rows_from_result(result)

    # -- convenience --------------------------------------------------------

    def query_view(self, view_key: str, arguments: dict | None = None) -> list[dict[str, Any]]:
        """Query a materialized view by its logical key (config.deltastream.views)."""
        tool = self.cfg.views.get(view_key)
        if not tool:
            raise DeltaStreamMCPError(f"Unknown view key '{view_key}'.")
        return self.call_tool(tool, arguments)

    @property
    def available(self) -> bool:
        try:
            self.list_tools()
            return True
        except DeltaStreamMCPError:
            return False


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
