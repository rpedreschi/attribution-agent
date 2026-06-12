"""One-off: delete legacy Kafka topics left over from earlier naming.

Earlier runs created source topics under the `src.` prefix and a few derived
topics under `attribution.` (dotted). Everything is now `attr_`-prefixed, so this
removes the stragglers. It deletes ONLY topics whose names start with a legacy
prefix and never touches `attr_*` topics.

Uses the same Confluent connection as the datagen (config + KAFKA_* env vars).

    python scripts/delete_legacy_topics.py             # list, then delete
    python scripts/delete_legacy_topics.py --dry-run   # just list, delete nothing
    python scripts/delete_legacy_topics.py --prefix foo. --prefix bar.   # custom
"""
from __future__ import annotations

import argparse

from attribution_agent.config import load_settings
from attribution_agent.mock_generator.kafka_publisher import _admin_client

LEGACY_PREFIXES = ("src.", "attribution.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete legacy (non-attr_) Kafka topics.")
    parser.add_argument("--dry-run", action="store_true",
                        help="List matching topics but delete nothing.")
    parser.add_argument("--prefix", action="append", dest="prefixes",
                        help="Override the legacy prefixes to match (repeatable).")
    args = parser.parse_args()
    prefixes = tuple(args.prefixes) if args.prefixes else LEGACY_PREFIXES

    settings = load_settings()
    admin = _admin_client(settings)
    existing = admin.list_topics(timeout=15).topics
    targets = sorted(t for t in existing if t.startswith(prefixes))

    if not targets:
        print(f"No legacy topics found (nothing starts with {', '.join(prefixes)}).")
        return

    print(f"Legacy topics to delete ({len(targets)}):")
    for t in targets:
        print(f"  {t}")

    if args.dry_run:
        print("\n--dry-run: nothing deleted.")
        return

    print("\nDeleting…")
    for topic, fut in admin.delete_topics(targets, operation_timeout=30).items():
        try:
            fut.result()
            print(f"  deleted {topic}")
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"  {topic}: {exc}")


if __name__ == "__main__":
    main()
