from attribution_agent.config import GuardrailConfig
from attribution_agent.agent.guardrails import Guardrails


def _g():
    return Guardrails(GuardrailConfig())


def test_excluded_channels_blocked():
    g = _g()
    eligible, reasons = g.is_channel_eligible("Brand", trailing_conversions=500)
    assert not eligible and reasons


def test_thin_channel_blocked():
    g = _g()
    # Below the min trailing-deals gate (default 3) -> too thin to act on.
    eligible, _ = g.is_channel_eligible("Paid Search", trailing_conversions=2)
    assert not eligible


def test_delta_clamped_to_cap():
    g = _g()
    d = g.apply("Paid Social", current_spend=500_000, requested_delta=-500_000,
                trailing_conversions=800)
    assert d.applied_delta == -100_000  # 20% of 500k
    assert d.clamped and d.allowed


def test_excluded_channel_yields_zero_delta():
    g = _g()
    d = g.apply("Events", current_spend=360_000, requested_delta=-100_000,
                trailing_conversions=900)
    assert d.excluded and d.applied_delta == 0 and not d.allowed
