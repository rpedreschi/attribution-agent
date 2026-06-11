# Demo Script — DeltaStream Attribution Agent

**Audience:** B2B CMO at a $50M–$250M company defending marketing spend to the
board. **Length:** ~10 minutes. **Customer:** Acme Cloud (Series C SaaS, $180M
revenue).

## 0. Setup (before the call)

```bash
pip install -e .
# Launch the interactive agent on the deterministic sample (no infra needed):
python -m attribution_agent.agent.cli --source sample
#   agent> summary      # land here to open
#   agent> export       # writes out/acme_cloud_attribution_2026-Q1.xlsx
```

Keep the xlsx open in a second window to flip to when you say "and here's the
board pack." Drive the live story from the REPL.

## 1. The pain (1 min)

"You present a marketing number to the board every quarter. Can you defend it?
Most attribution is batch — last night's snapshot, one model, no way to see the
full account journey. So the number is confidently wrong, and you feel it."

## 2. The artifact, not a dashboard (2 min)

Open the workbook. Land on **Executive Summary**:

- Attributed revenue **$4.28M**, **+9.5% QoQ**, across **36 deals**.
- Blended ROI **2.25x**, blended CAC **$52,778**.
- **Model agreement 0.76** — "the three models *disagree* on channel ranking.
  That disagreement is the whole game: pick the wrong model and you cut the
  wrong channel."

"This is a spreadsheet. It's the thing you already forward to the CFO. We're not
asking you to live in another dashboard."

## 3. Trust the numbers (2 min)

**Attribution by Channel** — last-touch / linear / time-decay side by side, each
summing to the same $4.28M. "Same revenue, three lenses. Last-touch over-credits
Paid Search; time-decay shows Outbound SDR and Email doing the real mid-funnel
work."

**Funnel Metrics** and **CAC and ROI** — "every number ties: funnel rolls up to
36 won, CAC math ties to the $1.9M spend. Nothing is hand-wavy."

## 4. The agent (3 min) — the actual point

In the REPL, `agent> recs`:

- "Paid Social ROI is 1.36x, below blended. The agent proposes trimming it
  **−$112K/week** — and note it's *capped at −20%*. It will not blow up your
  channel."
- "It redeploys into Email Nurture (12.8x) and Organic (10x), each also capped.
  Brand and Events? The agent won't touch them — excluded by policy."
- "Every line has a rationale and the source data it came from. And nothing
  moves until *you* approve it." Then do it live: `agent> reject 0 not this
  quarter` — "the human decides, and every decision is logged for the audit
  trail." Try `agent> ask which move has the best revenue-per-dollar?` to show
  grounded Q&A.

"This is real-time. When a campaign turns last week, the recommendation reflects
it today — not next month's batch."

## 5. Honest framing (1 min)

"Two of these three jobs — the reporting and the written commentary — are
scheduled LLM jobs. We're not going to tell you they're magic. The *agent* is
the budget-reallocation engine, and it's deliberately on a leash in v1. You've
been burned by 'AI agent' overpromising; we're not doing that."

## 6. Close (1 min)

"Bizible, but the numbers are real-time and you can trust the recommendation.
The wedge is exactly the board-defense pain you have right now. Want to be one
of three design partners?"

---

### Live-data variant

With Confluent Cloud + DeltaStream provisioned and the MVs exposed over MCP
(see README):

```bash
python -m attribution_agent.mock_generator --create-topics   # publish to Confluent
# (DeltaStream ingests, resolves identity, maintains the materialized views)
python -m attribution_agent.agent.cli                        # auto-connects via MCP
#   agent> tools     # shows the live MVs exposed as MCP tools
#   agent> refresh   # re-pull live state mid-demo
```
