# Demo Script — DeltaStream Pulse

**Audience:** the B2B CMO — and, crucially, whoever they need to convince: the
**CFO and CRO**. Often they bring a marketing-ops lead or a data engineer too;
there's an objection section for each below. (Background and the buyer story:
`positioning.md`.)

**Length:** ~12 minutes + Q&A.
**Demo persona:** Acme Cloud, Series C SaaS — a CMO who re-defends marketing
spend to the board every quarter and wants to stop.

**Who you're really selling:** not the CMO alone — the CMO as **the one who
finally gets the CFO and CRO to believe the number.** The win is the moment all
three look at *one live source of truth*, drill into it together, and the budget
fight ends.

**The one-sentence pitch:** *DeltaStream Pulse turns your marketing data into
one live source of truth an AI agent can act on — so the number you bring to the
board is one the CFO and CRO already believe.*

**Two things the buyer says (lead with their words):**
- *"The data is old by the time you see it."* — batch reporting, one stale model.
- *"The tools tell you what happened, not what to do next."* — dashboards are
  analysis; the agent proposes the action.

**What this demo is NOT:** a claim that revenue attribution itself is
"real-time." Closed-won lags your sales cycle no matter what pipeline you build.
We say that out loud (beat 5) — naming the limit is what makes the rest
credible. This is a **trust problem first, a technology problem second**; the
tech earns the trust, it doesn't replace it.

---

## 0. Setup (15 minutes before the call)

Three terminals + the agent, all started before anyone joins:

Set the DeltaStream env once (Terminal 1 and 2):

```bash
export DSQL_BIN=../../dscliv2
export DS_SERVER=https://api-kd8j38.stage.deltastream-internal.name/v2
export DS_TOKEN=<your-deltastream-api-token>
```

Terminal 1 — clean rebuild + live firehose in one command (terminate, teardown,
deploy, then keep streaming). Leave it visible; scrolling events are the show:

```bash
bash scripts/demo_up.sh
```

Terminal 2 — the agent, pinned to live MCP (no silent sample fallback):

```bash
python -m attribution_agent.agent.cli --source mcp
```

Terminal 3 (optional) — the dashboard UI, live off the same pipeline:

```bash
python -m attribution_agent.api.board_view --source mcp --serve 8787
```
then open `ui/index.html?api=http://localhost:8787/board.json`.

(Teardown only, no rebuild: `bash scripts/demo_down.sh`.)

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
> you half-defend it. Not because the work is bad — because the number isn't
> *believed*. The CFO can't tie it to revenue. The CRO isn't sure the leads were
> good. So the budget is never safe; it's an annual fight you re-fight from zero.
>
> And the pipeline behind that number makes it worse: it's batch. The data is
> old by the time you see it, from one attribution model picked years ago.
> Between now and the board meeting a campaign can break, spend can run hot, a
> tracking tag can die — and your reporting won't notice until the next run. The
> tools tell you what *happened*, never what to do next.
>
> And here's the new problem: you're about to put **AI agents** on top of that
> data. Everyone is. An agent answering from a stale snapshot isn't cautious —
> it's **confidently wrong**, in fluent English. You can't take that to a board
> that's already skeptical."

The thesis: this is a **trust problem first.** The rest of the demo is about
getting the CFO and CRO to believe one number — and giving an agent context
honest enough to act on.

---

## 2. Meet the agent (2 min) — Terminal 3

```
agent> summary
agent> channels
```

> "This is not a dashboard — and that's deliberate. You've spent years buying
> dashboards nobody opens; the data team builds them and someone still has to pull
> the answer off them for you. This is an agent sitting on live marketing data —
> Salesforce, HubSpot, GA4, ad platforms — streaming through DeltaStream right
> now. Same revenue, three attribution models side by side: last-touch, linear,
> time-decay. They disagree — they always do — and that disagreement is the whole
> game: pick the wrong model and you cut the wrong channel."

(If a data/analytics veteran is in the room, this lands hard — the universal
truth is dashboard adoption is near zero and the CMO always needed a human to
extract the answer. The agent *is* that human, on call.)

Then the conversational beat:

```
agent> ask which channel has the best ROI and why?
```

> "I didn't click through a dashboard to get that. I asked, and I got a one-line
> answer — which is exactly what a board wants. And every figure traces back to a
> source view; nothing is the model's imagination.
>
> Picture this beat with your CFO and CRO in the room. This is **one source of
> truth, straight from your systems — Salesforce, HubSpot, the ad platforms.**
> When the CFO asks 'where does that number come from,' you don't promise to
> follow up after the meeting — you drill in, live, right there. That's the
> moment the questioning stops and the CRO starts defending the number *with*
> you, because it's their pipeline data too. Alignment isn't a meeting; it's all
> three of you looking at the same live data and trusting it."

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

## 6. The channel you can't buy — AI influence (2 min)

This is the beat nobody else can show. Start with the channel table:

```
agent> cac
```

