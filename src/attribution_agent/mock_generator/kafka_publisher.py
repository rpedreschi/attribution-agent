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
    "channel_cost": "channel",
    "share_of_model": "buyer_query",
}


def _key_for(topic_key: str, payload: dict) -> str:
    field = _KEY_FIELD.get(topic_key, "")
    return str(payload.get(field, "") or topic_key)


class FilePublisher:
    """Writes one JSONL file per topic under <out_dir>. No Kafka required.

    `mode` is the file open mode: "w" (truncate, for a one-shot batch) or "a"
    (append, so a streaming run does not clobber a preceding backfill)."""

    def __init__(self, out_dir: Path, mode: str = "w") -> None:
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._mode = mode
        self._handles: dict[str, object] = {}
        self.counts: dict[str, int] = {}

    def publish(self, topic: str, key: str, payload: dict) -> None:
        fh = self._handles.get(topic)
        if fh is None:
            fh = (self.out_dir / f"{topic}.jsonl").open(self._mode)
            self._handles[topic] = fh
        fh.write(json.dumps({"key": key, "value": payload}) + "\n")  # type: ignore[union-attr]
        self.counts[topic] = self.counts.get(topic, 0) + 1

    def flush(self, timeout: float = 0) -> None:
        for fh in self._handles.values():
            fh.flush()  # type: ignore[union-attr]

    def close(self) -> None:
        for fh in self._handles.values():
            fh.close()  # type: ignore[union-attr]


def _kafka_conf(settings: Settings) -> dict[str, object]:
    """librdkafka connection config shared by the producer and admin client."""
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
    if settings.kafka.ssl_ca_location:            # custom broker CA (e.g. WarpStream)
        conf["ssl.ca.location"] = settings.kafka.ssl_ca_location
    return conf


class KafkaPublisher:
    """Wraps confluent_kafka.Producer. Imported lazily so dry-run needs no broker."""

    def __init__(self, settings: Settings) -> None:
        from confluent_kafka import Producer  # lazy import

        self._producer = Producer(_kafka_conf(settings))
        self.counts: dict[str, int] = {}

    def publish(self, topic: str, key: str, payload: dict) -> None:
        self._producer.produce(topic, key=key.encode(), value=json.dumps(payload).encode())
        self.counts[topic] = self.counts.get(topic, 0) + 1
        self._producer.poll(0)

    def flush(self, timeout: float = 0) -> None:
        # Serve delivery callbacks; with timeout>0 block for outstanding acks.
        self._producer.flush(timeout) if timeout else self._producer.poll(0)

    def close(self) -> None:
        self._producer.flush(30)


def _admin_client(settings: Settings):
    """Build a confluent_kafka AdminClient from settings (lazy import)."""
    from confluent_kafka.admin import AdminClient  # lazy import

    return AdminClient(_kafka_conf(settings))


def create_topics(settings: Settings, *, partitions: int = 6, replication: int = 3) -> None:
    """Create the source topics on Confluent Cloud (auto-create is usually off).
    Confluent Basic/Standard clusters require replication factor 3."""
    from confluent_kafka.admin import NewTopic  # lazy import

    admin = _admin_client(settings)
    topics = [NewTopic(t, num_partitions=partitions, replication_factor=replication)
              for t in settings.kafka.topics.values()]
    for topic, fut in admin.create_topics(topics).items():
        try:
            fut.result()
            print(f"  created topic {topic}")
        except Exception as exc:  # noqa: BLE001 - already-exists is fine
            print(f"  topic {topic}: {exc}")


def delete_topics(settings: Settings) -> None:
    """Delete the source topics (and all their data) from Confluent Cloud."""
    admin = _admin_client(settings)
    names = list(settings.kafka.topics.values())
    for topic, fut in admin.delete_topics(names, operation_timeout=30).items():
        try:
            fut.result()
            print(f"  deleted topic {topic}")
        except Exception as exc:  # noqa: BLE001 - not-found is fine
            print(f"  topic {topic}: {exc}")


def recreate_topics(settings: Settings, *, partitions: int = 6, replication: int = 3,
                    poll_seconds: float = 3.0, max_polls: int = 20) -> None:
    """Delete then recreate the source topics for a clean slate. Confluent Cloud
    deletes asynchronously, so wait for the names to disappear before creating
    (a create racing an in-flight delete fails)."""
    import time

    print("Deleting topics…")
    delete_topics(settings)
    names = set(settings.kafka.topics.values())
    print("Waiting for deletion to propagate…")
    for _ in range(max_polls):
        time.sleep(poll_seconds)
        existing = set(_admin_client(settings).list_topics(timeout=10).topics)
        if not (names & existing):
            break
    else:
        print("  warning: some topics still present; attempting create anyway")
    print("Creating topics…")
    create_topics(settings, partitions=partitions, replication=replication)


def make_publisher(settings: Settings, *, dry_run: bool,
                   out_dir: Path | None = None, mode: str = "w"):
    """Construct the right publisher for the run (file in dry-run, else Kafka)."""
    if dry_run:
        return FilePublisher(out_dir or Path("events"), mode=mode)
    return KafkaPublisher(settings)


def publish_event(publisher, topics: dict, topic_key: str, payload: dict) -> None:
    """Route one event to its topic and publish it on the given publisher."""
    topic = topics.get(topic_key, topic_key)
    publisher.publish(topic, _key_for(topic_key, payload), payload)


def publish_all(events: Iterable[Event], settings: Settings, *, dry_run: bool,
                out_dir: Path | None = None) -> dict[str, int]:
    """Route each event to its topic and publish. Returns per-topic counts."""
    topics = settings.kafka.topics
    publisher = make_publisher(settings, dry_run=dry_run, out_dir=out_dir)
    try:
        for topic_key, payload in events:
            publish_event(publisher, topics, topic_key, payload)
    finally:
        publisher.close()
    return publisher.counts
