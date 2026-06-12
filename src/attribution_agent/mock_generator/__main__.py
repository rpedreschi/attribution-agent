"""CLI: generate Acme Cloud source events and publish them.

    # Dry run — write JSONL files under ./events, no broker needed:
    python -m attribution_agent.mock_generator --dry-run

    # Publish the fixed Q1 backfill to the Kafka cluster in config/settings.yaml:
    python -m attribution_agent.mock_generator

    # Stream live events forever (fresh wall-clock timestamps) so DeltaStream
    # keeps recomputing attribution — Ctrl-C to stop:
    python -m attribution_agent.mock_generator --stream

    # Backfill Q1 first, then keep the stream running on top of it:
    python -m attribution_agent.mock_generator --stream --backfill
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

from ..config import load_settings
from .generator import SEED, Generator
from .kafka_publisher import (create_topics, make_publisher, publish_all,
                              publish_event, recreate_topics)
from .live_generator import LiveGenerator


def _run_batch(settings, args) -> None:
    events = Generator(seed=args.seed).generate()
    counts = publish_all(events, settings, dry_run=args.dry_run, out_dir=Path(args.out_dir))
    total = sum(counts.values())
    target = "files in " + args.out_dir if args.dry_run else "Kafka"
    print(f"Published {total:,} events to {target}:")
    for topic, n in sorted(counts.items()):
        print(f"  {topic:<32} {n:>8,}")


def _run_stream(settings, args) -> None:
    topics = settings.kafka.topics
    # Stream appends so it never clobbers a --backfill written to the same dir.
    publisher = make_publisher(settings, dry_run=args.dry_run,
                               out_dir=Path(args.out_dir), mode="a")
    gen = LiveGenerator(seed=args.seed, journey_seconds=args.journey_seconds,
                        new_journey_rate=args.new_journey_rate,
                        ambient_per_tick=args.ambient_per_tick)
    target = "files in " + args.out_dir if args.dry_run else "Kafka"
    print(f"Streaming live events to {target} every {args.interval}s "
          f"(Ctrl-C to stop)…")
    total = 0
    start = time.time()
    try:
        while True:
            now = datetime.utcnow()
            n = 0
            for topic_key, payload in gen.tick(now):
                publish_event(publisher, topics, topic_key, payload)
                total += 1
                n += 1
            publisher.flush(0)
            if n:
                elapsed = int(time.time() - start)
                print(f"  t+{elapsed:>4}s  +{n:<3} events  (total {total:,}, "
                      f"{gen.inflight} journeys in flight)")
            if args.max_events and total >= args.max_events:
                break
            if args.duration and time.time() - start >= args.duration:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        publisher.close()
    print(f"Published {total:,} live events to {target}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Acme Cloud source events.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Write JSONL files instead of producing to Kafka.")
    parser.add_argument("--out-dir", default="events",
                        help="Directory for --dry-run JSONL output (default: events).")
    parser.add_argument("--create-topics", action="store_true",
                        help="Create the Confluent Cloud topics before publishing.")
    parser.add_argument("--recreate-topics", action="store_true",
                        help="Delete the topics (clearing all data) and recreate "
                             "them before publishing — a clean slate.")
    parser.add_argument("--seed", type=int, default=SEED,
                        help=f"RNG seed for reproducibility (default: {SEED}).")

    parser.add_argument("--stream", action="store_true",
                        help="Continuously emit live events with current timestamps "
                             "(runs until Ctrl-C) instead of the one-shot backfill.")
    parser.add_argument("--backfill", action="store_true",
                        help="With --stream: publish the fixed Q1 backfill first, "
                             "then start streaming on top of it.")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="Seconds between stream ticks (default: 2.0).")
    parser.add_argument("--journey-seconds", type=float, default=180.0,
                        help="Wall-clock span of a full anon->close journey "
                             "(default: 180).")
    parser.add_argument("--new-journey-rate", type=float, default=0.15,
                        help="Probability a new journey starts each tick "
                             "(default: 0.15 — gentle drift; raise for a busier stream).")
    parser.add_argument("--ambient-per-tick", type=int, default=2,
                        help="Anonymous background touches per tick (default: 2).")
    parser.add_argument("--max-events", type=int, default=0,
                        help="Stop streaming after this many events (0 = unlimited).")
    parser.add_argument("--duration", type=float, default=0.0,
                        help="Stop streaming after this many seconds (0 = unlimited).")
    args = parser.parse_args()

    settings = load_settings()
    if args.recreate_topics and not args.dry_run:
        recreate_topics(settings)
    elif args.create_topics and not args.dry_run:
        print("Creating topics…")
        create_topics(settings)

    if args.stream:
        if args.backfill:
            _run_batch(settings, args)
        _run_stream(settings, args)
    else:
        _run_batch(settings, args)


if __name__ == "__main__":
    main()
