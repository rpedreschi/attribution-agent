# Demo Script — DeltaStream Attribution Agent

**Audience:** B2B CMO (and whoever they bring — often a marketing-ops lead or a
data engineer; there's a section for each objection below).
**Length:** ~12 minutes + Q&A.
**Demo persona:** Acme Cloud, Series C SaaS — a CMO defending marketing spend to
the board every quarter.

**The one-sentence pitch:** *An AI agent can only be as smart as the freshness
of what it can see — DeltaStream is how you give an agent live context instead
of last night's snapshot.*

**What this demo is NOT:** a claim that revenue attribution itself is
"real-time." Closed-won lags your sales cycle no matter what pipeline you build.
We say that out loud (beat 5) — it's what makes the rest credible.

---

## 0. Setup (15 minutes before the call)

Three terminals + the agent, all started before anyone joins:

```bash
# Terminal 1 — clean rebuild so the numbers are coherent (see deltastream_deploy.md):
python scripts/terminate_queries.py --cli <dsql> --server <server-url>
python scripts/run_sql.py deltastream/teardown.sql --keep-going --cli <dsql> --server <server-url>
python scripts/run_sql.py deltastream/deploy_all.sql --cli <dsql> --server <server-url>

# Terminal 2 — the live event firehose. Backfill Q1, then KEEP STREAMING.
# Leave this visible: scrolling events are part of the show.
python -m attribution_agent.mock_generator --stream --backfill

# Terminal 3 — the agent, pinned to live MCP (no silent sample fallback):
python -m attribution_agent.agent.cli --source mcp
```

Pre-flight checks (do not skip):
- `agent> summary` shows non-zero revenue and spend.
- `agent> query spend_by_channel` returns rows for Paid Search *and* Paid Social.
- `LIST QUERIES;` in DeltaStream: 15 queries, all `running`.
- The stream in Terminal 2 has been up ≥5 minutes, so a few live journeys have
  already closed (`--stream` journeys go anonymous-touch → closed-won in ~3
  minutes — that's beat 4's payoff).

Write down two numbers from `summary`: **attributed revenue** and **won deals**.
You'll point at them growing later.

---

## 1. The pain (1 min) — say this, show nothing yet

> "Every quarter you present a marketing number to the board, and every quarter
> you half-defend it. The pipeline behind it is batch: the number was computed
> last night, from one attribution model, picked years ago. Between now and the
> board meeting, a campaign can break, spend can run hot, a tracking tag can die
> — and your reporting won't notice until the next batch run.
>
> And here's the new problem: you're about to put **AI agents** on top of that
> data. Everyone is. An agent answering questions from a stale snapshot isn't
> cautious — it's **confidently wrong**, in fluent English."

That last line is the thesis. Everything in the demo proves it.

---

## 2. Meet the agent (2 min) — Terminal 3

```
agent> summary
agent> channels
```

> "This is not a dashboard. It's an agent sitting on live marketing data —
> Salesforce, HubSpot, GA4, ad platforms — streaming through DeltaStream right
> now. Same revenue, three attribution models side by side: last-touch, linear,
> time-decay. They disagree — they always do — and that disagreement is the whole
> game: pick the wrong model and you cut the wrong channel."

Then the conversational beat:

```
agent> ask which channel has the best ROI and why?
```

> "I didn't click through a dashboard to get that. I asked. The answer is
> grounded in the live views — every figure traces to data, not to the model's
> imagination."

---

## 3. The part a warehouse can't do (2 min) — point at Terminal 2

Point at the events scrolling.

> "That terminal is the company's marketing exhaust, live: web sessions, form
> fills, SDR calls, opportunity stage changes, ad spend. DeltaStream is
> ingesting all of it, resolving anonymous web traffic to known accounts —
> cookie to email to account — and maintaining the aggregates the agent reads.
> Continuously. There is no nightly job in this architecture. There is no
> 'as of yesterday.'"

```
agent> tools
```

> "And this is the part I want your data team to notice: those are DeltaStream
> **materialized views, auto-exposed to the agent as tools over MCP** — the open
> protocol agents speak. Nobody built an API for this. The data team wrote SQL;
> the agent discovered it. That's the integration story: SQL in, agent-ready
> context out."

---

## 4. Watch it move (2 min) — the money beat

> "Stale data demos look exactly like live ones — until you wait sixty seconds.
> So let's wait."

Recall the revenue + won-deals numbers you wrote down. Talk through beat 5's
framing below while ~a minute passes, then:

```
agent> refresh
agent> summary
```

> "Revenue moved. Deal count moved. While we were talking, a buyer journey out
> there — anonymous web visit, demo request, SDR call, closed-won — completed,
> and every number the agent sees already includes it. Nobody ran a job. Ask
> your team what the lag is between a deal closing in Salesforce and your
> attribution reflecting it today. The honest answer is usually 'tomorrow,'
> and sometimes 'next sprint.'"

(If numbers didn't move: the stream closes a deal every ~2–3 minutes — fill
with beat 5 and refresh again. Never refresh silently; the waiting is the
point.)

---

## 5. The honest part (1.5 min) — preempt the objection before they raise it

Say this unprompted. It's the credibility move of the whole demo:

> "Now let me argue against myself, because you're going to think it on the
> drive home anyway: **revenue attribution can never be fully real-time** — a
> deal that closes today was earned by touches from the last ninety days. Your
> sales cycle is the speed limit, and no pipeline changes that.
>
> So why stream? Two reasons.
>
> **One: the leading indicators don't lag.** Spend pacing, lead velocity, funnel
> conversion, a tracking tag that silently dies — those move *hourly*, and
> catching them live is the difference between fixing a misfiring campaign
> today and explaining it in the QBR.
>
> **Two — the strategic one: agents.** The moment software *acts* on your data —
> answers your CFO's question, proposes a budget move, eventually executes one —
> freshness stops being a nice-to-have. A human analyst knows the dashboard is a
> day old and hedges. An agent doesn't hedge. It treats whatever it sees as now.
> Feed it yesterday, and you've automated being wrong."

---

## 6. The agent on a leash (2 min)

```
agent> recs
```

> "The agent proposes budget reallocations from the live numbers — and look at
> the guardrails: every move is **capped at 20% per week**, channels below a
> minimum conversion count are untouchable, Brand and Events are excluded by
> policy, and every line carries its rationale and source data."

```
agent> reject 1 not this quarter
```

> "And nothing moves without a human. Approve or reject, with a reason, logged.
> You've been burned by 'AI agent' overpromising — this one is deliberately on a
> leash, and the leash is configuration, not a slide."

```
agent> export
```

> "And because the board doesn't want a login: it ends as the spreadsheet you
> already forward to your CFO."

---

## 7. Close (1 min)

> "Here's the summary. The attribution math isn't the magic — your team could
> build these models in a warehouse. What they can't get from a warehouse is
> **an agent with live context**: streaming identity resolution, continuously
> maintained views, exposed to AI over MCP with zero API work. This demo — the
> full pipeline, sources to agent — was stood up in about a day on DeltaStream.
> The do-it-yourself version is Kafka plus Flink plus a serving database plus an
> API layer, measured in months, and your team operates it forever.
>
> You're going to put agents on your marketing data within a year. The only
> question is whether they see *now* or *yesterday*."

Ask for the next step (design-partner / pilot — whatever the motion is).

---

## Objection handling

**"Our deals take 6 months to close — real-time attribution is pointless."**
Agree immediately; it's beat 5. Revenue is the lagging output — the *inputs*
(spend, leads, funnel, anomalies) move hourly, and the agent needs live context
regardless of revenue lag. Never argue the lag; it's load-bearing for your
credibility.

**"We have Snowflake/BigQuery — why isn't this a dbt job?"** (the data engineer)
"For the quarterly deck, batch is fine — we'll say that in writing. Batch can't
do two things here: sub-minute operational signals, and serving an *agent* that
answers at any moment. A warehouse answers 'as of last run.' Also: your team
writes the same SQL here — streams instead of tables — and skips building the
agent API entirely, because MCP exposure is automatic."

**"Can't we build this on open-source Flink?"**
"Yes — DeltaStream *is* that engine, managed. The difference is this pipeline
was integration-tested in a day, versus owning Kafka + Flink + a serving DB +
an API layer. The streaming-SQL sharp edges are identical either way; the ops
burden isn't."

**"Is the AI deciding where my budget goes?"**
"No. It drafts; you approve; everything is capped, scoped, and logged. The
autonomy dial is yours, and v1 ships with it turned low on purpose."

**"Are these my real numbers?"**
"Demo data — a realistic B2B funnel with seeded randomness. The production
version is the same pipeline pointed at your CDC feeds; connectors are the real
implementation work and we'll scope that honestly."

---

## Fallback — no live infra on demo day

```bash
python -m attribution_agent.agent.cli --source sample
```

Runs the whole agent on the deterministic sample (canonical figures: $4.28M
attributed, 36 deals, model agreement 0.76). You lose beats 3–4 (the live
moment), so reframe: "this is the artifact; the live pipeline is what keeps it
honest" — and lean on beats 2, 5, 6. Do not pretend sample is live; if asked,
say it's the offline mode.
