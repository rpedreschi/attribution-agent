"""Run a .sql file statement-by-statement through the DeltaStream CLI (dsql).

The web console and `dsql` both run one statement at a time, and `dsql` rejects
piped stdin. This splits a .sql file on its `;` terminators and feeds each
statement to `dsql -c`, so a whole deploy/teardown is a single command.

Authenticate with the DS_TOKEN env var (dsql reads it automatically).

    export DS_TOKEN="<your-token>"
    python scripts/run_sql.py deltastream/deploy_all.sql \
        --cli ../../dscliv2 --server https://api-kap822.deltastream.io/v2

    # teardown: keep going past harmless 'does not exist' errors
    python scripts/run_sql.py deltastream/teardown.sql --keep-going \
        --cli ../../dscliv2 --server https://api-kap822.deltastream.io/v2

The --cli / --server / --org defaults can also come from the DSQL_BIN /
DS_SERVER / DS_ORG environment variables.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


def split_statements(sql: str) -> list[str]:
    """Split SQL into statements. Strips `--` line comments first, then splits on
    `;`. Safe for the deltastream/ files: no `--` or `;` appears inside a string
    literal in them."""
    stripped = []
    for line in sql.splitlines():
        i = line.find("--")
        stripped.append(line if i == -1 else line[:i])
    text = "\n".join(stripped)
    return [s.strip() for s in text.split(";") if s.strip()]


def main() -> None:
    p = argparse.ArgumentParser(
        description="Run a .sql file through dsql, one statement at a time.")
    p.add_argument("file", help="Path to the .sql file to run.")
    p.add_argument("--cli", default=os.environ.get("DSQL_BIN", "dsql"),
                   help="Path to the dsql binary (default: dsql, or $DSQL_BIN).")
    p.add_argument("--server",
                   default=os.environ.get("DS_SERVER", "https://api.deltastream.io/v2"),
                   help="DeltaStream server URL (or $DS_SERVER).")
    p.add_argument("--org", default=os.environ.get("DS_ORG"),
                   help="Organization id/name, if dsql needs it (or $DS_ORG).")
    p.add_argument("--keep-going", action="store_true",
                   help="Continue after a statement errors (default: stop).")
    args = p.parse_args()

    with open(args.file) as fh:
        statements = split_statements(fh.read())
    print(f"{len(statements)} statements from {args.file}\n")

    base = [args.cli, "--server", args.server]
    if args.org:
        base += ["-g", args.org]

    failures = 0
    for i, stmt in enumerate(statements, 1):
        head = " ".join(stmt.split())[:72]
        print(f"[{i}/{len(statements)}] {head}")
        res = subprocess.run(base + ["-c", stmt + ";"], capture_output=True, text=True)
        out = (res.stdout + res.stderr).strip()
        if res.returncode != 0:
            failures += 1
            print(f"    ERROR: {out}")
            if not args.keep_going:
                print(f"\nStopped at statement {i}. Fix it (or pass --keep-going), "
                      "then re-run.")
                sys.exit(1)
        elif out:
            print(f"    {out.splitlines()[-1][:100]}")

    print(f"\nDone — {len(statements) - failures}/{len(statements)} succeeded, "
          f"{failures} failed.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
