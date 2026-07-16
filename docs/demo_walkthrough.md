# Demo Walkthrough — quick run sheet

The 5-minute live drive. (The full version with objection-handling is
`demo_script.md`; this is the cheat sheet you keep on a second screen.)

---

## Before the call (5 min)

```bash
# 1. one command brings the whole demo up: deploy → backfill the $4.28M / 36-deal
#    anchor → start the live stream → serve the dashboard at http://localhost:8787/.
#    Leave it running; Ctrl-C stops both the stream and the server.
#    MAX_CONCURRENT bounds journeys in flight, so revenue climbs gently and
#    continuously through the call (not a plateau, not a $30M runaway). Raise it
#    for a faster climb, lower it to hug the $4.28M anchor.
bash scripts/demo_up.sh                      # or: MAX_CONCURRENT=6 bash scripts/demo_up.sh

# 2. (optional) launch the agent on the live pipeline in another terminal
python -m attribution_agent.agent.cli --source mcp
```

Open **http://localhost:8787/** for the board. The backfill is guaranteed —
`demo_up.sh` publishes it as a blocking step before serving, so the board never
opens with only the thin live journeys.

### The live story (scripted beats)

`demo_up.sh` runs a scripted scenario so the board actually *moves* on cue. The
terminal running the stream prints a `🎬` director line as each beat lands — glance
at it, then point at the board:

| T+     | Beat | Talking point | What shows on screen |
|--------|------|---------------|----------------------|
| 0s     | Baseline | Figures recompute from the event stream as deals close. | Warm-up deals close; sourced-pipeline tile + bars tick up |
| ~35s   | Revenue pace | Attribution updates continuously, not on a nightly batch. | "Revenue pace shifted" card; bars move |
| **90s**| **AI-answer slip** | **A tracked buyer query dropped out of ChatGPT, Perplexity, and Gemini — a signal ad and last-touch reporting don't carry.** | **DRIFT card fires**; share-of-model bends to zero |
| ~115s  | Agent responds | The agent flags it but proposes no budget move — the AI Assistant channel has no media lever. | Decision-ledger entry; share-of-model watch |

The DRIFT card lands ~10–30s after the `🎬` cue (pipeline latency) — narrate into it
and it appears. Tune the slip with `SLIP_AT=120 bash scripts/demo_up.sh`.

**Drive it by hand:** to fire the next beat on cue, `touch /tmp/demo_cue` from
another terminal instead of waiting on the timer.

Quick pre-flight at the `agent>` prompt: `summary` (non-zero revenue + spend,
QoQ in a sane +30–50% range), `recs` (proposes a move). If `recs` is empty, the
data's still thin — let the stream run a bit longer. Deals keep closing at a
bounded rate (the concurrent cap), so the headline climbs gently through the
call instead of plateauing or running away — no need to Ctrl-C mid-demo.

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
