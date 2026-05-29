"""DeltaStream Marketing Attribution Agent — Phase 0 demo package.

Subpackages:
    mock_generator  Deterministic source events -> Kafka topics.
    agent           ClickHouse-backed reporting, observations, and the
                    recommendation agent (AWS Bedrock AgentCore + Claude).
    spreadsheet     openpyxl six-sheet board pack (the CMO artifact).

`sample_data` holds the canonical, internally-consistent Acme Cloud figures
that drive the deterministic demo.
"""

__version__ = "0.1.0"
