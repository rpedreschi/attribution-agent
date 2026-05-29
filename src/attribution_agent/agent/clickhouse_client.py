"""Thin ClickHouse query layer over the attribution views.

One method per view the board pack needs. Imports clickhouse_connect lazily so
the package (and the deterministic sample path) work without the driver
installed. Returns plain dict rows; reporting.py shapes them into BoardPackData.
"""
from __future__ import annotations

from typing import Any

from ..config import ClickHouseConfig


class ClickHouseClient:
    def __init__(self, cfg: ClickHouseConfig) -> None:
        import clickhouse_connect  # lazy import

        self.db = cfg.database
        self._client = clickhouse_connect.get_client(
            host=cfg.host, port=cfg.port, secure=cfg.secure,
            username=cfg.username, password=cfg.password or "",
            database=cfg.database,
        )

    def _rows(self, sql: str) -> list[dict[str, Any]]:
        result = self._client.query(sql)
        cols = result.column_names
        return [dict(zip(cols, row)) for row in result.result_rows]

    def attribution_by_channel(self) -> list[dict[str, Any]]:
        return self._rows(f"SELECT * FROM {self.db}.v_attribution_by_channel")

    def funnel_metrics(self) -> list[dict[str, Any]]:
        return self._rows(f"SELECT * FROM {self.db}.funnel_metrics ORDER BY won DESC")

    def cac_roi(self) -> list[dict[str, Any]]:
        return self._rows(f"SELECT * FROM {self.db}.cac_roi ORDER BY roi_multiple DESC")

    def channel_conversions_trailing_90d(self) -> dict[str, int]:
        """Conversion counts per channel for the guardrail eligibility check."""
        rows = self._rows(f"""
            SELECT program_category AS channel,
                   countIf(event_type IN ('mql','sql','opp_created','closed_won')) AS conversions
            FROM {self.db}.conversions
            WHERE event_time >= now() - INTERVAL 90 DAY
            GROUP BY program_category
        """)
        return {r["channel"]: int(r["conversions"]) for r in rows}

    def top_campaigns(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._rows(f"""
            SELECT campaign, any(channel) AS channel,
                   sum(attributed_revenue) AS attributed_revenue
            FROM {self.db}.v_won_journeys
            GROUP BY campaign
            ORDER BY attributed_revenue DESC
            LIMIT {limit}
        """)
