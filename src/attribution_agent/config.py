"""Configuration loading.

Resolution order, lowest to highest precedence:
    1. config/settings.example.yaml defaults that ship with the repo
    2. config/settings.yaml (gitignored, operator-supplied)
    3. matching UPPER_SNAKE environment variables

`${VAR}` references inside the YAML are expanded from the environment so that
secrets stay out of files.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_DIR = _REPO_ROOT / "config"
_ENV_REF = re.compile(r"\$\{([A-Z0-9_]+)\}")


class KafkaConfig(BaseModel):
    bootstrap_servers: str = "localhost:9092"
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: str | None = None
    sasl_username: str | None = None
    sasl_password: str | None = None
    topics: dict[str, str] = Field(default_factory=dict)


class DeltaStreamConfig(BaseModel):
    """DeltaStream MCP endpoint. Materialized views the API token's role can
    SELECT are exposed as MCP tools the agent discovers and calls."""
    # Org-specific REST endpoint; find yours via the DeltaStream REST API docs.
    mcp_endpoint: str = "https://api-kap822.deltastream.io/mcp/v1"
    api_token: str | None = None          # CREATE API_TOKEN; sent as Bearer
    organization: str | None = None
    role: str = "attribution_reader"
    database: str = "attribution"
    schema_name: str = "public"
    # MV names as exposed over MCP. DeltaStream names each tool fully-qualified
    # as <database>_<schema>_<mv> (e.g. attribution_public_mv_spend_by_channel),
    # so these must carry the attribution_public_ prefix to match the live tools.
    views: dict[str, str] = Field(default_factory=lambda: {
        "spend_by_channel": "attribution_public_mv_spend_by_channel",
        "funnel_by_category": "attribution_public_mv_funnel_by_category",
        "channel_touch_distribution": "attribution_public_mv_channel_touch_distribution",
        "won_revenue_by_account": "attribution_public_mv_won_revenue_by_account",
        "share_of_model": "attribution_public_mv_share_of_model",
    })


class GuardrailConfig(BaseModel):
    max_weekly_reallocation_pct: float = 0.20
    min_conversions_trailing_90d: int = 3   # min trailing won deals to act on a channel
    # Brand/Events: policy exclusion. AI Assistant: no media lever exists, so
    # there is nothing to reallocate — the agent watches share-of-model instead.
    excluded_channels: list[str] = Field(
        default_factory=lambda: ["Brand", "Events", "AI Assistant"])
    attribution_model_for_decisions: str = "time_decay"


class AgentConfig(BaseModel):
    # LLM backend: "bedrock" (AgentCore) or "anthropic" (direct API, for the
    # local interactive CLI). Both call Claude.
    llm_backend: str = "bedrock"
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-6-v1:0"
    anthropic_model_id: str = "claude-sonnet-4-6"
    anthropic_api_key: str | None = None
    agentcore_runtime_arn: str | None = None
    guardrails: GuardrailConfig = Field(default_factory=GuardrailConfig)


class CustomerConfig(BaseModel):
    id: str = "acme_cloud"
    display_name: str = "Acme Cloud"
    fiscal_period: str = "2026-Q1"


class OutputConfig(BaseModel):
    directory: str = "out"
    filename_template: str = "{customer_id}_attribution_{fiscal_period}.xlsx"


class Settings(BaseModel):
    customer: CustomerConfig = Field(default_factory=CustomerConfig)
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    deltastream: DeltaStreamConfig = Field(default_factory=DeltaStreamConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def _expand_env(value: Any) -> Any:
    """Recursively expand ${VAR} references using the environment."""
    if isinstance(value, str):
        return _ENV_REF.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, val in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_settings(config_dir: Path | None = None) -> Settings:
    """Load merged settings. Pass `config_dir` to override the default location."""
    cfg_dir = config_dir or _CONFIG_DIR
    merged = _deep_merge(
        _load_yaml(cfg_dir / "settings.example.yaml"),
        _load_yaml(cfg_dir / "settings.yaml"),
    )
    merged = _expand_env(merged)
    return Settings(**merged)
