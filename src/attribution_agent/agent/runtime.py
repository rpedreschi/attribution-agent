"""AgentCore runtime entrypoint.

Orchestrates the weekly cycle:
    1. reporting       -> BoardPackData (from ClickHouse, or sample for the demo)
    2. observations    -> prose commentary (scheduled LLM job)
    3. recommendations -> guardrailed reallocation proposals (the agent)

`run_pipeline()` is the plain callable used by the spreadsheet CLI and tests.
`agent_entrypoint()` adapts it to the Bedrock AgentCore Runtime contract when
the bedrock_agentcore SDK is installed; the import is guarded so the package
works without it.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..config import Settings, load_settings
from .guardrails import Guardrails
from .llm import ClaudeClient
from .observations import generate_observations
from .recommendations import RecommendationEngine
from .reporting import BoardPackData


def run_pipeline(settings: Settings | None = None, *, source: str = "sample") -> BoardPackData:
    """Build the board pack data and attach observations + recommendations.

    source="sample"     -> canonical Acme Cloud figures (no infra needed)
    source="clickhouse" -> live attribution views
    """
    settings = settings or load_settings()

    if source == "clickhouse":
        from .clickhouse_client import ClickHouseClient

        client = ClickHouseClient(settings.clickhouse)
        data = BoardPackData.from_clickhouse(
            client, settings.customer.display_name, settings.customer.fiscal_period)
    else:
        data = BoardPackData.from_sample()

    claude = ClaudeClient(settings.agent)
    data.observations = generate_observations(data, claude)

    engine = RecommendationEngine(Guardrails(settings.agent.guardrails), claude)
    data.recommendations = engine.propose(data)
    return data


def _summarize(data: BoardPackData) -> dict[str, Any]:
    """JSON-serializable summary for an AgentCore response / audit log."""
    return {
        "customer": data.customer_name,
        "fiscal_period": data.fiscal_period,
        "total_attributed_revenue": data.total_attributed,
        "blended_roi": round(data.blended_roi, 2),
        "model_agreement": round(data.model_agreement, 3),
        "observations": data.observations,
        "recommendations": [
            {
                "channel": r.channel, "action": r.action,
                "current_spend": round(r.current_spend),
                "proposed_spend": round(r.proposed_spend),
                "delta": round(r.delta),
                "expected_revenue_impact": round(r.expected_revenue_impact),
                "rationale": r.rationale,
                "source_refs": r.source_refs,
                "guardrail": asdict(r.guardrail) if r.guardrail else None,
                "status": "pending_human_approval",
            }
            for r in data.recommendations
        ],
    }


# --- Bedrock AgentCore Runtime adapter (optional) ---------------------------
try:
    from bedrock_agentcore.runtime import BedrockAgentCoreApp  # type: ignore

    app = BedrockAgentCoreApp()

    @app.entrypoint
    def agent_entrypoint(payload: dict, context: Any = None) -> dict:  # noqa: ANN401
        source = payload.get("source", "clickhouse")
        data = run_pipeline(source=source)
        return _summarize(data)

except Exception:  # noqa: BLE001 - SDK not installed in the demo environment
    app = None

    def agent_entrypoint(payload: dict, context: Any = None) -> dict:  # noqa: ANN401
        source = payload.get("source", "sample")
        return _summarize(run_pipeline(source=source))


if __name__ == "__main__":
    import json

    print(json.dumps(_summarize(run_pipeline(source="sample")), indent=2))
