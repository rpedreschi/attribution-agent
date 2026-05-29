"""Deterministic mock-data generator.

Produces JSON events shaped like the six source-system APIs and publishes them
to their Kafka topics (or to JSONL files in --dry-run mode). Seeded so a given
run is byte-for-byte reproducible.
"""
