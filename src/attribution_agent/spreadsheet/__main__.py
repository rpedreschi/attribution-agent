"""CLI: run the agent pipeline and write the board-pack workbook.

    # Deterministic sample (no infra) -> ./out/acme_cloud_attribution_2026-Q1.xlsx
    python -m attribution_agent.spreadsheet

    # From live ClickHouse views:
    python -m attribution_agent.spreadsheet --source clickhouse
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ..agent.runtime import run_pipeline
from ..config import load_settings
from .builder import build_workbook


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the attribution board pack.")
    parser.add_argument("--source", choices=["sample", "clickhouse"], default="sample",
                        help="Where to read attribution data from (default: sample).")
    parser.add_argument("--out", default=None, help="Output .xlsx path (overrides config).")
    args = parser.parse_args()

    settings = load_settings()
    data = run_pipeline(settings, source=args.source)

    if args.out:
        out_path = Path(args.out)
    else:
        fname = settings.output.filename_template.format(
            customer_id=settings.customer.id, fiscal_period=settings.customer.fiscal_period)
        out_path = Path(settings.output.directory) / fname

    written = build_workbook(data, out_path)
    print(f"Board pack written to {written}")
    print(f"  {len(data.observations)} observations, "
          f"{len(data.recommendations)} recommendations (pending approval)")


if __name__ == "__main__":
    main()
