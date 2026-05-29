"""The recommendation agent.

Watches the attribution data, decides whether the dispersion in channel ROI is
material enough to act on, and — if so — proposes a reallocation: trim spend on
below-blended-ROI channels and redeploy the freed budget to the best performers
(net of any residual the ±20% caps prevent from being efficiently redeployed).
Every proposed move passes through the guardrails (file guardrails.py) before it
is emitted, and carries its rationale + the source figures it was derived from.

The math is deterministic and auditable; Claude is used only to phrase the
rationale. A human approves or rejects each move — no autonomous spend changes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .guardrails import GuardrailDecision, Guardrails
from .llm import BedrockUnavailable, ClaudeClient
from .reporting import BoardPackData

# Only act when the best eligible channel's ROI is at least this multiple of the
# worst eligible channel's ROI — otherwise the reallocation isn't worth the noise.
MATERIALITY_DISPERSION = 1.5


@dataclass
class Recommendation:
    channel: str
    action: str                 # "Increase" | "Decrease"
    current_spend: float
    delta: float                # applied (guardrailed) weekly $ change
    roi: float
    expected_revenue_impact: float
    rationale: str = ""
    source_refs: list[str] = field(default_factory=list)
    guardrail: GuardrailDecision | None = None

    @property
    def proposed_spend(self) -> float:
        return self.current_spend + self.delta


class RecommendationEngine:
    def __init__(self, guardrails: Guardrails, claude: ClaudeClient | None = None) -> None:
        self.guardrails = guardrails
        self.claude = claude

    def _trailing_conversions(self, data: BoardPackData) -> dict[str, int]:
        return {f.program_category: f.conversions_total for f in data.funnel}

    def propose(self, data: BoardPackData) -> list[Recommendation]:
        conversions = self._trailing_conversions(data)
        roi_by_channel = {r.program_category: r.roi for r in data.cac_roi if r.roi is not None}
        spend_by_channel = {r.program_category: r.spend for r in data.cac_roi}

        # Eligible = passes the per-channel guardrail gate.
        eligible = {
            ch: roi for ch, roi in roi_by_channel.items()
            if self.guardrails.is_channel_eligible(ch, conversions.get(ch, 0))[0]
        }
        if len(eligible) < 2:
            return []

        blended = data.blended_roi
        hi, lo = max(eligible.values()), min(eligible.values())
        if lo <= 0 or hi / lo < MATERIALITY_DISPERSION:
            return []  # not a material change — stay put

        # Trim below-blended channels (guardrail-capped); pool the freed budget.
        cuts: list[Recommendation] = []
        freed = 0.0
        for ch, roi in sorted(eligible.items(), key=lambda kv: kv[1]):
            if roi >= blended:
                continue
            decision = self.guardrails.apply(ch, spend_by_channel[ch],
                                             requested_delta=-spend_by_channel[ch],  # ask to cut hard; gets clamped to cap
                                             trailing_conversions=conversions.get(ch, 0))
            if decision.applied_delta < 0:
                freed += -decision.applied_delta
                cuts.append(self._mk(ch, "Decrease", spend_by_channel[ch], decision.applied_delta,
                                     roi, conversions[ch], decision))

        if not cuts or freed <= 0:
            return []

        # Redeploy the freed budget into above-blended channels, proportional to
        # ROI, each capped by the guardrail. The ±20% caps can leave part of the
        # freed budget unallocated (small high-ROI channels can't absorb it all);
        # that residual surfaces as net savings rather than being forced out.
        invest_targets = sorted(((ch, roi) for ch, roi in eligible.items() if roi >= blended),
                                key=lambda kv: kv[1], reverse=True)
        roi_sum = sum(roi for _, roi in invest_targets) or 1.0
        invests: list[Recommendation] = []
        for ch, roi in invest_targets:
            want = freed * (roi / roi_sum)
            decision = self.guardrails.apply(ch, spend_by_channel[ch], requested_delta=want,
                                             trailing_conversions=conversions.get(ch, 0))
            if decision.applied_delta > 0:
                invests.append(self._mk(ch, "Increase", spend_by_channel[ch], decision.applied_delta,
                                        roi, conversions[ch], decision))

        recs = cuts + invests
        self._attach_rationale(recs, data, blended)
        return recs

    def _mk(self, ch, action, spend, delta, roi, conv, decision) -> Recommendation:
        return Recommendation(
            channel=ch, action=action, current_spend=spend, delta=delta, roi=roi,
            expected_revenue_impact=delta * roi,
            source_refs=[
                f"cac_roi: {ch} spend ${spend:,.0f}, ROI {roi:.2f}x",
                f"funnel_metrics: {ch} {conv} conversions (trailing 90d)",
            ],
            guardrail=decision,
        )

    # ---- rationale (LLM with deterministic fallback) ----------------------

    def _attach_rationale(self, recs: list[Recommendation], data: BoardPackData, blended: float) -> None:
        if self.claude is not None:
            try:
                self._llm_rationale(recs, data, blended)
                return
            except BedrockUnavailable:
                pass
        for r in recs:
            verb = "below" if r.action == "Decrease" else "above"
            r.rationale = (
                f"{r.channel} ROI is {r.roi:.2f}x, {verb} the blended {blended:.2f}x. "
                f"{r.action} weekly spend by ${abs(r.delta):,.0f} "
                f"(to ${r.proposed_spend:,.0f}); estimated revenue impact "
                f"${r.expected_revenue_impact:+,.0f} at current efficiency.")
            if r.guardrail and r.guardrail.clamped:
                r.rationale += " Capped by the ±20% weekly reallocation guardrail."

    def _llm_rationale(self, recs: list[Recommendation], data: BoardPackData, blended: float) -> None:
        assert self.claude is not None
        payload = {
            "blended_roi": round(blended, 2),
            "moves": [{
                "channel": r.channel, "action": r.action,
                "current_spend": round(r.current_spend), "delta": round(r.delta),
                "roi": round(r.roi, 2),
                "expected_revenue_impact": round(r.expected_revenue_impact),
            } for r in recs],
        }
        system = (
            "You are a marketing-budget agent presenting reallocation moves to a CMO "
            "for approval. For each move, write one tight sentence of rationale that "
            "cites the channel ROI, the blended ROI, the dollar change, and the "
            "estimated revenue impact. Return a JSON array of strings, one per move, "
            "in the same order. No preamble.")
        text = self.claude.complete(system, json.dumps(payload, indent=2), max_tokens=800)
        rationales = json.loads(text)
        for r, sentence in zip(recs, rationales):
            r.rationale = str(sentence)
