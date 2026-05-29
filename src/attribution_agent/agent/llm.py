"""Claude-via-Bedrock wrapper used by the observation and recommendation jobs.

Kept deliberately small: a single `complete()` that takes a system prompt and a
user message and returns text. boto3 is imported lazily, and if Bedrock is
unavailable (no credentials, offline demo) callers fall back to deterministic
templates so the pipeline always produces a board pack.
"""
from __future__ import annotations

import json

from ..config import AgentConfig


class BedrockUnavailable(RuntimeError):
    pass


class ClaudeClient:
    def __init__(self, cfg: AgentConfig) -> None:
        self.cfg = cfg
        self._client = None

    def _ensure(self) -> None:
        if self._client is not None:
            return
        try:
            import boto3  # lazy import

            self._client = boto3.client("bedrock-runtime", region_name=self.cfg.aws_region)
        except Exception as exc:  # noqa: BLE001 - any failure -> fallback
            raise BedrockUnavailable(str(exc)) from exc

    def complete(self, system: str, user: str, *, max_tokens: int = 1024,
                 temperature: float = 0.2) -> str:
        self._ensure()
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        try:
            resp = self._client.invoke_model(  # type: ignore[union-attr]
                modelId=self.cfg.bedrock_model_id, body=json.dumps(body))
            payload = json.loads(resp["body"].read())
            return "".join(block.get("text", "") for block in payload.get("content", []))
        except Exception as exc:  # noqa: BLE001
            raise BedrockUnavailable(str(exc)) from exc

    @property
    def available(self) -> bool:
        try:
            self._ensure()
            return True
        except BedrockUnavailable:
            return False
