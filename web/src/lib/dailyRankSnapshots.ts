import type { PickCriteria } from "../pickCriteria";

export const DAILY_RANK_SNAPSHOTS_STORAGE_KEY = "sherpa_daily_rank_snapshots_v1";
const LS_KEY = DAILY_RANK_SNAPSHOTS_STORAGE_KEY;
const RETAIN_DAYS = 60;

export type DailyPickSnapshotRow = {
  symbol: string;
  score: number;
  reasons: string[];
  last_close: number | null;
  sma5: number | null;
  sma10: number | null;
  sma200: number | null;
  rsi: number | null;
  atr_pct: number | null;
  volume_last: number | null;
  target_buy_price: number | null;
  target_sell_price: number | null;
};

export type DailyRankSnapshot = {
  picks: DailyPickSnapshotRow[];
  disclaimer: string;
  universe_cap: number;
  candidates_scored: number;
  criteria?: PickCriteria;
};

export function localDateKey(d = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function loadDailyRankSnapshots(): Record<string, DailyRankSnapshot> {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return {};
    const p = JSON.parse(raw) as unknown;
    if (p && typeof p === "object" && !Array.isArray(p)) return p as Record<string, DailyRankSnapshot>;
    return {};
  } catch {
    return {};
  }
}

function pruneOld(all: Record<string, DailyRankSnapshot>): Record<string, DailyRankSnapshot> {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - RETAIN_DAYS);
  const minKey = localDateKey(cutoff);
  const next: Record<string, DailyRankSnapshot> = {};
  for (const k of Object.keys(all).sort()) {
    if (k >= minKey) next[k] = all[k];
  }
  return next;
}

/** Store today’s run (local calendar date). Overwrites if you run again the same day. */
export function mergeDailyRankSnapshot(snapshot: DailyRankSnapshot): void {
  try {
    const key = localDateKey();
    const all = pruneOld(loadDailyRankSnapshots());
    all[key] = snapshot;
    localStorage.setItem(LS_KEY, JSON.stringify(all));
  } catch {
    /* ignore quota / private mode */
  }
}

export function lastNDateKeys(n: number): string[] {
  const out: string[] = [];
  for (let i = 0; i < n; i++) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    out.push(localDateKey(d));
  }
  return out;
}
