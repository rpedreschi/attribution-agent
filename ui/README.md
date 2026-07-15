# UI starter kit

Everything needed to build the dashboard against the live pipeline **without
touching the backend**. The UI binds to one JSON document (`BoardView`); see
`../docs/ui_data_contract.md` for the field-by-field spec.

## Files
- **`board.d.ts`** — TypeScript types for the whole contract. Import `BoardView`.
- **`boardClient.ts`** — `fetchBoardView()`, a poll-based React hook factory
  (`makeUseBoardView`), plus helpers (`recomputedAgo`, `cplSeries`).
- **`sample-board.json`** — a stable fixture (sample data) to design against with
  zero infra. Regenerate with the command below.

## Two ways to get data

**Design-time (no infra) — use the fixture:**
```ts
import sample from "./sample-board.json";
import type { BoardView } from "./board.d";
const view = sample as BoardView;
```

**Live — run the server and point the client at it:**
```bash
# from the repo root
python -m attribution_agent.api.board_view --source mcp --serve 8787   # live DeltaStream
# or, no infra:
python -m attribution_agent.api.board_view --source sample --serve 8787
```
```ts
import { fetchBoardView, makeUseBoardView } from "./boardClient";
import * as React from "react";
const useBoardView = makeUseBoardView(React);

function Board() {
  const { data, error, loading } = useBoardView({ intervalMs: 5000 });
  if (loading) return <div>loading…</div>;
  if (error)   return <div>offline: {error.message}</div>;
  return <h1>{data!.meta.customer} — {data!.meta.period_label}</h1>;
}
```
The server rebuilds per request and sends permissive CORS, so a Vite/Next dev
server on another port can fetch it directly.

## Notes
- The four screens map to `live_board`, `model_compare`, `reallocation_agent`,
  `decision_ledger`. Header chrome is `meta` + `trends`.
- Badge anything with `illustrative: true` (or `*_illustrative`, or a card's
  `real: false`) — that's data the demo can't measure truthfully yet.
- Live CPL isn't a field; derive it with `cplSeries(view, channel)`.

## Regenerate the fixture
```bash
python -m attribution_agent.api.board_view --source sample --out ui/sample-board.json
```
