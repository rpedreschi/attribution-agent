"""`doctor` — one diagnostic for the live bring-up.

Checks, in order, the four things that have to be true for the real demo:
    1. config loaded and which secrets are present
    2. Confluent Cloud reachable + how many source topics exist
    3. DeltaStream MCP handshake (tools/list) + which MVs are exposed
    4. the LLM backend is reachable

Every check degrades gracefully (missing driver, no token) and reports rather
than throwing, so this is safe to run at any stage of setup.
"""
from __future__ import annotations

from ..config import Settings, load_settings
from .deltastream_mcp import DeltaStreamMCPClient, DeltaStreamMCPError
from .llm import ClaudeClient

OK, WARN, FAIL = "✓", "!", "✗"


def _line(status: str, title: str, detail: str = "") -> None:
    print(f"  {status}  {title}" + (f"\n        {detail}" if detail else ""))


def _check_config(s: Settings) -> bool:
    have_kafka = bool(s.kafka.sasl_username and s.kafka.sasl_password)
    have_token = bool(s.deltastream.api_token)
    have_llm = bool(s.agent.anthropic_api_key) or s.agent.llm_backend == "bedrock"
    _line(OK, f"Config loaded — customer={s.customer.id}, period={s.customer.fiscal_period}")
    _line(OK if have_kafka else WARN,
          f"Confluent creds {'present' if have_kafka else 'missing'} "
          f"(bootstrap={s.kafka.bootstrap_servers})")
    _line(OK if have_token else WARN,
          f"DeltaStream API token {'present' if have_token else 'missing'} "
          f"(endpoint={s.deltastream.mcp_endpoint})")
    _line(OK if have_llm else WARN,
          f"LLM backend={s.agent.llm_backend}, key {'present' if have_llm else 'missing'}")
    return True


def _check_confluent(s: Settings) -> bool:
    try:
        from confluent_kafka.admin import AdminClient
    except ImportError:
        _line(WARN, "Confluent check skipped — confluent-kafka not installed")
        return True
    if not (s.kafka.sasl_username and s.kafka.sasl_password):
        _line(WARN, "Confluent check skipped — no credentials configured")
        return True
    conf: dict[str, object] = {
        "bootstrap.servers": s.kafka.bootstrap_servers,
        "security.protocol": s.kafka.security_protocol,
    }
    if s.kafka.sasl_mechanism:
        conf.update({"sasl.mechanism": s.kafka.sasl_mechanism,
                     "sasl.username": s.kafka.sasl_username,
                     "sasl.password": s.kafka.sasl_password})
    try:
        md = AdminClient(conf).list_topics(timeout=10)
    except Exception as exc:  # noqa: BLE001
        _line(FAIL, "Confluent unreachable", str(exc))
        return False
    want = set(s.kafka.topics.values())
    present = want & set(md.topics)
    missing = want - present
    status = OK if not missing else WARN
    detail = "" if not missing else "missing: " + ", ".join(sorted(missing)) + \
        "  (run: attribution-generate --create-topics)"
    _line(status, f"Confluent OK — {len(md.brokers)} brokers, "
                  f"{len(present)}/{len(want)} source topics present", detail)
    return True


def _check_mcp(s: Settings) -> bool:
    if not s.deltastream.api_token:
        _line(WARN, "DeltaStream MCP check skipped — no API token (sample mode only)")
        return True
    client = DeltaStreamMCPClient(s.deltastream)
    try:
        tools = client.list_tools()
    except DeltaStreamMCPError as exc:
        _line(FAIL, "DeltaStream MCP handshake failed", str(exc))
        return False
    names = [t.get("name", "?") for t in tools]
    want = set(s.deltastream.views.values())
    found = want & set(names)
    missing = want - found
    status = OK if not missing else WARN
    detail = "exposed: " + (", ".join(names) if names else "(none)")
    if missing:
        detail += "\n        missing MVs: " + ", ".join(sorted(missing))
    _line(status, f"DeltaStream MCP OK — {len(names)} tools, "
                  f"{len(found)}/{len(want)} expected MVs", detail)
    return True


def _check_llm(s: Settings) -> bool:
    claude = ClaudeClient(s.agent)
    if claude.available:
        _line(OK, f"LLM reachable ({s.agent.llm_backend})")
    else:
        _line(WARN, f"LLM unreachable ({s.agent.llm_backend}) — "
                    "observations/ask fall back to templates")
    return True


def run_doctor(settings: Settings | None = None) -> int:
    s = settings or load_settings()
    print("\nDeltaStream Attribution Agent — doctor\n")
    results = [
        _check_config(s),
        _check_confluent(s),
        _check_mcp(s),
        _check_llm(s),
    ]
    ok = all(results)
    print("\n" + ("All required checks passed." if ok
                  else "Some checks failed — see ✗ above.") + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(run_doctor())
