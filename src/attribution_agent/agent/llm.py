"""Claude wrapper used by the observation, recommendation, and CLI jobs.

Two backends, selected by config.agent.llm_backend:
    "anthropic"  direct Anthropic API (the local interactive CLI default)
    "bedrock"    AWS Bedrock (AgentCore deployment)

Both expose a single `complete(system, user) -> text`. SDKs are imported lazily,
and if the backend is unreachable (no credentials, offline demo) callers catch
`LLMUnavailable` and fall back to deterministic templates so the pipeline always
produces output.
"""
from __future__ import annotations

import json

from ..config import AgentConfig


class LLMUnavailable(RuntimeError):
    pass


# Backwards-compatible alias (earlier modules import BedrockUnavailable).
BedrockUnavailable = LLMUnavailable


class ClaudeClient:
    def __init__(self, cfg: AgentConfig) -> None:
        self.cfg = cfg
        self._client = None

    def _ensure(self) -> None:
        if self._client is not None:
            return
        try:
            if self.cfg.llm_backend == "anthropic":
                import anthropic  # lazy import

                self._client = anthropic.Anthropic(api_key=self.cfg.anthropic_api_key or None)
            else:
                import boto3  # lazy import

                self._client = boto3.client("bedrock-runtime", region_name=self.cfg.aws_region)
        except Exception as exc:  # noqa: BLE001 - any failure -> fallback
            raise LLMUnavailable(str(exc)) from exc

    def complete(self, system: str, user: str, *, max_tokens: int = 1024,
                 temperature: float = 0.2) -> str:
        self._ensure()
        try:
            if self.cfg.llm_backend == "anthropic":
                resp = self._client.messages.create(  # type: ignore[union-attr]
                    model=self.cfg.anthropic_model_id, max_tokens=max_tokens,
                    temperature=temperature, system=system,
                    messages=[{"role": "user", "content": user}])
                return "".join(b.text for b in resp.content if b.type == "text")
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens, "temperature": temperature,
                "system": system, "messages": [{"role": "user", "content": user}],
            }
            resp = self._client.invoke_model(  # type: ignore[union-attr]
                modelId=self.cfg.bedrock_model_id, body=json.dumps(body))
            payload = json.loads(resp["body"].read())
            return "".join(block.get("text", "") for block in payload.get("content", []))
        except Exception as exc:  # noqa: BLE001
            raise LLMUnavailable(str(exc)) from exc

    @property
    def available(self) -> bool:
        try:
            self._ensure()
            return True
        except LLMUnavailable:
            return False
