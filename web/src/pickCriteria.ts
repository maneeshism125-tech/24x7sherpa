const LS_KEY = "sherpa_pick_criteria";

export const UNIVERSE_OPTIONS = [
  { id: "sp500", label: "S&P 500" },
  { id: "dow", label: "Dow Jones (DJIA)" },
  { id: "nasdaq100", label: "Nasdaq-100 (QQQ)" },
  { id: "nasdaq", label: "Nasdaq-listed stocks" },
  { id: "russell2000", label: "Russell 2000" },
] as const;

export type UniverseId = (typeof UNIVERSE_OPTIONS)[number]["id"];

const UNIVERSE_IDS = new Set<string>(UNIVERSE_OPTIONS.map((o) => o.id));

export function universeLabel(id: string): string {
  const o = UNIVERSE_OPTIONS.find((x) => x.id === id);
  return o?.label ?? id;
}

export type PickCriteria = {
  universe_id: UniverseId;
  universe_cap: number;
  pick_count: number;
  skip_news: boolean;
  min_bars: number;
  min_volume: number;
  require_above_sma200: boolean;
  rsi_band_low: number;
  rsi_band_high: number;
  rsi_overbought: number;
  volume_surge_ratio: number;
  /** ATR(14)/price; e.g. 0.015 ≈ 1.5% of price */
  atr_elevated_pct: number;
  news_penalty: number;
  sell_atr_multiplier: number;
};

export const DEFAULT_PICK_CRITERIA: PickCriteria = {
  universe_id: "sp500",
  universe_cap: 150,
  pick_count: 10,
  skip_news: false,
  min_bars: 200,
  min_volume: 200_000,
  require_above_sma200: true,
  rsi_band_low: 38,
  rsi_band_high: 65,
  rsi_overbought: 70,
  volume_surge_ratio: 1.35,
  atr_elevated_pct: 0.015,
  news_penalty: 45,
  sell_atr_multiplier: 1,
};

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}

export function loadPickCriteria(): PickCriteria {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { ...DEFAULT_PICK_CRITERIA };
    const p = JSON.parse(raw) as Record<string, unknown>;
    const base = { ...DEFAULT_PICK_CRITERIA };
    const num = (k: keyof PickCriteria, lo: number, hi: number) => {
      const v = p[k];
      if (typeof v === "number" && Number.isFinite(v)) base[k] = clamp(v, lo, hi) as never;
    };
    const int = (k: keyof PickCriteria, lo: number, hi: number) => {
      const v = p[k];
      if (typeof v === "number" && Number.isFinite(v))
        base[k] = Math.round(clamp(v, lo, hi)) as never;
    };
    const bool = (k: keyof PickCriteria) => {
      if (typeof p[k] === "boolean") base[k] = p[k] as never;
    };
    if (typeof p.universe_id === "string" && UNIVERSE_IDS.has(p.universe_id)) {
      base.universe_id = p.universe_id as UniverseId;
    }
    int("universe_cap", 20, 3500);
    int("pick_count", 1, 25);
    bool("skip_news");
    int("min_bars", 200, 400);
    num("min_volume", 0, 50_000_000);
    bool("require_above_sma200");
    num("rsi_band_low", 0, 100);
    num("rsi_band_high", 0, 100);
    num("rsi_overbought", 50, 100);
    num("volume_surge_ratio", 1, 5);
    num("atr_elevated_pct", 0.001, 0.1);
    num("news_penalty", 0, 100);
    num("sell_atr_multiplier", 0.1, 5);
    if (base.rsi_band_low > base.rsi_band_high) {
      [base.rsi_band_low, base.rsi_band_high] = [base.rsi_band_high, base.rsi_band_low];
    }
    return base;
  } catch {
    return { ...DEFAULT_PICK_CRITERIA };
  }
}

export function savePickCriteria(c: PickCriteria): void {
  localStorage.setItem(LS_KEY, JSON.stringify(c));
}
