"""CLI: generate Acme Cloud source events and publish them.

    # Dry run — write JSONL files under ./events, no broker needed:
    python -m attribution_agent.mock_generator --dry-run

    # Publish to the Kafka cluster in config/settings.yaml:
    python -m attribution_agent.mock_generator
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ..config import load_settings
from .generator import SEED, Generator
from .kafka_publisher import create_topics, publish_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Acme Cloud source events.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Write JSONL files instead of producing to Kafka.")
    parser.add_argument("--out-dir", default="events",
                        help="Directory for --dry-run JSONL output (default: events).")
    parser.add_argument("--create-topics", action="store_true",
                        help="Create the Confluent Cloud topics before publishing.")
    parser.add_argument("--seed", type=int, default=SEED,
                        help=f"RNG seed for reproducibility (default: {SEED}).")
    args = parser.parse_args()

    settings = load_settings()
    if args.create_topics and not args.dry_run:
        print("Creating topics…")
        create_topics(settings)

    events = Generator(seed=args.seed).generate()
    counts = publish_all(events, settings, dry_run=args.dry_run, out_dir=Path(args.out_dir))

    total = sum(counts.values())
    target = "files in " + args.out_dir if args.dry_run else "Kafka"
    print(f"Published {total:,} events to {target}:")
    for topic, n in sorted(counts.items()):
        print(f"  {topic:<32} {n:>8,}")


if __name__ == "__main__":
    main()
