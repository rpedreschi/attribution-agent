# Demo Walkthrough — quick run sheet

The 5-minute live drive. (The full version with objection-handling is
`demo_script.md`; this is the cheat sheet you keep on a second screen.)

---

## Before the call (5 min)

```bash
# 1. data flowing — start the stream a few minutes early so deals have closed
python -m attribution_agent.mock_generator --stream --backfill

# 2. when the numbers look good in the agent, FREEZE them: Ctrl-C the stream
#    (a steady headline reads more credible than one ticking up mid-sentence)

# 3. launch the agent on the live pipeline
python -m attribution_agent.agent.cli --source mcp
```

Quick pre-flight at the `agent>` prompt: `summary` (non-zero revenue + spend),
`recs` (proposes a move). If `recs` is empty, the data's still thin — let the
stream run a bit longer. Then you're set.

---

## The walk (≈5 min)

**Open — say, don't type (15 sec)**
> "This is an AI agent sitting on our marketing data — Salesforce, HubSpot, GA4,
> ad platforms — streaming live through DeltaStream. Not a dashboard. Watch."

**1. `summary`**
> "Here's the quarter, live. Attributed revenue, blended ROI, CAC. And model
> agreement — these three attribution models only agree ~75% of the time, which
> is the whole problem: pick the wrong one and you cut the wrong channel."

**2. `channels`**
> "Same revenue, three lenses — last-touch, linear, time-decay. Last-touch
> over-credits the final ad click; time-decay shows Email and SDR doing the real
> mid-funnel work. The disagreement is the point."

**3. `cac`**
> "Now bring in spend. Per-channel ROI. Paid Social is underwater — under a
> dollar back per dollar in. Email and Organic are printing at 13x. *That's* the
> insight you can't get from a batch report that's a day stale."

**4. `recs`**  ← the money beat
> "So the agent proposes a reallocation: trim Paid Social and Paid Search, move
> that budget to Email, Organic, SDR. Every move is **capped at 20% a week**,
> each line has its rationale and the numbers it came from — and nothing moves
> until I approve it. It drafts; I decide."

**5. `reject 0 not this quarter` then `approve 2`**
> "Human in the loop. I reject the Paid Social cut, approve the Email increase —
> both logged for the audit trail. No autonomous spend changes."

**6. `ask how would revenue change if I took the increases but skipped the cuts?`**
> "And I can just ask it, in plain English — grounded in the live numbers, not
> made up."

**7. `export`**
> "And it ends as the spreadsheet I already forward to the CFO. No new dashboard
> to live in."

**Close (15 sec)**
> "Built in a day on DeltaStream — the data team writes SQL, the agent gets live
> context over MCP automatically. The honest catch: revenue itself lags your
> sales cycle, no pipeline changes that. But the leading signals — spend, leads,
> a campaign breaking — move hourly, and the moment an *agent* acts on your data,
> it has to see *now*, not yesterday. That's the bet."

---

## If something's off mid-demo

| symptom | quick recovery |
|---|---|
| `recs` empty | data too thin — `refresh`, or it needs more stream time. Pivot to `cac` (the ROI spread still lands) |
| spend `$0` / no ROI | spend batch was missed — run `python -m attribution_agent.mock_generator` once, then `refresh` |
| can't reach DeltaStream | fall back: `python -m attribution_agent.agent.cli --source sample` (offline canonical figures; say it's the offline mode) |

## Don't show
- The **Funnel tab** of the export — mql/sql counts only populate for two
  channels (known cosmetic gap). Drive from `cac`/`recs`/`channels` instead.
