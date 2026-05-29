"""Recommendation guardrails (v1).

These are hard constraints applied *after* the engine proposes a reallocation,
not suggestions to the LLM. A recommendation that violates a guardrail is
clamped or dropped, and every decision is recorded on the Recommendation for
the audit trail. v1 policy:

  * Agent recommends, human approves — no autonomous spend changes.
  * Reallocation capped at +/- max_weekly_reallocation_pct of current spend.
  * Channels with < min_conversions_trailing_90d conversions are excluded.
  * Brand and Events are excluded from agent autonomy entirely.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import GuardrailConfig


@dataclass
class GuardrailDecision:
    channel: str
    requested_delta: float
    applied_delta: float
    clamped: bool
    excluded: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return not self.excluded and self.applied_delta != 0


class Guardrails:
    def __init__(self, cfg: GuardrailConfig) -> None:
        self.cfg = cfg

    def is_channel_eligible(self, channel: str, trailing_conversions: int) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        eligible = True
        if channel in self.cfg.excluded_channels:
            eligible = False
            reasons.append(f"'{channel}' is excluded from agent autonomy (policy).")
        if trailing_conversions < self.cfg.min_conversions_trailing_90d:
            eligible = False
            reasons.append(
                f"{trailing_conversions} conversions in trailing 90d "
                f"< {self.cfg.min_conversions_trailing_90d} minimum (too thin to act on).")
        return eligible, reasons

    def apply(self, channel: str, current_spend: float, requested_delta: float,
              trailing_conversions: int) -> GuardrailDecision:
        """Clamp a requested spend delta to policy and record the rationale."""
        eligible, reasons = self.is_channel_eligible(channel, trailing_conversions)
        if not eligible:
            return GuardrailDecision(channel, requested_delta, 0.0, clamped=False,
                                     excluded=True, reasons=reasons)

        cap = current_spend * self.cfg.max_weekly_reallocation_pct
        applied = max(-cap, min(cap, requested_delta))
        clamped = abs(applied - requested_delta) > 1e-6
        if clamped:
            reasons.append(
                f"Requested {requested_delta:+,.0f} clamped to {applied:+,.0f} "
                f"(±{self.cfg.max_weekly_reallocation_pct:.0%} weekly cap on "
                f"${current_spend:,.0f} current spend).")
        return GuardrailDecision(channel, requested_delta, applied, clamped=clamped,
                                 excluded=False, reasons=reasons)
