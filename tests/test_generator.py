"""Datagen contract: payloads match the DeltaStream stream definitions.

The streams declare 'timestamp.format' = 'iso8601', so every TIMESTAMP field the
generator emits must be ISO-8601. This test guards that contract (a regression
here means DeltaStream ingestion would silently fail to parse event-time).
"""
from datetime import datetime

from attribution_agent.mock_generator.generator import Generator

ISO_FIELDS = {"event_time", "updated_at"}


def _events_by_topic():
    out: dict[str, list[dict]] = {}
    for topic_key, payload in Generator(seed=42).generate():
        out.setdefault(topic_key, []).append(payload)
    return out


def test_all_timestamps_are_iso8601():
    for _topic, payloads in _events_by_topic().items():
        for p in payloads:
            for field in ISO_FIELDS & p.keys():
                val = p[field]
                # DeltaStream TIMESTAMP (no zone) under iso8601 rejects a trailing
                # 'Z', so the contract is a zoneless ISO-8601 local datetime.
                assert not val.endswith("Z"), f"{field}={val!r} must not carry a zone suffix"
                datetime.fromisoformat(val)   # parses 2026-06-12T00:46:43.000


def test_deterministic_volumes_and_topics():
    by_topic = _events_by_topic()
    # All eight source topic keys are produced.
    assert set(by_topic) == {
        "ga4", "hubspot", "outreach", "linkedin_ads", "google_ads", "channel_cost",
        "salesforce_accounts", "salesforce_contacts", "salesforce_opportunities",
    }
    # Seeded => stable total across runs.
    assert sum(len(v) for v in by_topic.values()) == sum(
        len(v) for v in _events_by_topic().values())


def test_hubspot_form_carries_identity_bridge():
    forms = [p for p in _events_by_topic()["hubspot"] if p["event_type"] == "form_submission"]
    assert forms, "expected HubSpot form submissions (the anon->known bridge)"
    for f in forms:
        assert f["web_user_id"] and f["email"]   # both join keys present
