"""Terminate the attribution pipeline's continuous queries and wait for them to
actually stop.

DeltaStream won't drop a relation while its continuous query is running, so run
this before teardown.sql. It lists queries via dsql, keeps only the ones whose
SQL references an attribution relation (so it never touches the fico/demo
databases' queries), terminates each, then polls until they've all reached a
terminated state — because TERMINATE is async and an immediate teardown would
fail on the still-terminating relations.

    python scripts/terminate_queries.py --cli ../../dscliv2 --server <url>
    python scripts/terminate_queries.py --cli ../../dscliv2 --server <url> --dry-run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

# Quoted relation names that identify our queries (won't match other databases).
MARKERS = (
    '"touchpoints"', '"conversions"', '"spend"', '"funnel_events"',
    '"web_resolved"', '"web_identity_map"', '"channel_cost"',
    '"mv_spend_by_channel"', '"mv_funnel_by_category"',
    '"mv_channel_touch_distribution"', '"mv_won_revenue_by_account"',
)


def _dsql(cli: str, server: str, stmt: str) -> subprocess.CompletedProcess:
    return subprocess.run([cli, "--server", server, "-c", stmt],
                          capture_output=True, text=True)


def _get(d: dict, *keys: str) -> str:
    for k in keys:
        if k in d and d[k] is not None:
            return str(d[k])
    return ""


def _list_attribution_queries(cli: str, server: str) -> list[tuple[str, str, str]]:
    """Return (id, state, sql-snippet) for every attribution query currently
    listed. `state` is the lower-cased actual state ('' if unreadable)."""
    res = _dsql(cli, server, "LIST QUERIES;")
    out = res.stdout
    i = out.find("[")
    if i == -1:
        sys.exit("Could not read LIST QUERIES output:\n" + out + res.stderr)
    try:
        queries = json.loads(out[i:])
    except json.JSONDecodeError as exc:
        sys.exit(f"Could not parse LIST QUERIES JSON: {exc}\n{out[i:][:500]}")
    rows = []
    for q in queries:
        sql = _get(q, "Query", "query")
        qid = _get(q, "ID", "Id", "id")
        state = _get(q, "Actual State", "ActualState", "actualState", "actual_state").lower()
        if qid and any(m in sql for m in MARKERS):
            rows.append((qid, state, " ".join(sql.split())[:60]))
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description="Terminate the attribution continuous queries.")
    p.add_argument("--cli", default="dsql", help="Path to the dsql binary.")
    p.add_argument("--server", required=True, help="DeltaStream server URL.")
    p.add_argument("--dry-run", action="store_true", help="List, but don't terminate.")
    p.add_argument("--wait-timeout", type=float, default=240.0,
                   help="Seconds to wait for queries to finish terminating (default 240).")
    p.add_argument("--poll", type=float, default=5.0, help="Seconds between polls.")
    args = p.parse_args()

    targets = _list_attribution_queries(args.cli, args.server)
    if not targets:
        print("No attribution queries running.")
        return

    print(f"{len(targets)} attribution queries:")
    for qid, _state, sql in targets:
        print(f"  {qid}  {sql}")
    if args.dry_run:
        print("\n--dry-run: nothing terminated.")
        return

    print("\nTerminating…")
    for qid, _state, _sql in targets:
        r = _dsql(args.cli, args.server, f"TERMINATE QUERY {qid};")
        if r.returncode != 0:                       # retry with the id quoted
            r = _dsql(args.cli, args.server, f'TERMINATE QUERY "{qid}";')
        msg = "requested" if r.returncode == 0 else f"ERROR: {(r.stdout + r.stderr).strip()[:90]}"
        print(f"  {qid}: {msg}")

    # Poll until none are still running/terminating — TERMINATE is async, and an
    # immediate teardown would fail on a relation whose query hasn't stopped yet.
    print("\nWaiting for termination to complete…")
    deadline = time.time() + args.wait_timeout
    while time.time() < deadline:
        time.sleep(args.poll)
        active = [t for t in _list_attribution_queries(args.cli, args.server)
                  if t[1] != "terminated"]   # absent or 'terminated' == done
        if not active:
            print("All queries terminated. Safe to run teardown.")
            return
        print(f"  {len(active)} still terminating… ({', '.join(t[1] or '?' for t in active)})")
    print("WARNING: timed out waiting for termination — some queries may still be "
          "stopping; teardown may need a retry.")


if __name__ == "__main__":
    main()
