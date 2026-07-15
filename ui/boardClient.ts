// Tiny typed client for the board view. Framework-agnostic fetch + an optional
// React hook. Point it at the served endpoint (`board_view --serve 8787`) or the
// static fixture (./sample-board.json) during design.

import type { BoardView } from "./board.d";

export const DEFAULT_ENDPOINT = "http://localhost:8787/board.json";

/** Fetch one board view. Throws on HTTP / network error. */
export async function fetchBoardView(
  url: string = DEFAULT_ENDPOINT,
  init?: RequestInit,
): Promise<BoardView> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`board view ${res.status} ${res.statusText}`);
  return (await res.json()) as BoardView;
}

/** "recomputed_at" -> "3s ago" style label for the header chip. */
export function recomputedAgo(recomputedAt: string, now: number = Date.now()): string {
  const secs = Math.max(0, Math.round((now - Date.parse(recomputedAt)) / 1000));
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  return `${Math.round(secs / 3600)}h ago`;
}

/** Live CPL per bucket for a channel: spend / touches, aligned by index. */
export function cplSeries(view: BoardView, channel: string): Array<{ t: string; cpl: number | null }> {
  const spend = view.trends.spend_by_channel[channel] ?? [];
  const touches = view.trends.touches_by_channel[channel] ?? [];
  return spend.map((s, i) => {
    const t = touches[i]?.touches ?? 0;
    return { t: s.t, cpl: t > 0 ? s.spend / t : null };
  });
}

// ---- optional React hook --------------------------------------------------
// Usage: const { data, error, loading } = useBoardView({ intervalMs: 5000 });
// (Import React in your app; this file has no hard React dependency until used.)

export interface UseBoardViewOpts {
  url?: string;
  intervalMs?: number; // poll cadence; 0 = fetch once
}

export function makeUseBoardView(react: typeof import("react")) {
  const { useState, useEffect, useRef } = react;
  return function useBoardView(opts: UseBoardViewOpts = {}) {
    const { url = DEFAULT_ENDPOINT, intervalMs = 5000 } = opts;
    const [data, setData] = useState<BoardView | null>(null);
    const [error, setError] = useState<Error | null>(null);
    const [loading, setLoading] = useState(true);
    const alive = useRef(true);

    useEffect(() => {
      alive.current = true;
      const tick = async () => {
        try {
          const v = await fetchBoardView(url);
          if (alive.current) { setData(v); setError(null); }
        } catch (e) {
          if (alive.current) setError(e as Error);
        } finally {
          if (alive.current) setLoading(false);
        }
      };
      tick();
      const id = intervalMs > 0 ? setInterval(tick, intervalMs) : undefined;
      return () => { alive.current = false; if (id) clearInterval(id); };
    }, [url, intervalMs]);

    return { data, error, loading };
  };
}
