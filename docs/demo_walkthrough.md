# Demo Walkthrough — quick run sheet

The 5-minute live drive. (The full version with objection-handling is
`demo_script.md`; this is the cheat sheet you keep on a second screen.)

---

## Before the call (5 min)

```bash
# 1. data flowing — start the stream a few minutes early so deals have closed.
#    --max-journeys caps live deals so the headline stays believable (~$5-6M,
#    not a $30M runaway) even if you leave it running. Raise it for bigger
#    numbers, lower it to stay closer to the $4.28M anchor.
python -m attribution_agent.mock_generator --stream --backfill --no-ambient --interval 8 --max-journeys 12

# 2. launch the agent on the live pipeline
python -m attribution_agent.agent.cli --source mcp
```

Quick pre-flight at the `agent>` prompt: `summary` (non-zero revenue + spend,
QoQ in a sane +30–50% range), `recs` (proposes a move). If `recs` is empty, the
data's still thin — let the stream run a bit longer. The cap means the totals
plateau on their own, so you no longer have to Ctrl-C the stream mid-demo to
keep the number steady.

---

## The walk (≈5 min)

**Open — say, don't type (15 sec)**
> "This is an AI agent sitting on our marketing data — Salesforce, HubSpot, GA4,
> ad platforms — streaming live through DeltaStream. **One source of truth, not a
> dashboard.** The point isn't prettier charts — it's a number your CFO and CRO
> will believe in the room. Watch."

**1. `summary`**
> "Here's the quarter, live. Attributed revenue, blended ROI, CAC — straight from
> your systems. This is the number, and the CFO can drill into where every dollar
> came from. And model agreement — these three attribution models only agree ~75%
> of the time, which is the whole problem: pick the wrong one and you cut the
> wrong channel."

**2. `channels`**
> "Same revenue, three lenses — last-touch, linear, time-decay. Last-touch
> over-credits the final ad click; time-decay shows Email and SDR doing the real
> mid-funnel work. The disagreement is the point."

**3. `cac`**
> "Now bring in spend. Per-channel ROI. Paid Social is underwater — under a
> dollar back per dollar in. And look at the top: **AI Assistant, 17x** — deals
> where an LLM pointed the buyer at us. Highest ROI in the mix, and a batch
> report a day stale can't see it."

**4. `aishare`**  ← the differentiator nobody else has
> "Here's the catch with that channel: you can't *buy* an LLM recommendation. So
> the agent won't reallocate into it — it watches **share of model** instead. And
> right now we've **slipped out of the answer** on 'cloud cost anomaly detection'
> — ranked and cited yesterday, gone today. A model updated and we fell off. No
> ad dashboard shows you that. We caught it live."

**5. `recs`**  ← the money beat
> "So the agent proposes a reallocation: trim Paid Social and Paid Search, move
> that budget to Email, Organic, SDR. Every move is **capped at 20% a week**,
> each line has its rationale — and note the footer: it flags AI Assistant as
> top ROI but refuses to fund it (no media lever). It drafts; I decide."

**6. `reject 0 not this quarter` then `approve 2`**
> "Human in the loop. I reject the Paid Social cut, approve the Email increase —
> both logged for the audit trail. No autonomous spend changes."

**7. `ask how would revenue change if I took the increases but skipped the cuts?`**
> "And I can just ask it, in plain English — grounded in the live numbers, not
> made up."

**8. `export`**
> "And it ends as the spreadsheet I already forward to the CFO. No new dashboard
> to live in."

**Close (15 sec)**
> "Amazon shifts its budget across platforms *hourly* because it sees the signal
> live. Your agencies report back monthly — this gives you that same reflex.
> The honest catch: revenue itself lags your sales cycle, no pipeline changes
> that — and saying so is what makes the rest credible. But the leading signals
> move hourly, and the moment an *agent* acts on your data it has to see *now*.
> The payoff isn't the dashboard — it's a number the CFO and CRO believe, and
> **proven ROI is what protects the budget.** You turn it on like SaaS — no
> six-month IT project. That's the bet."

---

## If something's off mid-demo

| symptom | quick recovery |
|---|---|
| `recs` empty | data too thin — `refresh`, or it needs more stream time. Pivot to `cac` (the ROI spread still lands) |
| `aishare` empty | needs the live probe feed — make sure datagen is running with `--stream` (not just `--backfill`), then `refresh` |
| `aishare` not slipped yet | the drop fires ~2 min into the stream; `refresh` after a moment, or just narrate the "strong/slipping" rows |
| spend `$0` / no ROI | spend batch was missed — run `python -m attribution_agent.mock_generator` once, then `refresh` |
| can't reach DeltaStream | fall back: `python -m attribution_agent.agent.cli --source sample` (offline canonical figures; say it's the offline mode) |

---

The *why* behind every line above — buyer, trust story, budget-protection close —
is in `positioning.md`. The full timed version is `demo_script.md`.