> "Look at the top of that list. **AI Assistant** — 17x ROI, the best in your
> mix. These are deals where the buyer asked ChatGPT or Perplexity 'who's best
> for this,' got pointed at you, and showed up already sold. We catch it three
> ways: the assistant referral, a self-report on the form, and the journey. And
> here's the kicker — last-touch *hides* it, because the assistant nudge is
> invisible and the credit defaults to the direct visit that follows. Only the
> multi-touch view surfaces it."

Then the twist — what the agent does *not* do:

```
agent> recs
```

> "Notice the agent's footer: it flags AI Assistant as your highest-ROI channel
> and then refuses to fund it. Why? **There's no media buy.** You can't spend
> your way into an LLM's recommendation. A naive optimizer would dump budget
> here and accomplish nothing. This one knows the difference between a channel
> you can *buy* and a channel you can only *earn*."

So what *do* you do about it? You watch your standing in the answer:

```
agent> aishare
```

> "This is **share of model** — when an assistant answers a buyer's question,
> are you in the answer, are you cited, where do you rank. And watch this one:
> on *'cloud cost anomaly detection'* you've **slipped out of the answer** — from
> ranked-and-cited to absent. A model updated overnight and you fell off. No ad
> dashboard on earth shows you that. The agent caught it live, and that's the
> early warning for a channel that's quietly driving your best-fit deals."

The honest caveat (say it — it's the credibility move): "Nobody attributes LLM
influence to the dollar yet; it's zero-click and invisible. So we triangulate —
the referral we can see, the self-report, and share of model as the leading
indicator. Anyone claiming a clean deterministic 'ChatGPT sourced $X' is selling
you the tip and hiding the iceberg."

---

## 7. The agent on a leash (2 min)

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

## 8. Close (1 min) — make it about the budget

> "Let me land where this actually matters to you. The attribution math isn't the
> magic — your team could build these models in a warehouse. What a warehouse
> *can't* give you is what we just did: **one live source of truth your CFO and
> CRO will believe in the room**, and an agent that turns it into a defensible,
> one-line answer with a human on the approve button.
>
> And here's why that's worth doing. **Proven ROI protects the budget.** The day
> the CFO can drill into your number live and it holds, the budget stops being an
> annual fight — it becomes 'can I give you more?' That's the return on this. Not
> a nicer dashboard. A number that survives scrutiny, so your spend is safe.
>
> Think about how Amazon runs marketing: a multi-billion-dollar budget it shifts
> across platforms **hourly**, because it sees the signal live. You can't —
> your agencies report back monthly, barely, and the campaign that's burning
> money already burned it by the time you find out. This gives you that same
> reflex: see it now, move the budget today, not next quarter.
>
> And you adopt it the way you bought the rest of your stack — **as software your
> team turns on, not a data-engineering project.** It connects to the SaaS you
> already run; there's no six-month IT build in the middle. You're going to put
> agents on your marketing data within a year regardless. The only question is
> whether they see *now* or *yesterday* — and whether the number they produce is
> one the whole leadership team will stand behind."

Ask for the next step (design-partner / pilot — whatever the motion is).

**Reading the room — who's the buyer:**
- **VP of E-commerce** instead of a CMO? Same demo, same story — they live the
  budget-shifting pain across Amazon / Walmart / D2C / TikTok Shop.
- **RevOps / Demand Gen / MarTech** in the room? They feel the integration tax —
  lean on "SQL in, agent-ready context out, no custom connectors to own."
- **Keep it out of IT's lane.** This is bought as SaaS by the marketing org;
  routing it through data engineering is how a fast deal becomes a slow one. Only
  the SAP/Oracle-ERP shops need the VPC/IT path.

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

**"How do I know I can trust the number — that it's not AI making things up?"**
(the CFO/board question) "Because it isn't AI magic — it's verifiable. Every
figure traces to a live source view you can drill into, in the room. The agent
doesn't invent numbers; it reads the same streaming data your systems produce
and explains its reasoning. The trust comes from the single source of truth
underneath, not from believing the model. That's the whole point: defensible,
not impressive."

**"My CFO and CRO don't believe my numbers today — how does this change that?"**
"It puts all three of you on one live view you can interrogate together. The CFO
stops re-deriving their own number; the CRO sees it's their pipeline data too.
Alignment stops being a negotiation and becomes a shared scoreboard — and proven
ROI is what protects your budget."

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
attributed, 36 deals, model agreement 0.76). You lose beats 4 (the live revenue
move) and the *live* slip in beat 6, so reframe: "this is the artifact; the live
pipeline is what keeps it honest" — and lean on beats 2, 5, 6, 7. The AI-influence
beat (6) still mostly lands offline: `cac` shows AI Assistant at 17x, `recs`
shows the won't-fund footer, and `aishare` shows a query already slipped to "at
risk" — you just can't show it dropping in real time. Do not pretend sample is
live; if asked, say it's the offline mode.
