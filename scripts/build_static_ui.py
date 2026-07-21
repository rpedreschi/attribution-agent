#!/usr/bin/env python
"""Bake a board dataset into ONE self-contained dashboard HTML file.

    python scripts/build_static_ui.py                  # sample data — zero setup
    python scripts/build_static_ui.py --source mcp     # freeze the live board
    python scripts/build_static_ui.py --out ui/pulse.html

The output embeds the data and removes the network polling, so it renders the
whole dashboard (all four screens) when opened directly in a browser — no server,
no DeltaStream, no Python. Hand the file to anyone; double-click to view.

--source sample uses the built-in $4.28M example board and needs no credentials.
--source mcp reads config/settings.yaml + your DeltaStream login and freezes the
current live numbers into the file.
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_UI = _REPO / "ui" / "index.html"


def _brace_span(text: str, start_after: str) -> tuple[int, int]:
    """Return (start, end) covering the first {...} object after `start_after`."""
    i = text.index(start_after) + len(start_after)
    depth = 0
    for j in range(i, len(text)):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i, j + 1
    raise ValueError("unbalanced braces after " + start_after)


def _board_and_pack(source: str) -> tuple[dict, bytes]:
    """Load the board data once and return (view dict, board-pack .xlsx bytes) so
    the embedded screen and the embedded workbook come from the same numbers."""
    from attribution_agent.api.board_view import _load, build_board_view
    from attribution_agent.spreadsheet.builder import build_workbook_bytes
    loaded = _load(source)
    view = build_board_view(loaded.data, decisions=loaded.decisions,
                            excluded_channels=loaded.excluded, trends=loaded.trends)
    return view, build_workbook_bytes(loaded.data)


def build(source: str) -> str:
    import base64
    html = _UI.read_text()
    view, xlsx = _board_and_pack(source)
    # 1. swap the embedded FALLBACK for the chosen dataset (the initial BOARD).
    s, e = _brace_span(html, "const FALLBACK = ")
    html = html[:s] + json.dumps(view) + html[e:]
    # 2. freeze the data feed (no server), but keep the "recomputed" chip alive:
    #    re-baseline it to page-load so it always reads fresh, and keep the ticker.
    html = html.replace("render();\npoll();",
                        "BOARD.meta.recomputed_at=new Date().toISOString();\nrender();", 1)
    html = re.sub(r"\nsetInterval\(poll,\s*5000\);", "\n", html)
    # 3. embed the matching board pack as base64 so "Export board pack" builds the
    #    file client-side (Blob) — works offline and inside sandboxed hosts where a
    #    data:-URL download link is blocked (e.g. embedded artifact iframes).
    b64 = base64.b64encode(xlsx).decode()
    html = html.replace('let EMBEDDED_PACK = "";', f'let EMBEDDED_PACK = "{b64}";', 1)
    return html


def main() -> None:
    ap = argparse.ArgumentParser(description="Bake the dashboard into one portable HTML file.")
    ap.add_argument("--source", choices=["sample", "mcp"], default="sample",
                    help="sample = built-in example board (no login); mcp = freeze the live board.")
    ap.add_argument("--out", default="ui/deltastream-pulse.html",
                    help="Output file (default: ui/deltastream-pulse.html).")
    args = ap.parse_args()

    html = build(args.source)
    out = _REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"Wrote {out} ({len(html):,} bytes) from {args.source} data.")
    print("Open it in any browser — no server needed.")


if __name__ == "__main__":
    main()
