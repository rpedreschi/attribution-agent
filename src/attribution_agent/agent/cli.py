"""Interactive CLI agent.

Launch it, and it pulls the live attribution context from DeltaStream's MCP
endpoint (falling back to the deterministic sample when no token is configured),
runs the observation + recommendation jobs, and drops you into a REPL where you
can explore the numbers, approve/reject the agent's budget moves (human-in-the-
loop), ask grounded questions, and export the board pack to xlsx on demand.

    python -m attribution_agent.agent.cli            # auto: MCP if configured
    python -m attribution_agent.agent.cli --source sample
    python -m attribution_agent.agent.cli doctor     # connectivity diagnostic
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings, load_settings
from .deltastream_mcp import DeltaStreamMCPClient, DeltaStreamMCPError
from .guardrails import Guardrails
from .llm import ClaudeClient, LLMUnavailable
from .observations import generate_observations
from .recommendations import RecommendationEngine
from .reporting import BoardPackData

BANNER = "DeltaStream Attribution Agent"


def _money(v: float) -> str:
    return f"${v:,.0f}"


def _table(headers: list[str], rows: list[list[str]], aligns: list[str] | None = None) -> str:
    cols = list(zip(*([headers] + rows))) if rows else [[h] for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]
    aligns = aligns or ["<"] * len(headers)
    def fmt(cells: list[str]) -> str:
        return "  ".join(f"{str(c):{a}{w}}" for c, w, a in zip(cells, widths, aligns))
    line = "  ".join("-" * w for w in widths)
    return "\n".join([fmt(headers), line, *(fmt(r) for r in rows)])


class AgentCLI:
    def __init__(self, settings: Settings, source: str) -> None:
        self.settings = settings
        self.source = source
        self.mcp: DeltaStreamMCPClient | None = None
        self.claude = ClaudeClient(settings.agent)
        self.data: BoardPackData = self._load()
        self.decisions: list[dict] = []
        self.decisions_path = Path(settings.output.directory) / "decisions.jsonl"

    # -- data ---------------------------------------------------------------

    def _resolve_source(self) -> str:
        if self.source != "auto":
            return self.source
        if self.settings.deltastream.api_token:
            client = DeltaStreamMCPClient(self.settings.deltastream)
            if client.available:
                self.mcp = client
                return "mcp"
        return "sample"

    def _load(self) -> BoardPackData:
        resolved = self._resolve_source()
        if resolved == "mcp":
            self.mcp = self.mcp or DeltaStreamMCPClient(self.settings.deltastream)
            data = BoardPackData.from_mcp(
                self.mcp, self.settings.customer.display_name,
                self.settings.customer.fiscal_period)
            self._active = "DeltaStream MCP (live)"
        else:
            data = BoardPackData.from_sample()
            self._active = "deterministic sample"
        data.observations = generate_observations(data, self.claude)
        engine = RecommendationEngine(Guardrails(self.settings.agent.guardrails), self.claude)
        data.recommendations = engine.propose(data)
        return data

    # -- rendering ----------------------------------------------------------

    def cmd_summary(self, _: str) -> None:
        d = self.data
        print(f"\n{d.customer_name} — {d.fiscal_period}   (source: {self._active})")
        print(_table(
            ["KPI", "Value", "Context"],
            [["Attributed revenue", _money(d.total_attributed), f"{d.revenue_qoq:+.1%} QoQ"],
             ["Blended ROI", f"{d.blended_roi:.2f}x", f"spend {_money(d.total_spend)}"],
             ["Blended CAC", _money(d.blended_cac), f"{d.won_deals} new customers"],
             ["Model agreement", f"{d.model_agreement:.2f}", "1.00 = models agree"]],
            aligns=["<", ">", "<"]))
        print("\nObservations:")
        for o in d.observations:
            print(f"  • {o}")

    def cmd_channels(self, _: str) -> None:
        d = self.data
        tl = sum(c.last_touch for c in d.channels) or 1
        tn = sum(c.linear for c in d.channels) or 1
        td = sum(c.time_decay for c in d.channels) or 1
        rows = [[c.channel, _money(c.last_touch), _money(c.linear), _money(c.time_decay),
                 f"{c.time_decay/td:.1%}"]
                for c in sorted(d.channels, key=lambda c: c.time_decay, reverse=True)]
        rows.append(["Total", _money(tl), _money(tn), _money(td), "100.0%"])
        print("\n" + _table(["Channel", "Last Touch", "Linear", "Time Decay", "TD Share"],
                            rows, aligns=["<", ">", ">", ">", ">"]))

    def cmd_funnel(self, _: str) -> None:
        rows = [[f.program_category, f"{f.touches:,}", f"{f.conversations:,}", f"{f.mqls:,}",
                 f"{f.sqls:,}", f"{f.opps:,}", f"{f.won:,}", f"{f.rates()['won_per_opp']:.0%}"]
                for f in sorted(self.data.funnel, key=lambda f: f.won, reverse=True)]
        print("\n" + _table(["Program", "Touch", "Conv", "MQL", "SQL", "Opp", "Won", "Won/Opp"],
                            rows, aligns=["<", ">", ">", ">", ">", ">", ">", ">"]))

    def cmd_cac(self, _: str) -> None:
        rows = [[r.program_category, _money(r.spend), _money(r.attributed_revenue),
                 str(r.attributed_deals), _money(r.cac) if r.cac else "—",
                 f"{r.roi:.2f}x" if r.roi else "—",
                 f"{r.payback_months:.1f}" if r.payback_months else "—"]
                for r in self.data.ranked_by_roi()]
        print("\n" + _table(["Program", "Spend", "Attr. Rev", "Deals", "CAC", "ROI", "Payback"],
                            rows, aligns=["<", ">", ">", ">", ">", ">", ">"]))

    def cmd_recs(self, _: str) -> None:
        recs = self.data.recommendations
        if not recs:
            print("\nNo material change this period — no reallocation proposed.")
            return
        print("\nAgent recommendations (pending human approval):")
        for i, r in enumerate(recs):
            status = self._status_of(i)
            print(f"\n  [{i}] {r.action} {r.channel}  {_money(r.delta)}/wk "
                  f"→ {_money(r.proposed_spend)}   est. impact {_money(r.expected_revenue_impact)}   [{status}]")
            print(f"      {r.rationale}")
        print("\n  approve <n> / reject <n> [reason]   to act")

    # -- human-in-the-loop --------------------------------------------------

    def _status_of(self, idx: int) -> str:
        for d in reversed(self.decisions):
            if d["index"] == idx:
                return d["decision"].upper()
        return "pending"

    def _decide(self, arg: str, decision: str) -> None:
        parts = arg.split(maxsplit=1)
        if not parts or not parts[0].isdigit():
            print(f"usage: {decision} <recommendation number> [reason]")
            return
        idx = int(parts[0])
        if idx >= len(self.data.recommendations):
            print(f"no recommendation [{idx}]")
            return
        rec = self.data.recommendations[idx]
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "index": idx, "decision": decision, "channel": rec.channel,
            "action": rec.action, "delta": rec.delta,
            "reason": parts[1] if len(parts) > 1 else "",
            "source_refs": rec.source_refs,
        }
        self.decisions.append(entry)
        self.decisions_path.parent.mkdir(parents=True, exist_ok=True)
        with self.decisions_path.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")
        print(f"  {decision.upper()}: {rec.action} {rec.channel} {_money(rec.delta)}/wk "
              f"(logged to {self.decisions_path})")

    def cmd_approve(self, arg: str) -> None:
        self._decide(arg, "approve")

    def cmd_reject(self, arg: str) -> None:
        self._decide(arg, "reject")

    # -- agentic Q&A --------------------------------------------------------

    def cmd_ask(self, question: str) -> None:
        if not question.strip():
            print("usage: ask <question about the attribution data>")
            return
        context = self._facts_json()
        system = (
            "You are a marketing-attribution analyst answering a CMO's question. "
            "Answer ONLY from the provided JSON context. Be concise and cite the "
            "specific numbers. If the context does not contain the answer, say so.")
        try:
            answer = self.claude.complete(system, f"CONTEXT:\n{context}\n\nQUESTION: {question}",
                                          max_tokens=500)
            print("\n" + answer.strip())
        except LLMUnavailable:
            print("\n[LLM unavailable — set ANTHROPIC_API_KEY to enable Q&A. "
                  "Showing the data instead.]")
            self.cmd_summary("")

    def _facts_json(self) -> str:
        d = self.data
        return json.dumps({
            "customer": d.customer_name, "period": d.fiscal_period,
            "total_attributed_revenue": d.total_attributed,
            "blended_roi": round(d.blended_roi, 2), "blended_cac": round(d.blended_cac),
            "won_deals": d.won_deals, "model_agreement": round(d.model_agreement, 3),
            "channels": [{"channel": c.channel, "last_touch": c.last_touch,
                          "linear": c.linear, "time_decay": c.time_decay} for c in d.channels],
            "cac_roi": [{"program": r.program_category, "spend": r.spend,
                         "attributed_revenue": r.attributed_revenue, "deals": r.attributed_deals,
                         "roi": round(r.roi, 2) if r.roi else None} for r in d.cac_roi],
            "funnel": [{"program": f.program_category, "touches": f.touches, "won": f.won}
                       for f in d.funnel],
            "recommendations": [{"channel": r.channel, "action": r.action, "delta": r.delta,
                                 "rationale": r.rationale} for r in d.recommendations],
        }, indent=2)

    # -- infra --------------------------------------------------------------

    def cmd_tools(self, _: str) -> None:
        if not self.mcp:
            print("\nNot connected to DeltaStream MCP (running on sample data).")
            return
        try:
            tools = self.mcp.list_tools()
        except DeltaStreamMCPError as exc:
            print(f"\nMCP error: {exc}")
            return
        print("\nDeltaStream MCP tools (materialized views):")
        for t in tools:
            print(f"  • {t.get('name')} — {t.get('description', '')}")

    def cmd_query(self, arg: str) -> None:
        """Call one MV tool and print the parsed rows. Accepts a view key
        (e.g. spend_by_channel) or a raw MV/tool name."""
        if not self.mcp:
            print("\nNot connected to DeltaStream MCP (running on sample data).")
            return
        name = arg.strip()
        if not name:
            print("usage: query <view-key-or-tool>   (keys: "
                  + ", ".join(self.settings.deltastream.views) + ")")
            return
        try:
            tool = self.settings.deltastream.views.get(name, name)
            rows = self.mcp.call_tool(tool)
        except DeltaStreamMCPError as exc:
            print(f"\nMCP error: {exc}")
            return
        print(f"\n{tool}: {len(rows)} rows")
        for r in rows[:25]:
            print(f"  {r}")
        if len(rows) > 25:
            print(f"  … {len(rows) - 25} more")

    def cmd_raw(self, arg: str) -> None:
        """Dump the raw JSON-RPC result for a tool — use this to share the exact
        response shape during bring-up so the row parser can be pinned."""
        if not self.mcp:
            print("\nNot connected to DeltaStream MCP (running on sample data).")
            return
        name = arg.strip()
        if not name:
            print("usage: raw <view-key-or-tool>")
            return
        try:
            tool = self.settings.deltastream.views.get(name, name)
            result = self.mcp.call_tool_raw(tool)
        except DeltaStreamMCPError as exc:
            print(f"\nMCP error: {exc}")
            return
        print("\n" + json.dumps(result, indent=2, default=str)[:4000])

    def cmd_refresh(self, _: str) -> None:
        print("Refreshing from source…")
        self.data = self._load()
        print(f"Refreshed ({self._active}).")

    def cmd_export(self, arg: str) -> None:
        from ..spreadsheet.builder import build_workbook

        if arg.strip():
            out = Path(arg.strip())
        else:
            fname = self.settings.output.filename_template.format(
                customer_id=self.settings.customer.id,
                fiscal_period=self.settings.customer.fiscal_period)
            out = Path(self.settings.output.directory) / fname
        written = build_workbook(self.data, out)
        print(f"Board pack exported to {written}")

    def cmd_help(self, _: str) -> None:
        print(_help_text())

    # -- loop ---------------------------------------------------------------

    COMMANDS = {
        "summary": "cmd_summary", "kpis": "cmd_summary",
        "channels": "cmd_channels", "attribution": "cmd_channels",
        "funnel": "cmd_funnel",
        "cac": "cmd_cac", "roi": "cmd_cac",
        "recs": "cmd_recs", "recommendations": "cmd_recs",
        "approve": "cmd_approve", "reject": "cmd_reject",
        "ask": "cmd_ask", "tools": "cmd_tools", "query": "cmd_query",
        "raw": "cmd_raw", "refresh": "cmd_refresh",
        "export": "cmd_export", "help": "cmd_help",
    }

    def run(self) -> None:
        print(f"\n{BANNER}  ·  {self.data.customer_name} {self.data.fiscal_period}  ·  "
              f"source: {self._active}")
        self.cmd_summary("")
        self.cmd_recs("")
        print("\nType a command (help for the list, quit to exit).")
        while True:
            try:
                raw = input("\nagent> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not raw:
                continue
            verb, _, arg = raw.partition(" ")
            verb = verb.lower()
            if verb in ("quit", "exit", "q"):
                break
            method = self.COMMANDS.get(verb)
            if not method:
                print(f"unknown command '{verb}' (try: help)")
                continue
            getattr(self, method)(arg)


def _help_text() -> str:
    return (
        "Commands:\n"
        "  summary            top-line KPIs + agent observations\n"
        "  channels           attribution by channel (3 models)\n"
        "  funnel             funnel metrics by program\n"
        "  cac | roi          CAC / ROI / payback by program\n"
        "  recs               agent reallocation recommendations\n"
        "  approve <n> [why]  approve a recommendation (logged)\n"
        "  reject <n> [why]   reject a recommendation (logged)\n"
        "  ask <question>     grounded Q&A about the data\n"
        "  tools              list DeltaStream MCP tools (live mode)\n"
        "  query <view>       call one MV tool, print parsed rows (live mode)\n"
        "  raw <view>         dump one MV tool's raw JSON-RPC result (live mode)\n"
        "  refresh            re-pull from the source\n"
        "  export [path]      write the board pack xlsx\n"
        "  help | quit")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive DeltaStream attribution agent.")
    parser.add_argument("command", nargs="?", choices=["run", "doctor"], default="run",
                        help="run = interactive agent (default); doctor = connectivity check.")
    parser.add_argument("--source", choices=["auto", "mcp", "sample"], default="auto",
                        help="Data source (default: auto — MCP if a token is configured).")
    args = parser.parse_args()

    if args.command == "doctor":
        from .doctor import run_doctor

        raise SystemExit(run_doctor(load_settings()))
    AgentCLI(load_settings(), args.source).run()


if __name__ == "__main__":
    main()
