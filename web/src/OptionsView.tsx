import { useCallback, useEffect, useState } from "react";
import { useAuth } from "./AuthContext";
import { apiGet, apiPost } from "./lib/api";

const LS_PROFILE = "sherpa_sim_profile";

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

type OptionsPositionRow = {
  position_key: string;
  underlying: string;
  expiry: string;
  strike: number;
  option_type: "call" | "put";
  contracts: number;
  avg_premium: number;
  mark: number;
  market_value: number;
  unrealized_pnl: number;
};

type OptionsPositionsResponse = {
  profile: string;
  cash: number;
  equity: number;
  positions: OptionsPositionRow[];
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

function formatMoney(n: number) {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function RecommendationCard({
  rec,
  expanded,
  onToggle,
  onPaperTrade,
  paperBusy,
}: {
  rec: TradeRecommendation;
  expanded: boolean;
  onToggle: () => void;
  onPaperTrade?: () => void;
  paperBusy?: boolean;
}) {
  const canPaper = rec.recommendation !== "NEUTRAL" && rec.suggested_strike && rec.suggested_expiry;

  return (
    <article
      className={`glass p-5 transition hover:ring-1 hover:ring-mint-500/30 ${
        expanded ? "ring-2 ring-mint-500/40" : ""
      }`}
    >
      <div
        className="cursor-pointer"
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
      </div>

      {onPaperTrade && (
        <div className="mt-4 border-t border-slate-200 pt-4">
          <button
            type="button"
            className="btn-primary w-full sm:w-auto"
            disabled={!canPaper || paperBusy}
            onClick={(e) => {
              e.stopPropagation();
              onPaperTrade();
            }}
          >
            {paperBusy ? "Submitting…" : "Paper trade this pick"}
          </button>
          {!canPaper && (
            <p className="mt-2 text-xs text-slate-500">Neutral picks or missing strike/expiry cannot be paper traded.</p>
          )}
        </div>
      )}
    </article>
  );
}

export function OptionsView() {
  const { ready, authRequired, user } = useAuth();
  const apiEnabled = ready && (!authRequired || Boolean(user));

  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"dow" | "nasdaq">("dow");
  const [expanded, setExpanded] = useState<string | null>(null);

  const [profile, setProfile] = useState("default");
  const [contracts, setContracts] = useState("1");
  const [positions, setPositions] = useState<OptionsPositionsResponse | null>(null);
  const [posBusy, setPosBusy] = useState<string | null>(null);
  const [tradeMsg, setTradeMsg] = useState<string | null>(null);

  useEffect(() => {
    try {
      const p = localStorage.getItem(LS_PROFILE);
      if (p) setProfile(p);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(LS_PROFILE, profile);
    } catch {
      /* ignore */
    }
  }, [profile]);

  const loadPositions = useCallback(async () => {
    if (!apiEnabled) return;
    const q = new URLSearchParams({ profile });
    const json = await apiGet<OptionsPositionsResponse>(`/api/trade/paper/options/positions?${q}`);
    setPositions(json);
  }, [apiEnabled, profile]);

  useEffect(() => {
    void loadPositions().catch(() => setPositions(null));
  }, [loadPositions]);

  const fetchRecommendations = useCallback(async (refresh = false) => {
    if (!apiEnabled) return;
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
  }, [apiEnabled]);

  useEffect(() => {
    void fetchRecommendations();
  }, [fetchRecommendations]);

  const paperTradePick = async (rec: TradeRecommendation) => {
    if (!rec.suggested_strike || !rec.suggested_expiry || rec.recommendation === "NEUTRAL") return;
    const n = parseInt(contracts, 10);
    if (!Number.isFinite(n) || n < 1) {
      setTradeMsg("Enter a valid contract count (1 or more).");
      return;
    }
    setPosBusy(rec.symbol);
    setTradeMsg(null);
    try {
      const optionType =
        rec.recommendation === "BUY_PUT" ? "put" : rec.recommendation === "BUY_CALL" ? "call" : "call";
      const r = await apiPost<{ avg_premium: number; action: string }>("/api/trade/paper/options", {
        profile,
        underlying: rec.symbol,
        expiry: rec.suggested_expiry,
        strike: rec.suggested_strike,
        option_type: optionType,
        contracts: n,
        recommendation: rec.recommendation,
      });
      setTradeMsg(
        `Filled ${n} ${optionType} contract(s) on ${rec.symbol} @ $${r.avg_premium.toFixed(2)} (${r.action.replace(/_/g, " ")}).`,
      );
      await loadPositions();
    } catch (err) {
      setTradeMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setPosBusy(null);
    }
  };

  const closePosition = async (pos: OptionsPositionRow) => {
    const abs = Math.abs(pos.contracts);
    setPosBusy(pos.position_key);
    setTradeMsg(null);
    try {
      const action = pos.contracts > 0 ? "sell_to_close" : "buy_to_close";
      await apiPost("/api/trade/paper/options", {
        profile,
        underlying: pos.underlying,
        expiry: pos.expiry,
        strike: pos.strike,
        option_type: pos.option_type,
        contracts: abs,
        action,
      });
      setTradeMsg(`Closed ${abs} ${pos.option_type} contract(s) on ${pos.underlying}.`);
      await loadPositions();
    } catch (err) {
      setTradeMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setPosBusy(null);
    }
  };

  const refreshMarks = async () => {
    setPosBusy("marks");
    setTradeMsg(null);
    try {
      const q = new URLSearchParams({ profile });
      await apiPost(`/api/trade/paper/options/refresh-marks?${q}`);
      await loadPositions();
      setTradeMsg("Option marks updated from live chain quotes.");
    } catch (err) {
      setTradeMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setPosBusy(null);
    }
  };

  const recommendations = tab === "dow" ? data?.dow_jones : data?.nasdaq;
  const tabLabel = tab === "dow" ? "Dow Jones 30" : "NASDAQ-100";

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-900">Options Picks</h1>
          <p className="mt-1 text-sm text-slate-600">
            Daily US options trade recommendations for Dow Jones and NASDAQ-100 — with paper trading on the
            same sandbox profile as equity paper trades.
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
                <strong className="text-slate-700">{new Date(data.generated_at).toLocaleString()}</strong>
              </div>
            </div>
          )}
          <button
            type="button"
            className="btn-primary"
            onClick={() => fetchRecommendations(true)}
            disabled={loading || !apiEnabled}
          >
            {loading ? "Analyzing…" : "Refresh Analysis"}
          </button>
        </div>
      </div>

      <section className="glass mt-8 p-6">
        <h2 className="font-display text-lg font-semibold text-slate-900">Paper options trading</h2>
        <p className="mt-1 text-sm text-slate-600">
          Uses sandbox cash from your simulation profile. Fills at chain mid ± slippage (100 shares per
          contract). Not real brokerage execution.
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <div className="min-w-[140px]">
            <label className="mb-1 block text-xs text-slate-500">Simulation profile</label>
            <input
              className="input font-mono text-sm"
              value={profile}
              onChange={(e) => setProfile(e.target.value.trim() || "default")}
              spellCheck={false}
            />
          </div>
          <div className="w-24">
            <label className="mb-1 block text-xs text-slate-500">Contracts</label>
            <input
              className="input"
              value={contracts}
              onChange={(e) => setContracts(e.target.value)}
              inputMode="numeric"
            />
          </div>
          <button type="button" className="btn-ghost" disabled={posBusy !== null} onClick={() => loadPositions()}>
            Refresh positions
          </button>
          <button type="button" className="btn-ghost" disabled={posBusy !== null} onClick={() => refreshMarks()}>
            {posBusy === "marks" ? "Updating…" : "Update marks"}
          </button>
        </div>
        {positions && (
          <dl className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-slate-500">Sandbox cash</dt>
              <dd className="font-mono text-lg text-mint-700">${formatMoney(positions.cash)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Total equity</dt>
              <dd className="font-mono text-lg text-slate-900">${formatMoney(positions.equity)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Open option legs</dt>
              <dd className="font-mono text-lg text-slate-800">{positions.positions.length}</dd>
            </div>
          </dl>
        )}
        {tradeMsg && (
          <p
            className={`mt-4 rounded-lg border px-3 py-2 text-sm ${
              tradeMsg.startsWith("Filled") || tradeMsg.startsWith("Closed") || tradeMsg.startsWith("Option")
                ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                : "border-red-200 bg-red-50 text-red-800"
            }`}
          >
            {tradeMsg}
          </p>
        )}
        {positions && positions.positions.length > 0 ? (
          <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-100">
                <tr className="border-b border-slate-200 text-slate-500">
                  <th className="px-3 py-2 font-medium">Underlying</th>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium">Strike</th>
                  <th className="px-3 py-2 font-medium">Expiry</th>
                  <th className="px-3 py-2 font-medium">Qty</th>
                  <th className="px-3 py-2 font-medium">Avg</th>
                  <th className="px-3 py-2 font-medium">Mark</th>
                  <th className="px-3 py-2 font-medium">P&amp;L</th>
                  <th className="px-3 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {positions.positions.map((p) => (
                  <tr key={p.position_key} className="border-b border-slate-100 font-mono text-slate-700">
                    <td className="px-3 py-2 text-mint-700">{p.underlying}</td>
                    <td className="px-3 py-2 uppercase">{p.option_type}</td>
                    <td className="px-3 py-2">${formatMoney(p.strike)}</td>
                    <td className="px-3 py-2">{p.expiry}</td>
                    <td className="px-3 py-2">{p.contracts > 0 ? `+${p.contracts}` : p.contracts}</td>
                    <td className="px-3 py-2">${formatMoney(p.avg_premium)}</td>
                    <td className="px-3 py-2">${formatMoney(p.mark)}</td>
                    <td className={`px-3 py-2 ${p.unrealized_pnl >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                      {p.unrealized_pnl >= 0 ? "+" : ""}
                      {formatMoney(p.unrealized_pnl)}
                    </td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        className="text-amber-700 underline hover:text-amber-900"
                        disabled={posBusy !== null}
                        onClick={() => closePosition(p)}
                      >
                        Close
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-500">
            No paper option positions yet. Use <strong>Paper trade this pick</strong> on a recommendation below
            (reset sandbox cash under Trading → Portfolio if needed).
          </p>
        )}
      </section>

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
            Scanning Dow Jones 30 and NASDAQ-100. Analyzing options chains, put/call ratios, volatility, and
            unusual activity. First load may take several minutes.
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
                  onToggle={() => setExpanded(expanded === rec.symbol ? null : rec.symbol)}
                  onPaperTrade={() => paperTradePick(rec)}
                  paperBusy={posBusy === rec.symbol}
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
