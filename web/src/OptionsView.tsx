import { useCallback, useEffect, useState } from "react";
import { apiGet } from "./lib/api";

type SignalDetail = {
  name: string;
  value: number | string;
  score: number;
  interpretation: string;
  weight: number;
};

type TradeRecommendation = {
  rank: number;
  symbol: string;
  index: "DOW" | "NASDAQ";
  current_price: number;
  recommendation: "BUY_CALL" | "BUY_PUT" | "NEUTRAL" | "SELL_PREMIUM";
  confidence: number;
  composite_score: number;
  suggested_strike: number | null;
  suggested_expiry: string | null;
  put_call_ratio: number;
  implied_volatility: number | null;
  iv_rank: number | null;
  signals: SignalDetail[];
  summary: string;
};

type RecommendationsResponse = {
  generated_at: string;
  market_date: string;
  dow_jones: TradeRecommendation[];
  nasdaq: TradeRecommendation[];
  disclaimer: string;
};

const REC_LABELS: Record<string, string> = {
  BUY_CALL: "Buy Call",
  BUY_PUT: "Buy Put",
  NEUTRAL: "Neutral",
  SELL_PREMIUM: "Sell Premium",
};

const BADGE_CLASS: Record<string, string> = {
  BUY_CALL: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  BUY_PUT: "bg-rose-100 text-rose-800 ring-rose-200",
  SELL_PREMIUM: "bg-amber-100 text-amber-800 ring-amber-200",
  NEUTRAL: "bg-slate-100 text-slate-700 ring-slate-200",
};

const CRITERIA = [
  { name: "Put/Call Ratio", desc: "Volume-weighted sentiment" },
  { name: "IV Analysis", desc: "Implied vs historical volatility" },
  { name: "Unusual Activity", desc: "Volume/OI spikes near ATM" },
  { name: "Momentum", desc: "RSI + MACD confluence" },
  { name: "Volume/OI", desc: "Positioning intensity" },
  { name: "IV Skew", desc: "Put vs call premium bias" },
  { name: "Liquidity", desc: "Bid-ask spread quality" },
  { name: "Max Pain", desc: "Options pin strike analysis" },
];

