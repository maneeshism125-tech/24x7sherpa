import { useCallback, useEffect, useState } from "react";
import { AdminView } from "./AdminView";
import { useAuth } from "./AuthContext";
import { AuthEntry } from "./AuthEntry";
import { apiGet, apiGetOrNull, apiPost } from "./lib/api";
import { loadPickCriteria, type PickCriteria, universeLabel } from "./pickCriteria";
import { SettingsView } from "./SettingsView";

const LS_PROFILE = "sherpa_sim_profile";

type SimStatus = {
  profile: string;
  path: string;
  starting_cash: number;
  equity: number;
  cash: number;
  pnl: number;
  positions: {
    symbol: string;
    qty: number;
    last: number;
    market_value: number;
  }[];
  last_reset: string | null;
};

type Account = {
  equity: number;
  cash: number;
  buying_power: number;
  profile: string;
};

type SignalRow = {
  symbol: string;
  side: string;
  score: number;
  reasons: string[];
};

type ScanResult = { signals: SignalRow[]; scanned: number };

type DailyPickRow = {
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

type DailyRecResult = {
  picks: DailyPickRow[];
  disclaimer: string;
  universe_cap: number;
  candidates_scored: number;
  criteria: PickCriteria;
};

function formatMoney(n: number) {
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export default function App() {
  const { ready, authRequired, user, err: authErr, logout } = useAuth();
  const [page, setPage] = useState<"main" | "settings" | "admin">("main");
  const [pickCriteria, setPickCriteria] = useState<PickCriteria>(() => loadPickCriteria());
  const [universeRefresh, setUniverseRefresh] = useState(() => loadPickCriteria().universe_id);
  const [profile, setProfile] = useState("default");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sim, setSim] = useState<SimStatus | null>(null);
  const [acct, setAcct] = useState<Account | null>(null);
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [dailyRec, setDailyRec] = useState<DailyRecResult | null>(null);

  const [resetCash, setResetCash] = useState("100000");
  const [tradeSym, setTradeSym] = useState("AAPL");
  const [tradeSide, setTradeSide] = useState<"buy" | "sell">("buy");
  const [tradeQty, setTradeQty] = useState("1");
  const [scanTop, setScanTop] = useState("15");
  const [scanSkipNews, setScanSkipNews] = useState(false);

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

  const run = useCallback(async (label: string, fn: () => Promise<void>) => {
    setErr(null);
    setBusy(label);
    try {
      await fn();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }, []);

  const loadStatus = useCallback(() => {
    return run("status", async () => {
      const q = new URLSearchParams({ profile });
      const data = await apiGetOrNull<SimStatus>(`/api/simulate/status?${q}`);
      setSim(data);
    });
  }, [profile, run]);

  const loadAccount = useCallback(() => {
    return run("account", async () => {
      const q = new URLSearchParams({ profile });
      const data = await apiGet<Account>(`/api/account/paper?${q}`);
      setAcct(data);
    });
  }, [profile, run]);

  useEffect(() => {
    void loadStatus().catch(() => setSim(null));
    void loadAccount().catch(() => setAcct(null));
  }, [loadAccount, loadStatus]);

  useEffect(() => {
    setUniverseRefresh(pickCriteria.universe_id);
  }, [pickCriteria.universe_id]);

  useEffect(() => {
    if (page === "admin" && !user?.is_admin) setPage("main");
  }, [page, user?.is_admin]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }

  if (authErr) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center text-red-200">
        <p>{authErr}</p>
      </div>
    );
  }

  if (authRequired && !user) {
    return <AuthEntry />;
  }

  if (page === "admin" && user?.is_admin) {
    return <AdminView onBack={() => setPage("main")} />;
  }

  if (page === "settings") {
    return (
      <SettingsView
        criteria={pickCriteria}
        onSave={(c) => {
          setPickCriteria(c);
          setPage("main");
        }}
        onCancel={() => setPage("main")}
      />
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 pb-24 pt-10 sm:px-6 lg:px-8">
      <header className="mb-12 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-display text-sm font-semibold uppercase tracking-widest text-mint-500">
            24×7 Sherpa
          </p>
          <h1 className="font-display mt-2 text-4xl font-bold tracking-tight text-white sm:text-5xl">
            Paper trading lab
          </h1>
          <p className="mt-3 max-w-xl text-slate-400">
            Practice with fake money on S&amp;P 500 names: scan signals, reset sandboxes, and place
            paper market orders. Not investment advice.
          </p>
        </div>
        <div className="glass flex flex-col gap-3 p-4 sm:min-w-[240px]">
          {authRequired && user && (
            <p className="text-center text-xs text-slate-500">
              <span className="font-mono text-slate-300">{user.user_id}</span>
              {user.is_admin && (
                <span className="ml-2 rounded bg-mint-500/20 px-1.5 py-0.5 text-mint-400">admin</span>
              )}
            </p>
          )}
          {user?.is_admin && (
            <button
              type="button"
              className="btn-ghost w-full justify-center text-sm"
              onClick={() => setPage("admin")}
            >
              Admin — users
            </button>
          )}
          <button
            type="button"
            className="btn-ghost w-full justify-center text-sm"
            onClick={() => setPage("settings")}
          >
            Daily pick criteria
          </button>
          {authRequired && (
            <button type="button" className="btn-ghost w-full justify-center text-xs" onClick={logout}>
              Sign out
            </button>
          )}
          <div>
            <label className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Simulation profile
            </label>
            <input
              className="input mt-1 font-mono text-sm"
              value={profile}
              onChange={(e) => setProfile(e.target.value.trim() || "default")}
              placeholder="default"
              spellCheck={false}
            />
            <p className="mt-1 text-xs text-slate-500">Separate portfolios per name — stored on the server.</p>
          </div>
        </div>
      </header>

      {err && (
        <div
          className="mb-8 rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 text-sm text-red-200"
          role="alert"
        >
          {err}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="glass p-6">
          <h2 className="font-display text-lg font-semibold text-white">Sandbox</h2>
          <p className="mt-1 text-sm text-slate-400">Reset starting cash and reload positions.</p>
          <div className="mt-5 flex flex-wrap items-end gap-3">
            <div className="min-w-[140px] flex-1">
              <label className="mb-1 block text-xs text-slate-500">Starting cash</label>
              <input
                className="input"
                value={resetCash}
                onChange={(e) => setResetCash(e.target.value)}
                inputMode="decimal"
              />
            </div>
            <button
              type="button"
              className="btn-primary"
              disabled={busy !== null}
              onClick={() =>
                run("reset", async () => {
                  const cash = Number(resetCash);
                  if (!Number.isFinite(cash) || cash <= 0) throw new Error("Invalid cash amount");
                  await apiPost("/api/simulate/reset", { profile, cash });
                  await loadStatus();
                  await loadAccount();
                })
              }
            >
              {busy === "reset" ? "Resetting…" : "Reset simulation"}
            </button>
            <button type="button" className="btn-ghost" disabled={busy !== null} onClick={() => loadStatus()}>
              Refresh status
            </button>
          </div>
          {sim && (
            <dl className="mt-6 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-slate-500">Equity</dt>
                <dd className="font-mono text-lg text-white">${formatMoney(sim.equity)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Cash</dt>
                <dd className="font-mono text-lg text-mint-400">${formatMoney(sim.cash)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">P&amp;L vs start</dt>
                <dd
                  className={`font-mono text-lg ${sim.pnl >= 0 ? "text-mint-400" : "text-red-400"}`}
                >
                  {sim.pnl >= 0 ? "+" : ""}
                  {formatMoney(sim.pnl)}
                </dd>
              </div>
            </dl>
          )}
          {sim?.positions && sim.positions.length > 0 && (
            <div className="mt-6 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-500">
                    <th className="py-2 pr-4 font-medium">Symbol</th>
                    <th className="py-2 pr-4 font-medium">Qty</th>
                    <th className="py-2 pr-4 font-medium">Last</th>
                    <th className="py-2 font-medium">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {sim.positions.map((p) => (
                    <tr key={p.symbol} className="border-b border-white/5 font-mono text-slate-200">
                      <td className="py-2 pr-4">{p.symbol}</td>
                      <td className="py-2 pr-4">{p.qty}</td>
                      <td className="py-2 pr-4">${formatMoney(p.last)}</td>
                      <td className="py-2">${formatMoney(p.market_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {sim?.last_reset && (
            <p className="mt-4 text-xs text-slate-600">Last reset: {sim.last_reset}</p>
          )}
          {!sim && !busy && (
            <p className="mt-6 text-sm text-slate-500">
              No sandbox file for this profile yet. Use <strong>Reset simulation</strong> to create one.
            </p>
          )}
        </section>

        <section className="glass p-6">
          <h2 className="font-display text-lg font-semibold text-white">Broker view (paper)</h2>
          <p className="mt-1 text-sm text-slate-400">Same profile as sandbox — cash and equity.</p>
          <button
            type="button"
            className="btn-ghost mt-5"
            disabled={busy !== null}
            onClick={() => loadAccount()}
          >
            {busy === "account" ? "Loading…" : "Refresh account"}
          </button>
          {acct && (
            <dl className="mt-6 grid grid-cols-1 gap-4 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-slate-500">Equity</dt>
                <dd className="font-mono text-xl text-white">${formatMoney(acct.equity)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Cash</dt>
                <dd className="font-mono text-xl text-mint-400">${formatMoney(acct.cash)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Buying power</dt>
                <dd className="font-mono text-xl text-slate-200">${formatMoney(acct.buying_power)}</dd>
              </div>
            </dl>
          )}
          <div className="mt-8 border-t border-white/10 pt-6">
            <h3 className="font-medium text-white">Paper market order</h3>
            <div className="mt-4 grid gap-3 sm:grid-cols-4">
              <input
                className="input sm:col-span-1"
                value={tradeSym}
                onChange={(e) => setTradeSym(e.target.value.toUpperCase())}
                placeholder="AAPL"
                aria-label="Symbol"
              />
              <select
                className="input sm:col-span-1"
                value={tradeSide}
                onChange={(e) => setTradeSide(e.target.value as "buy" | "sell")}
                aria-label="Side"
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
              <input
                className="input sm:col-span-1"
                value={tradeQty}
                onChange={(e) => setTradeQty(e.target.value)}
                inputMode="numeric"
                placeholder="Qty"
                aria-label="Quantity"
              />
              <button
                type="button"
                className="btn-primary sm:col-span-1"
                disabled={busy !== null}
                onClick={() =>
                  run("trade", async () => {
                    const qty = parseInt(tradeQty, 10);
                    if (!Number.isFinite(qty) || qty < 1) throw new Error("Invalid quantity");
                    await apiPost("/api/trade/paper", {
                      symbol: tradeSym,
                      side: tradeSide,
                      qty,
                      profile,
                    });
                    await loadStatus();
                    await loadAccount();
                  })
                }
              >
                {busy === "trade" ? "Submitting…" : "Submit"}
              </button>
            </div>
          </div>
        </section>

        <section className="glass p-6 lg:col-span-2">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="font-display text-lg font-semibold text-white">Signal scan</h2>
              <p className="mt-1 text-sm text-slate-400">
                Rule-based demo (SMA / RSI / news filter). Can take a minute for large universes.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-slate-400">
                <input
                  type="checkbox"
                  checked={scanSkipNews}
                  onChange={(e) => setScanSkipNews(e.target.checked)}
                  className="rounded border-white/20 bg-night-850 text-mint-500"
                />
                Skip news (faster)
              </label>
              <input
                className="input w-24"
                value={scanTop}
                onChange={(e) => setScanTop(e.target.value)}
                inputMode="numeric"
                aria-label="Top N symbols"
              />
              <button
                type="button"
                className="btn-primary"
                disabled={busy !== null}
                onClick={() =>
                  run("scan", async () => {
                    const top = Math.min(503, Math.max(1, parseInt(scanTop, 10) || 15));
                    const q = new URLSearchParams({
                      top: String(top),
                      skip_news: String(scanSkipNews),
                    });
                    const data = await apiGet<ScanResult>(`/api/scan?${q}`);
                    setScan(data);
                  })
                }
              >
                {busy === "scan" ? "Scanning…" : "Run scan"}
              </button>
            </div>
          </div>
          {scan && (
            <p className="mt-4 text-xs text-slate-500">
              Scanned {scan.scanned} symbols — {scan.signals.length} non-flat signals.
            </p>
          )}
          {scan && scan.signals.length > 0 && (
            <div className="mt-4 max-h-80 overflow-auto rounded-xl border border-white/10">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-night-900">
                  <tr className="border-b border-white/10 text-slate-500">
                    <th className="px-4 py-2 font-medium">Symbol</th>
                    <th className="px-4 py-2 font-medium">Side</th>
                    <th className="px-4 py-2 font-medium">Score</th>
                    <th className="px-4 py-2 font-medium">Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {scan.signals.map((s) => (
                    <tr key={s.symbol} className="border-b border-white/5">
                      <td className="px-4 py-2 font-mono font-medium text-mint-400">{s.symbol}</td>
                      <td className="px-4 py-2 uppercase text-slate-300">{s.side}</td>
                      <td className="px-4 py-2 font-mono text-slate-200">{s.score.toFixed(2)}</td>
                      <td className="px-4 py-2 text-slate-400">{s.reasons.join(" · ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {scan && scan.signals.length === 0 && (
            <p className="mt-6 text-sm text-slate-500">No signals this run — try more symbols or another day.</p>
          )}
        </section>

        <section className="glass p-6 lg:col-span-2">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="font-display text-lg font-semibold text-white">Daily technical rank</h2>
              <p className="mt-1 text-sm text-slate-400">
                Uses your saved{" "}
                <button
                  type="button"
                  className="text-mint-400 underline decoration-mint-500/50 underline-offset-2 hover:text-mint-300"
                  onClick={() => setPage("settings")}
                >
                  criteria
                </button>
                : <strong>{universeLabel(pickCriteria.universe_id)}</strong> — first{" "}
                <strong>{pickCriteria.universe_cap}</strong> symbols, top{" "}
                <strong>{pickCriteria.pick_count}</strong> after filters
                {pickCriteria.require_above_sma200 ? (
                  <>
                    , <strong>close &gt; SMA(200)</strong>
                  </>
                ) : (
                  " (no SMA(200) filter)"
                )}
                , last volume ≥ <strong>{pickCriteria.min_volume.toLocaleString()}</strong> shares
                {pickCriteria.skip_news ? ", headlines off" : ""}. Suggested prices are ATR/SMA heuristics only — not
                advice.
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-3">
              <button
                type="button"
                className="btn-primary"
                disabled={busy !== null}
                onClick={() =>
                  run("picks", async () => {
                    const data = await apiPost<DailyRecResult>(
                      "/api/recommendations/daily",
                      pickCriteria,
                    );
                    setDailyRec(data);
                  })
                }
              >
                {busy === "picks" ? "Running…" : "Get daily picks"}
              </button>
            </div>
          </div>
          {dailyRec && (
            <p className="mt-4 rounded-lg border border-amber-500/30 bg-amber-950/30 px-3 py-2 text-xs text-amber-100/90">
              {dailyRec.disclaimer}
            </p>
          )}
          {dailyRec && (
            <p className="mt-2 text-xs text-slate-500">
              Scored {dailyRec.candidates_scored} candidates from universe cap {dailyRec.universe_cap}.
            </p>
          )}
          {dailyRec && dailyRec.picks.length > 0 && (
            <p className="mt-2 text-xs text-slate-600">
              *Suggested buy ≈ pullback above SMA(200); suggested sell ≈ last close +{" "}
              {dailyRec.criteria?.sell_atr_multiplier ?? pickCriteria.sell_atr_multiplier}×ATR (capped). Not limit/stop
              advice.
            </p>
          )}
          {dailyRec && dailyRec.picks.length > 0 && (
            <div className="mt-4 max-h-96 overflow-auto rounded-xl border border-white/10">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-night-900">
                  <tr className="border-b border-white/10 text-slate-500">
                    <th className="px-4 py-2 font-medium">#</th>
                    <th className="px-4 py-2 font-medium">Symbol</th>
                    <th className="px-4 py-2 font-medium">Score</th>
                    <th className="px-4 py-2 font-medium">Last</th>
                    <th className="px-4 py-2 font-medium">Buy*</th>
                    <th className="px-4 py-2 font-medium">Sell*</th>
                    <th className="px-4 py-2 font-medium">Vol</th>
                    <th className="px-4 py-2 font-medium">SMA200</th>
                    <th className="px-4 py-2 font-medium">RSI</th>
                    <th className="px-4 py-2 font-medium">Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {dailyRec.picks.map((p, idx) => (
                    <tr key={p.symbol} className="border-b border-white/5">
                      <td className="px-4 py-2 text-slate-500">{idx + 1}</td>
                      <td className="px-4 py-2 font-mono font-medium text-mint-400">{p.symbol}</td>
                      <td className="px-4 py-2 font-mono text-slate-200">{p.score.toFixed(1)}</td>
                      <td className="px-4 py-2 font-mono text-slate-300">
                        {p.last_close != null ? formatMoney(p.last_close) : "—"}
                      </td>
                      <td className="px-4 py-2 font-mono text-mint-400">
                        {p.target_buy_price != null ? formatMoney(p.target_buy_price) : "—"}
                      </td>
                      <td className="px-4 py-2 font-mono text-amber-200/90">
                        {p.target_sell_price != null ? formatMoney(p.target_sell_price) : "—"}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-slate-400">
                        {p.volume_last != null ? Math.round(p.volume_last).toLocaleString() : "—"}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-slate-400">
                        {p.sma200 != null ? formatMoney(p.sma200) : "—"}
                      </td>
                      <td className="px-4 py-2 font-mono text-slate-300">
                        {p.rsi != null ? p.rsi.toFixed(0) : "—"}
                      </td>
                      <td className="px-4 py-2 text-slate-400">{p.reasons.join(" · ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="glass p-6 lg:col-span-2">
          <h2 className="font-display text-lg font-semibold text-white">Data</h2>
          <p className="mt-1 text-sm text-slate-400">
            Re-download the ticker list for an index (Wikipedia, Nasdaq Trader, or a third-party Russell table —
            cached under the API data directory). Russell 2000 needs a successful refresh before daily picks.
          </p>
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs text-slate-500">Universe to refresh</label>
              <select
                className="input min-w-[220px]"
                value={universeRefresh}
                onChange={(e) => setUniverseRefresh(e.target.value as PickCriteria["universe_id"])}
              >
                <option value="sp500">S&amp;P 500</option>
                <option value="dow">Dow Jones (DJIA)</option>
                <option value="nasdaq100">Nasdaq-100 (QQQ)</option>
                <option value="nasdaq">Nasdaq-listed stocks</option>
                <option value="russell2000">Russell 2000</option>
              </select>
            </div>
            <button
              type="button"
              className="btn-ghost"
              disabled={busy !== null}
              onClick={() =>
                run("universe", async () => {
                  const q = new URLSearchParams({ universe: universeRefresh });
                  const r = await apiPost<{ tickers_cached: number; universe: string }>(
                    `/api/universe/refresh?${q}`,
                  );
                  alert(`Universe ${r.universe}: cached ${r.tickers_cached} tickers.`);
                })
              }
            >
              {busy === "universe" ? "Refreshing…" : "Refresh ticker cache"}
            </button>
          </div>
        </section>
      </div>

      <footer className="mt-16 border-t border-white/10 pt-8 text-center text-xs text-slate-600">
        Educational simulation only. Markets involve risk of loss. Past patterns do not guarantee future
        results.
      </footer>
    </div>
  );
}
