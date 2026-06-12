"""Terminate the attribution pipeline's continuous queries.

DeltaStream won't drop a relation while its continuous query is running, so run
this before teardown.sql. It lists queries via dsql, keeps only the ones whose
SQL references an attribution relation (so it never touches the fico/demo
databases' queries), and terminates each.

    python scripts/terminate_queries.py --cli ../../dscliv2 --server <url>
    python scripts/terminate_queries.py --cli ../../dscliv2 --server <url> --dry-run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

# Quoted relation names that identify our queries (won't match other databases).
MARKERS = (
    '"touchpoints"', '"conversions"', '"spend"', '"funnel_events"',
    '"web_resolved"', '"web_identity_map"',
    '"mv_spend_by_channel"', '"mv_funnel_by_category"',
    '"mv_channel_touch_distribution"', '"mv_won_revenue_by_account"',
)


def _dsql(cli: str, server: str, stmt: str) -> subprocess.CompletedProcess:
    return subprocess.run([cli, "--server", server, "-c", stmt],
                          capture_output=True, text=True)


def _get(d: dict, *keys: str) -> str:
    for k in keys:
        if k in d and d[k]:
            return str(d[k])
    return ""


def main() -> None:
    p = argparse.ArgumentParser(description="Terminate the attribution continuous queries.")
    p.add_argument("--cli", default="dsql", help="Path to the dsql binary.")
    p.add_argument("--server", required=True, help="DeltaStream server URL.")
    p.add_argument("--dry-run", action="store_true", help="List, but don't terminate.")
    args = p.parse_args()

    res = _dsql(args.cli, args.server, "LIST QUERIES;")
    out = res.stdout
    i = out.find("[")               # skip any device-code line before the JSON
    if i == -1:
        sys.exit("Could not read LIST QUERIES output:\n" + out + res.stderr)
    try:
        queries = json.loads(out[i:])
    except json.JSONDecodeError as exc:
        sys.exit(f"Could not parse LIST QUERIES JSON: {exc}\n{out[i:][:500]}")

    targets = []
    for q in queries:
        sql = _get(q, "Query", "query")
        qid = _get(q, "ID", "Id", "id")
        if qid and any(m in sql for m in MARKERS):
            targets.append((qid, " ".join(sql.split())[:60]))

    if not targets:
        print("No attribution queries running.")
        return

    print(f"{len(targets)} attribution queries:")
    for qid, sql in targets:
        print(f"  {qid}  {sql}")
    if args.dry_run:
        print("\n--dry-run: nothing terminated.")
        return

    print()
    for qid, _ in targets:
        r = _dsql(args.cli, args.server, f"TERMINATE QUERY {qid};")
        if r.returncode != 0:                       # retry with the id quoted
            r = _dsql(args.cli, args.server, f'TERMINATE QUERY "{qid}";')
        msg = "terminated" if r.returncode == 0 else f"ERROR: {(r.stdout + r.stderr).strip()[:90]}"
        print(f"  {qid}: {msg}")


if __name__ == "__main__":
    main()
