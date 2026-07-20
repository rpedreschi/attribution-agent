# DeltaStream Pulse — dashboard guide

Two ways to use the dashboard. Pick the one that fits what you're doing.

---

## Option A — Just show the dashboard (no setup)

For slides, screenshots, click-throughs, or sharing. Nothing to install.

1. Open **`ui/deltastream-pulse.html`** in any web browser (double-click it, or
   drag it onto a browser window).

That's it. It's one self-contained file with a full example board — all four
screens (Live board, Model compare, Reallocation agent, Decision ledger) with
realistic numbers. You can email it, drop it in a deck, or open it offline on a
plane. The numbers are a fixed, believable example ($4.28M sourced pipeline); it
does not change on its own.

The **Export board pack** button (top right) downloads a six-sheet Excel workbook
whose numbers match what's on the screen — works offline, right from this file.

---

## Option B — Run it live (moving numbers)

For a live demo where deals close and the board updates on screen, including the
"dropped from AI answers" moment. This uses Rachel's DeltaStream login.

**One-time setup**

1. Copy the settings template and fill it in:
   ```
   cp .env.example .env
   ```
   Open `.env` and paste in the DeltaStream token and WarpStream values (ask
   Rachel for these). Save it.
2. Write the app config and create the store + database (first time only):
   ```
   bash scripts/make_settings.sh
   bash scripts/demo_init.sh
   ```

**Every time you want to demo**

```
bash scripts/demo_up.sh
```

Wait for it to print `ready — NN won accounts in the views`, then open
**http://localhost:8787/** in your browser. Leave the terminal running; press
`Ctrl-C` there when you're done to stop everything.

The **Export board pack** button downloads a six-sheet Excel workbook of the
current live numbers, matching the board on screen.

While it runs, the terminal prints a `🎬` line each time a story beat happens
(baseline, revenue update, the AI-answer slip, the agent response) — glance at it,
then point at the board. The slip fires about 90 seconds in.

**Want a frozen copy of the live numbers?** After it's been running a minute:
```
python scripts/build_static_ui.py --source mcp
```
That overwrites `ui/deltastream-pulse.html` with the current live board baked in —
a portable file you can share, exactly like Option A but with live figures.

---

## If something looks off

- **Board shows a low total (~$1.1M) or a channel is missing** — the backfill
  didn't load. Stop with `Ctrl-C` and run `bash scripts/demo_up.sh` again; watch
  for the `Published … events to Kafka` line, which is the backfill going out.
- **Browser page is raw text/JSON instead of the dashboard** — make sure you
  opened `http://localhost:8787/` (with the trailing slash), not a `.json` URL.
- **`bash: ...: command not found` or a token error** — a value in `.env` is
  missing or wrong; re-check it against what Rachel gave you.
