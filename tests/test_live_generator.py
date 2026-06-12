"""Live (streaming) datagen contract.

LiveGenerator must honour the same payload contract as the batch Generator
(ISO-8601 timestamps, the anon->known identity bridge) while stamping events at
the wall-clock ``now`` passed to each tick, and must drive at least one journey
all the way to ClosedWon so the materialized views have credit to assign.
"""
from datetime import datetime, timedelta

from attribution_agent.mock_generator.live_generator import LiveGenerator

ISO_FIELDS = {"event_time", "updated_at"}


def _drain(seconds: float = 600.0, step: float = 1.0, **kw):
    """Run a deterministic, fully in-memory stream: advance a fake clock in
    fixed steps so every scheduled journey event fires. Returns events grouped
    by topic key."""
    gen = LiveGenerator(seed=42, journey_seconds=120.0, new_journey_rate=0.8, **kw)
    base = datetime(2026, 6, 12, 9, 0, 0)
    out: dict[str, list[dict]] = {}
    t = 0.0
    while t <= seconds:
        for topic_key, payload in gen.tick(base + timedelta(seconds=t)):
            out.setdefault(topic_key, []).append(payload)
        t += step
    return out


def test_live_timestamps_are_iso8601_and_track_now():
    base = datetime(2026, 6, 12, 9, 0, 0)
    for topic_key, payload in LiveGenerator(seed=1).tick(base):
        for field in ISO_FIELDS & payload.keys():
            val = payload[field]
            assert val.endswith("Z"), f"{field}={val!r} not ISO-8601 Z"
            parsed = datetime.fromisoformat(val.replace("Z", "+00:00")).replace(tzinfo=None)
            # Events fire at or after the tick's now, within the journey span.
            assert base - timedelta(seconds=1) <= parsed <= base + timedelta(seconds=200)


def test_journey_reaches_closed_won():
    by_topic = _drain()
    stages = {p["stage_to"] for p in by_topic.get("salesforce_opportunities", [])}
    assert "ClosedWon" in stages, "no journey closed won — nothing to attribute"
    # A won account flips is_customer 0 -> 1.
    assert any(a["is_customer"] == 1 for a in by_topic["salesforce_accounts"])


def test_live_emits_identity_bridge_and_spend():
    by_topic = _drain(seconds=120.0)
    forms = [p for p in by_topic["hubspot"] if p["event_type"] == "form_submission"]
    assert forms, "expected form submissions (the anon->known bridge)"
    for f in forms:
        assert f["web_user_id"] and f["email"] and f["vid"]
    # Daily spend fires once per calendar day on each ad platform.
    assert by_topic.get("linkedin_ads") and by_topic.get("google_ads")


def test_deterministic_under_seed():
    assert _drain(seconds=30.0) == _drain(seconds=30.0)
