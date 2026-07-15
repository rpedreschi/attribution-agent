// TypeScript contract for the DeltaStream Pulse board view.
// Produced by `python -m attribution_agent.api.board_view` (see docs/ui_data_contract.md).
// Bind your UI to `BoardView`. A stable sample lives in ./sample-board.json.

export interface BoardView {
  meta: Meta;
  trends: Trends;
  live_board: LiveBoard;
  model_compare: ModelCompare;
  reallocation_agent: ReallocationAgent;
  decision_ledger: LedgerEvent[];
}

export interface Meta {
  customer: string;
  period_label: string;          // e.g. "2026-Q1 to date"
  recomputed_at: string;         // ISO datetime — drives "recomputed Ns ago"
  events_per_sec: number;
  events_per_sec_illustrative: boolean;
  window: string;
  trend_buckets: number;         // minutes of history available to the time filter
  sources_streaming: number;
  environment: string;
}

// ---- trends (time axis) ---------------------------------------------------
export interface Trends {
  bucket: "minute";
  revenue: RevenuePoint[];
  touches_by_channel: Record<string, TouchPoint[]>;
  spend_by_channel: Record<string, SpendPoint[]>;
  share_of_model: Record<string, MentionPoint[]>;
  illustrative: boolean;         // true in sample mode
}
export interface RevenuePoint { t: string; revenue: number; deals: number; }
export interface TouchPoint    { t: string; touches: number; }
export interface SpendPoint    { t: string; spend: number; }
export interface MentionPoint  { t: string; mention_rate: number; }
// Live CPL for a channel/bucket = spend_by_channel[ch][i].spend / touches_by_channel[ch][i].touches

// ---- screen 1: live board -------------------------------------------------
export interface LiveBoard {
  kpis: Kpi[];
  what_changed: ChangeCard[];
  money_by_channel: MoneyRow[];
}
export interface Kpi {
  key: "sourced_pipeline" | "influenced" | "blended_cac" | "cac_payback_months";
  label: string;
  value: number | null;
  format: "currency" | "months";
  delta_pct: number | null;
  delta_label: string;
  subtext: string;
}
export interface ChangeCard {
  kind: "drift" | "new" | "low_confidence";
  title: string;
  body: string;
  real: boolean;                 // false => illustrative, badge it
}
export interface MoneyRow { channel: string; revenue: number; share: number; }

// ---- screen 2: model compare ---------------------------------------------
export interface ModelCompare {
  models: AttributionModel[];
  model_labels: Record<AttributionModel, string>;
  credit_by_channel: CreditRow[];
  credit_by_campaign: CampaignRow[];
  incrementality_tests: { illustrative: boolean; note: string; tests: unknown[] };
}
export type AttributionModel = "last_touch" | "linear" | "time_decay";
export interface CreditRow {
  channel: string;
  shares: Record<AttributionModel, number>;   // fractions, ~sum to 1 per model
  spread_pts: number;                          // max-min disagreement, points
  status: "agree" | "disagree" | "thin";
}
export interface CampaignRow {
  campaign: string; channel: string; spend: number;
  attributed_revenue: number; deals: number; roi: number | null;
}

// ---- screen 3: reallocation agent ----------------------------------------
export interface ReallocationAgent {
  recommendations: Recommendation[];
  autonomy: Autonomy;
}
export interface Recommendation {
  id: number;
  title: string;
  action: "Increase" | "Decrease";
  channel: string;
  current_spend: number;
  delta: number;
  proposed_spend: number;
  expected_revenue_impact: number;
  confidence: "high" | "low";
  rationale: string;
  basis: string[];               // "Show the math" source references
  reversible_days: number;
  status: "pending";
}
export interface Autonomy {
  level: number;
  max_level: number;
  weekly_cap: number;
  match_rate: { matched: number; of: number };
  note: string;
}

// ---- screen 4: decision ledger -------------------------------------------
export interface LedgerEvent {
  ts: string;
  event: string;
  actor: "AGENT" | "SYSTEM" | "HUMAN";
  result: string;
}