function RecommendationCard({
  rec,
  expanded,
  onToggle,
}: {
  rec: TradeRecommendation;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <article
      className={`glass cursor-pointer p-5 transition hover:ring-1 hover:ring-mint-500/30 ${
        expanded ? "ring-2 ring-mint-500/40" : ""
      }`}
      onClick={onToggle}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onToggle()}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="text-xs font-medium text-slate-500">#{rec.rank}</span>
          <div className="font-display text-xl font-bold text-slate-900">{rec.symbol}</div>
          <div className="font-mono text-sm text-slate-600">${rec.current_price.toFixed(2)}</div>
        </div>
        <span
          className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ring-1 ${
            BADGE_CLASS[rec.recommendation]
          }`}
        >
          {REC_LABELS[rec.recommendation]}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div>
          <div className="text-xs text-slate-500">PCR</div>
          <div className="font-mono font-medium">{rec.put_call_ratio.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-xs text-slate-500">IV</div>
          <div className="font-mono font-medium">
            {rec.implied_volatility != null ? `${rec.implied_volatility.toFixed(1)}%` : "—"}
          </div>
        </div>
        <div>
          <div className="text-xs text-slate-500">IV Rank</div>
          <div className="font-mono font-medium">
            {rec.iv_rank != null ? `${rec.iv_rank.toFixed(0)}%` : "—"}
          </div>
        </div>
        <div>
          <div className="text-xs text-slate-500">Strike / Exp</div>
          <div className="font-mono text-xs font-medium">
            {rec.suggested_strike ? `$${rec.suggested_strike}` : "—"}
            {rec.suggested_expiry ? ` · ${rec.suggested_expiry}` : ""}
          </div>
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1 flex justify-between text-xs text-slate-500">
          <span>Score {rec.composite_score.toFixed(0)}</span>
          <span>Confidence {rec.confidence.toFixed(0)}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-mint-600 transition-all"
            style={{ width: `${rec.composite_score}%` }}
          />
        </div>
      </div>

      <p className="mt-3 text-sm text-slate-600">{rec.summary}</p>

      {expanded && (
        <div className="mt-4 space-y-2 border-t border-slate-200 pt-4">
          {rec.signals.map((s) => (
            <div key={s.name} className="grid grid-cols-[1fr_auto] gap-2 text-sm sm:grid-cols-[140px_48px_1fr]">
              <span className="font-medium text-slate-700">{s.name}</span>
              <span className="font-mono text-mint-700">{s.score.toFixed(0)}</span>
              <span className="col-span-2 text-slate-500 sm:col-span-1">{s.interpretation}</span>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

export function OptionsView() {
  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"dow" | "nasdaq">("dow");
  const [expanded, setExpanded] = useState<string | null>(null);

  const fetchRecommendations = useCallback(async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const q = refresh ? "?refresh=true" : "";
      const json = await apiGet<RecommendationsResponse>(`/api/recommendations/options${q}`);
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load options recommendations");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  const recommendations = tab === "dow" ? data?.dow_jones : data?.nasdaq;
  const tabLabel = tab === "dow" ? "Dow Jones 30" : "NASDAQ-100";

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-900">Options Picks</h1>
          <p className="mt-1 text-sm text-slate-600">
            Daily US options trade recommendations for Dow Jones and NASDAQ-100 (SevenHorses engine).
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          {data && (
            <div className="text-right text-xs text-slate-500">
              <div>
                Market date: <strong className="text-slate-700">{data.market_date}</strong>
              </div>
              <div>
                Updated:{" "}
                <strong className="text-slate-700">
                  {new Date(data.generated_at).toLocaleString()}
                </strong>
              </div>
            </div>
          )}
          <button
            type="button"
            className="btn-primary"
            onClick={() => fetchRecommendations(true)}
            disabled={loading}
          >
            {loading ? "Analyzing…" : "Refresh Analysis"}
          </button>
        </div>
      </div>

      <div className="mt-6 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {CRITERIA.map((c) => (
          <div key={c.name} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs">
            <strong className="text-slate-800">{c.name}</strong>
            <span className="text-slate-500"> — {c.desc}</span>
          </div>
        ))}
      </div>

      {error && (
        <div className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && !data && (
        <div className="mt-12 flex flex-col items-center gap-4 text-center text-slate-500">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-mint-500 border-t-transparent" />
          <p className="max-w-md text-sm">
            Scanning Dow Jones 30 and NASDAQ-100. Analyzing options chains, put/call ratios,
            volatility, and unusual activity. First load may take several minutes.
          </p>
        </div>
      )}

      {data && (
        <>
          <div className="mt-8 flex gap-2 border-b border-slate-200">
            <button
              type="button"
              className={`px-4 py-2 text-sm font-medium ${
                tab === "dow"
                  ? "border-b-2 border-mint-600 text-mint-700"
                  : "text-slate-500 hover:text-slate-700"
              }`}
              onClick={() => setTab("dow")}
            >
              Dow Jones — Top 10
            </button>
            <button
              type="button"
              className={`px-4 py-2 text-sm font-medium ${
                tab === "nasdaq"
                  ? "border-b-2 border-mint-600 text-mint-700"
                  : "text-slate-500 hover:text-slate-700"
              }`}
              onClick={() => setTab("nasdaq")}
            >
              NASDAQ — Top 10
            </button>
          </div>

          <h2 className="mt-6 text-sm font-medium text-slate-600">
            {tabLabel} — Top {recommendations?.length ?? 0} picks
          </h2>

          {recommendations && recommendations.length > 0 ? (
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              {recommendations.map((rec) => (
                <RecommendationCard
                  key={rec.symbol}
                  rec={rec}
                  expanded={expanded === rec.symbol}
                  onToggle={() =>
                    setExpanded(expanded === rec.symbol ? null : rec.symbol)
                  }
                />
              ))}
            </div>
          ) : (
            <p className="mt-6 text-sm text-slate-500">No recommendations available.</p>
          )}

          <p className="mt-8 text-center text-xs text-slate-500">{data.disclaimer}</p>
        </>
      )}
    </div>
  );
}
