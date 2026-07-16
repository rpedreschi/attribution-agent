"""CLI: generate Acme Cloud source events and publish them.

    # Dry run — write JSONL files under ./events, no broker needed:
    python -m attribution_agent.mock_generator --dry-run

    # Publish the fixed Q1 backfill to the Kafka cluster in config/settings.yaml:
    python -m attribution_agent.mock_generator

    # Stream live events forever (fresh wall-clock timestamps) so DeltaStream
    # keeps recomputing attribution — Ctrl-C to stop:
    python -m attribution_agent.mock_generator --stream

    # Stream with the Q1 backfill anchor (default) — or without it:
    python -m attribution_agent.mock_generator --stream
    python -m attribution_agent.mock_generator --stream --no-backfill
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
    events = Generator(seed=args.seed).generate(no_ambient=args.no_ambient)
    counts = publish_all(events, settings, dry_run=args.dry_run, out_dir=Path(args.out_dir))
    total = sum(counts.values())
    target = "files in " + args.out_dir if args.dry_run else "Kafka"
    print(f"Published {total:,} events to {target}:")
    for topic, n in sorted(counts.items()):
        print(f"  {topic:<32} {n:>8,}")


def _print_cues(gen, start) -> None:
    """Drain and print any director cues the generator queued this tick, framed
    so they stand out in the stream console during a live demo."""
    while gen.cues:
        cue = gen.cues.pop(0)
        bar = "━" * 72
        print(f"\n{bar}\n🎬  T+{int(time.time() - start)}s  {cue}\n{bar}\n")


def _run_stream(settings, args) -> None:
    import os

    topics = settings.kafka.topics
    # Stream appends so it never clobbers a --backfill written to the same dir.
    publisher = make_publisher(settings, dry_run=args.dry_run,
                               out_dir=Path(args.out_dir), mode="a")
    gen = LiveGenerator(seed=args.seed, journey_seconds=args.journey_seconds,
                        new_journey_rate=args.new_journey_rate,
                        ambient_per_tick=0 if args.no_ambient else args.ambient_per_tick,
                        max_journeys=args.max_journeys,
                        max_concurrent=args.max_concurrent,
                        scenario=args.scenario, slip_at=args.slip_at)
    target = "files in " + args.out_dir if args.dry_run else "Kafka"
    print(f"Streaming live events to {target} every {args.interval}s "
          f"(Ctrl-C to stop)…")
    if args.scenario:
        print(f"  scenario mode: story beats fire on a timer (AI-answer slip at "
              f"T+{int(gen.slip_at)}s).")
        if args.cue_file:
            print(f"  on-cue: `touch {args.cue_file}` from another terminal to fire "
                  f"the next beat immediately.")
    total = 0
    start = time.time()
    try:
        while True:
            now = datetime.utcnow()
            # On-cue trigger: a sentinel file fires the next story beat now.
            if args.cue_file and os.path.exists(args.cue_file):
                gen.fire_next_beat(now)
                try:
                    os.remove(args.cue_file)
                except OSError:
                    pass
            n = 0
            for topic_key, payload in gen.tick(now):
                publish_event(publisher, topics, topic_key, payload)
                total += 1
                n += 1
            publisher.flush(0)
            _print_cues(gen, start)
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
    parser.add_argument("--backfill", action=argparse.BooleanOptionalAction, default=True,
                        help="With --stream: publish the fixed Q1 backfill anchor "
                             "(36 deals across all channels) before streaming on top "
                             "of it. On by default so the board is never left with "
                             "only the thin live journeys; pass --no-backfill to "
                             "stream without the anchor.")
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
    parser.add_argument("--no-ambient", action="store_true",
                        help="Drop the anonymous GA4 noise (never resolves to an "
                             "account; ~97%% of the volume). Use on bandwidth-metered "
                             "brokers — cuts the backfill from ~52k events to ~1.7k.")
    parser.add_argument("--max-journeys", type=int, default=12,
                        help="Hard lifetime cap on new live journeys (default: 12; "
                             "0 = unlimited). Totals plateau once hit; in-flight "
                             "journeys still finish. Set 0 with --max-concurrent for a "
                             "continuous gentle climb instead of a plateau.")
    parser.add_argument("--max-concurrent", type=int, default=0,
                        help="Cap on journeys IN FLIGHT at once (0 = off). New journeys "
                             "keep spawning as old ones close, so revenue climbs gently "
                             "and continuously through the call instead of plateauing. "
                             "The closing rate is bounded, so demo-length totals stay sane.")
    parser.add_argument("--scenario", action="store_true",
                        help="Run the scripted demo story: warm-up deals so revenue "
                             "ticks live, then the AI-answer slip, with director cues "
                             "printed as each beat lands.")
    parser.add_argument("--slip-at", type=float, default=None,
                        help="Seconds into the stream when the AI-answer slip fires "
                             "in --scenario mode (default: 90).")
    parser.add_argument("--cue-file", default=None,
                        help="On-cue trigger: when this file appears it fires the next "
                             "story beat immediately, then removes it. `touch` it from "
                             "another terminal to drive beats by hand ('watch this').")
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
