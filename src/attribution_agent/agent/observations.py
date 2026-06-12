"""Observation generation — a scheduled LLM job (NOT the agent).

Reads BoardPackData and writes the short prose commentary that appears on the
Executive Summary sheet. Uses Claude when Bedrock is reachable; otherwise emits
deterministic, number-grounded fallback prose so the artifact is never empty.

This job only describes the numbers. It does not propose actions — that is the
recommendation agent's job, kept separate so the honest framing holds.
"""
from __future__ import annotations

import json

from .llm import BedrockUnavailable, ClaudeClient
from .reporting import BoardPackData

_SYSTEM = (
    "You are a B2B marketing analyst writing the commentary for a CMO's weekly "
    "board pack. Be precise, quantitative, and neutral. Every sentence must cite "
    "a number from the data. No marketing fluff, no recommendations — description "
    "only. Output 3-5 bullet observations, one sentence each."
)


def _facts(data: BoardPackData) -> dict:
    ranked = data.ranked_by_roi()
    return {
        "fiscal_period": data.fiscal_period,
        "total_attributed_revenue": data.total_attributed,
        "revenue_qoq_pct": round(data.revenue_qoq * 100, 1),
        "blended_roi": round(data.blended_roi, 2),
        "blended_cac": round(data.blended_cac, 0),
        "won_deals": data.won_deals,
        "model_agreement": round(data.model_agreement, 3),
        "top_roi": [(r.program_category, round(r.roi, 2)) for r in ranked[:3]],
        "bottom_roi": [(r.program_category, round(r.roi, 2)) for r in ranked[-3:]],
    }


def generate_observations(data: BoardPackData, claude: ClaudeClient) -> list[str]:
    facts = _facts(data)
    try:
        text = claude.complete(
            _SYSTEM,
            "Write the observations for this data. Return one bullet per line, "
            "starting with '- '.\n\n" + json.dumps(facts, indent=2),
            max_tokens=600,
        )
        bullets = [line.lstrip("- ").strip() for line in text.splitlines()
                   if line.strip().startswith("-")]
        if bullets:
            return bullets
    except BedrockUnavailable:
        pass
    return _fallback(data, facts)


def _fallback(data: BoardPackData, facts: dict) -> list[str]:
    agree = facts["model_agreement"]
    agree_note = ("the three attribution models broadly agree on channel ranking"
                  if agree >= 0.8 else
                  "the attribution models disagree materially on channel ranking, "
                  "so model choice changes the budget answer")
    bullets = [
        f"Attributed revenue was ${data.total_attributed:,.0f} in {data.fiscal_period}, "
        f"{facts['revenue_qoq_pct']:+.1f}% versus the prior quarter, across {data.won_deals} closed-won deals.",
        f"Blended marketing ROI was {facts['blended_roi']:.2f}x at a blended CAC of "
        f"${facts['blended_cac']:,.0f} per new customer.",
    ]
    # Channel ROI ranking is only meaningful once spend and closed-won revenue
    # have both landed; skip it on sparse data rather than indexing an empty list.
    top_roi, bottom_roi = facts["top_roi"], facts["bottom_roi"]
    if top_roi and bottom_roi:
        top, bottom = top_roi[0], bottom_roi[-1]
        bullets.append(f"{top[0]} led ROI at {top[1]:.2f}x; {bottom[0]} was lowest at {bottom[1]:.2f}x.")
    else:
        bullets.append("Channel-level ROI is not yet available — spend and/or "
                       "closed-won revenue have not populated the materialized views.")
    bullets.append(f"Model-agreement coefficient is {agree:.2f} — {agree_note}.")
    return bullets
