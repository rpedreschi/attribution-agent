"""Publish generated events to Kafka, or to JSONL files in dry-run mode.

Kafka keys are chosen so related records land on the same partition and keep
ordering: changelog records key on their primary id; touch/spend events key on
the account/campaign. Salesforce CDC objects use a stable key so DeltaStream
changelog upserts collapse correctly.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..config import Settings
from .schemas import Event

# How to derive a partition key per topic_key.
_KEY_FIELD = {
    "salesforce_accounts": "account_id",
    "salesforce_contacts": "contact_id",
    "salesforce_opportunities": "opportunity_id",
    "hubspot": "vid",
    "ga4": "user_id",
    "linkedin_ads": "campaign",
    "google_ads": "campaign",
    "outreach": "contact_id",
}


def _key_for(topic_key: str, payload: dict) -> str:
    field = _KEY_FIELD.get(topic_key, "")
    return str(payload.get(field, "") or topic_key)


class FilePublisher:
    """Writes one JSONL file per topic under <out_dir>. No Kafka required."""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._handles: dict[str, object] = {}
        self.counts: dict[str, int] = {}

    def publish(self, topic: str, key: str, payload: dict) -> None:
        fh = self._handles.get(topic)
        if fh is None:
            fh = (self.out_dir / f"{topic}.jsonl").open("w")
            self._handles[topic] = fh
        fh.write(json.dumps({"key": key, "value": payload}) + "\n")  # type: ignore[union-attr]
        self.counts[topic] = self.counts.get(topic, 0) + 1

    def close(self) -> None:
        for fh in self._handles.values():
            fh.close()  # type: ignore[union-attr]


class KafkaPublisher:
    """Wraps confluent_kafka.Producer. Imported lazily so dry-run needs no broker."""

    def __init__(self, settings: Settings) -> None:
        from confluent_kafka import Producer  # lazy import

        conf: dict[str, object] = {
            "bootstrap.servers": settings.kafka.bootstrap_servers,
            "security.protocol": settings.kafka.security_protocol,
        }
        if settings.kafka.sasl_mechanism:
            conf.update({
                "sasl.mechanism": settings.kafka.sasl_mechanism,
                "sasl.username": settings.kafka.sasl_username,
                "sasl.password": settings.kafka.sasl_password,
            })
        self._producer = Producer(conf)
        self.counts: dict[str, int] = {}

    def publish(self, topic: str, key: str, payload: dict) -> None:
        self._producer.produce(topic, key=key.encode(), value=json.dumps(payload).encode())
        self.counts[topic] = self.counts.get(topic, 0) + 1
        self._producer.poll(0)

    def close(self) -> None:
        self._producer.flush(30)


def create_topics(settings: Settings, *, partitions: int = 6, replication: int = 3) -> None:
    """Create the source topics on Confluent Cloud (auto-create is usually off).
    Confluent Basic/Standard clusters require replication factor 3."""
    from confluent_kafka.admin import AdminClient, NewTopic  # lazy import

    conf: dict[str, object] = {
        "bootstrap.servers": settings.kafka.bootstrap_servers,
        "security.protocol": settings.kafka.security_protocol,
    }
    if settings.kafka.sasl_mechanism:
        conf.update({
            "sasl.mechanism": settings.kafka.sasl_mechanism,
            "sasl.username": settings.kafka.sasl_username,
            "sasl.password": settings.kafka.sasl_password,
        })
    admin = AdminClient(conf)
    topics = [NewTopic(t, num_partitions=partitions, replication_factor=replication)
              for t in settings.kafka.topics.values()]
    for topic, fut in admin.create_topics(topics).items():
        try:
            fut.result()
            print(f"  created topic {topic}")
        except Exception as exc:  # noqa: BLE001 - already-exists is fine
            print(f"  topic {topic}: {exc}")


def publish_all(events: Iterable[Event], settings: Settings, *, dry_run: bool,
                out_dir: Path | None = None) -> dict[str, int]:
    """Route each event to its topic and publish. Returns per-topic counts."""
    topics = settings.kafka.topics
    publisher = (
        FilePublisher(out_dir or Path("events"))
        if dry_run else KafkaPublisher(settings)
    )
    try:
        for topic_key, payload in events:
            topic = topics.get(topic_key, topic_key)
            publisher.publish(topic, _key_for(topic_key, payload), payload)
    finally:
        publisher.close()
    return publisher.counts
