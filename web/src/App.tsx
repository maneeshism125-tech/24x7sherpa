import { useCallback, useEffect, useState } from "react";
import { AdminView } from "./AdminView";
import { useAuth } from "./AuthContext";
import { AuthEntry } from "./AuthEntry";
import { BusinessNewsView } from "./BusinessNewsView";
import { DailyRankHistoryView } from "./DailyRankHistoryView";
import { apiDelete, apiGet, apiGetOrNull, apiPost } from "./lib/api";
import { mergeDailyRankSnapshot } from "./lib/dailyRankSnapshots";
import { loadPickCriteria, type PickCriteria, universeLabel } from "./pickCriteria";
import { SettingsView } from "./SettingsView";
import { TopNav, type AppPage, type MainTab, type SettingsTab } from "./TopNav";

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

type OpenOrderRow = {
  id: string;
  symbol: string;
  side: string;
  qty: number;
  order_type: string;
  limit_price: number | null;
  stop_price: number | null;
  stop_triggered: boolean;
  status: string;
  created_at: string;
};

type TradeOrderType = "market" | "limit" | "stop" | "stop_limit";

function formatMoney(n: number) {
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export default function App() {
  const { ready, authRequired, user, err: authErr, logout } = useAuth();
  const [page, setPage] = useState<AppPage>("main");
  const [mainTab, setMainTab] = useState<MainTab>("portfolio");
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("criteria");
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
  const [tradeOrderType, setTradeOrderType] = useState<TradeOrderType>("market");
  const [tradeLimitPx, setTradeLimitPx] = useState("");
  const [tradeStopPx, setTradeStopPx] = useState("");
  const [openOrders, setOpenOrders] = useState<OpenOrderRow[]>([]);
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

  const loadOpenOrders = useCallback(async () => {
    try {
      const q = new URLSearchParams({ profile });
      const data = await apiGet<OpenOrderRow[]>(`/api/trade/paper/orders?${q}`);
      setOpenOrders(data);
    } catch {
      setOpenOrders([]);
    }
  }, [profile]);

  useEffect(() => {
    void loadStatus().catch(() => setSim(null));
    void loadAccount().catch(() => setAcct(null));
  }, [loadAccount, loadStatus]);

  useEffect(() => {
    void loadOpenOrders();
  }, [loadOpenOrders]);

  useEffect(() => {
    setUniverseRefresh(pickCriteria.universe_id);
  }, [pickCriteria.universe_id]);

  useEffect(() => {
    if (page === "settings" && settingsTab === "admin" && !user?.is_admin) {
      setSettingsTab("criteria");
    }
  }, [page, settingsTab, user?.is_admin]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white text-slate-500">
        Loading…
      </div>
    );
  }

  if (authErr) {
    return (
      <div className="mx-auto max-w-md bg-white px-4 py-16 text-center text-red-700">
        <p>{authErr}</p>
      </div>
    );
  }

  if (authRequired && !user) {
    return <AuthEntry />;
  }

  const shell = (
    <div className="min-h-screen bg-white">
      <TopNav
        page={page}
        mainTab={mainTab}
        settingsTab={settingsTab}
        onGoMain={(tab) => {
          setPage("main");
          setMainTab(tab);
        }}
        onGoNews={() => setPage("news")}
        onGoRankHistory={() => setPage("rankHistory")}
        onGoSettings={(tab) => {
          setPage("settings");
          setSettingsTab(tab);
        }}
        user={user}
        authRequired={authRequired}
        onLogout={logout}
      />

      {page === "news" && <BusinessNewsView />}

      {page === "rankHistory" && <DailyRankHistoryView />}

      {page === "settings" && (
        <>
          <div className="border-b border-slate-200 bg-slate-50/80">
            <div className="mx-auto flex max-w-6xl flex-wrap gap-2 px-4 py-3 sm:px-6 lg:px-8">
              <button
                type="button"
                className={`rounded-lg px-3 py-2 text-sm font-medium ${
                  settingsTab === "criteria"
                    ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200"
                    : "text-slate-600 hover:bg-white/80"
                }`}
                onClick={() => setSettingsTab("criteria")}
              >
                Daily pick criteria
              </button>
              {user?.is_admin && (
                <button
                  type="button"
                  className={`rounded-lg px-3 py-2 text-sm font-medium ${
                    settingsTab === "admin"
                      ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200"
                      : "text-slate-600 hover:bg-white/80"
                  }`}
                  onClick={() => setSettingsTab("admin")}
                >
                  User admin
                </button>
              )}
            </div>
          </div>
          {settingsTab === "criteria" ? (
            <SettingsView
              criteria={pickCriteria}
              onSave={(c) => {
                setPickCriteria(c);
                setPage("main");
              }}
              onCancel={() => setPage("main")}
            />
          ) : (
            user?.is_admin && <AdminView onBack={() => setSettingsTab("criteria")} />
          )}
        </>
      )}

      {page === "main" && (
        <div className="mx-auto max-w-6xl px-4 pb-24 pt-8 sm:px-6 lg:px-8">
          <header className="mb-10">
            <p className="font-display text-sm font-semibold uppercase tracking-widest text-mint-600">
              24×7 Sherpa
            </p>
            <h1 className="font-display mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
              {mainTab === "portfolio" ? "Portfolio (sandbox)" : "Paper trading"}
            </h1>
            <p className="mt-3 max-w-2xl text-sm text-slate-600">
              {mainTab === "portfolio"
                ? "Reset sandbox cash, track simulated positions, refresh index ticker caches, then scan or rank names — all on fake money. Not investment advice."
                : "Place market, limit, stop, and stop-limit paper orders on the same simulation profile as your sandbox. Not real brokerage execution."}
            </p>
          </header>

          {err && (
            <div
              className="mb-8 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
              role="alert"
            >
              {err}
            </div>
          )}

          <div className="flex flex-col gap-6">
            {mainTab === "portfolio" && (
              <>
        <section className="glass p-6 w-full min-w-0">
          <h2 className="font-display text-lg font-semibold text-slate-900">Sandbox</h2>
          <p className="mt-1 text-sm text-slate-600">Reset starting cash and reload positions.</p>
          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/90 p-4">
            <label className="text-xs font-medium uppercase tracking-wide text-slate-600">
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
                <dd className="font-mono text-lg text-slate-900">${formatMoney(sim.equity)}</dd>
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
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="py-2 pr-4 font-medium">Symbol</th>
                    <th className="py-2 pr-4 font-medium">Qty</th>
                    <th className="py-2 pr-4 font-medium">Last</th>
                    <th className="py-2 font-medium">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {sim.positions.map((p) => (
                    <tr key={p.symbol} className="border-b border-slate-100 font-mono text-slate-800">
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
              </>
            )}

            {mainTab === "paper" && (
              <section className="glass p-6 w-full min-w-0">
          <h2 className="font-display text-lg font-semibold text-slate-900">Paper trading</h2>
          <p className="mt-1 text-sm text-slate-600">
            Same simulation profile as sandbox. Fills use Yahoo&apos;s latest close per symbol plus a small
            slippage model. <strong>Limit</strong> orders execute when the quote crosses your price;
            <strong> Stop</strong> is stop-market (sell: fires when price falls to stop; buy: when it rises);{" "}
            <strong>Stop-limit</strong> arms on the stop, then rests a limit. Not real brokerage execution.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-ghost"
              disabled={busy !== null}
              onClick={() => loadAccount()}
            >
              {busy === "account" ? "Loading…" : "Refresh account"}
            </button>
            <button
              type="button"
              className="btn-ghost"
              disabled={busy !== null}
              onClick={() => void loadOpenOrders()}
            >
              Refresh working orders
            </button>
            <button
              type="button"
              className="btn-ghost"
              disabled={busy !== null}
              onClick={() =>
                run("tick", async () => {
                  await apiPost("/api/trade/paper/tick", { symbol: tradeSym.trim(), profile });
                  await loadOpenOrders();
                  await loadAccount();
                  await loadStatus();
                })
              }
            >
              {busy === "tick" ? "Updating…" : `Update quote & fills (${tradeSym || "SYM"})`}
            </button>
          </div>
          {acct && (
            <dl className="mt-6 grid grid-cols-1 gap-4 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-slate-500">Equity</dt>
                <dd className="font-mono text-xl text-slate-900">${formatMoney(acct.equity)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Cash</dt>
                <dd className="font-mono text-xl text-mint-400">${formatMoney(acct.cash)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Buying power</dt>
                <dd className="font-mono text-xl text-slate-800">${formatMoney(acct.buying_power)}</dd>
              </div>
            </dl>
          )}
          <div className="mt-8 border-t border-slate-200 pt-6">
            <h3 className="font-medium text-slate-900">Place order</h3>
            <p className="mt-1 text-xs text-slate-500">
              Market fills immediately after the quote refresh inside submit. Working orders need periodic{" "}
              <em>Update quote &amp; fills</em> (or another submit on the same symbol).
            </p>
            <div className="mt-4 flex flex-col gap-4">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <label className="mb-1 block text-xs text-slate-500">Symbol</label>
                  <input
                    className="input"
                    value={tradeSym}
                    onChange={(e) => setTradeSym(e.target.value.toUpperCase())}
                    placeholder="AAPL"
                    aria-label="Symbol"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-500">Side</label>
                  <select
                    className="input"
                    value={tradeSide}
                    onChange={(e) => setTradeSide(e.target.value as "buy" | "sell")}
                    aria-label="Side"
                  >
                    <option value="buy">Buy</option>
                    <option value="sell">Sell</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-500">Quantity</label>
                  <input
                    className="input"
                    value={tradeQty}
                    onChange={(e) => setTradeQty(e.target.value)}
                    inputMode="numeric"
                    placeholder="Shares"
                    aria-label="Quantity"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-500">Order type</label>
                  <select
                    className="input"
                    value={tradeOrderType}
                    onChange={(e) => setTradeOrderType(e.target.value as TradeOrderType)}
                    aria-label="Order type"
                  >
                    <option value="market">Market</option>
                    <option value="limit">Limit</option>
                    <option value="stop">Stop (market after trigger)</option>
                    <option value="stop_limit">Stop-limit</option>
                  </select>
                </div>
              </div>
              {(tradeOrderType === "limit" || tradeOrderType === "stop_limit") && (
                <div className="max-w-xs">
                  <label className="mb-1 block text-xs text-slate-500">Limit price</label>
                  <input
                    className="input font-mono"
                    value={tradeLimitPx}
                    onChange={(e) => setTradeLimitPx(e.target.value)}
                    inputMode="decimal"
                    placeholder="e.g. 150.00"
                  />
                </div>
              )}
              {(tradeOrderType === "stop" || tradeOrderType === "stop_limit") && (
                <div className="max-w-xs">
                  <label className="mb-1 block text-xs text-slate-500">Stop (trigger) price</label>
                  <input
                    className="input font-mono"
                    value={tradeStopPx}
                    onChange={(e) => setTradeStopPx(e.target.value)}
                    inputMode="decimal"
                    placeholder="e.g. 145.00"
                  />
                </div>
              )}
              <button
                type="button"
                className="btn-primary w-fit"
                disabled={busy !== null}
                onClick={() =>
                  run("trade", async () => {
                    const qty = parseInt(tradeQty, 10);
                    if (!Number.isFinite(qty) || qty < 1) throw new Error("Invalid quantity");
                    const body: Record<string, string | number> = {
                      symbol: tradeSym.trim(),
                      side: tradeSide,
                      qty,
                      profile,
                      order_type: tradeOrderType,
                    };
                    if (tradeOrderType === "limit" || tradeOrderType === "stop_limit") {
                      const lp = parseFloat(tradeLimitPx);
                      if (!Number.isFinite(lp) || lp <= 0) throw new Error("Enter a valid limit price");
                      body.limit_price = lp;
                    }
                    if (tradeOrderType === "stop" || tradeOrderType === "stop_limit") {
                      const sp = parseFloat(tradeStopPx);
                      if (!Number.isFinite(sp) || sp <= 0) throw new Error("Enter a valid stop price");
                      body.stop_price = sp;
                    }
                    await apiPost("/api/trade/paper", body);
                    await loadStatus();
                    await loadAccount();
                    await loadOpenOrders();
                  })
                }
              >
                {busy === "trade" ? "Submitting…" : "Submit order"}
              </button>
            </div>
          </div>
          <div className="mt-8 border-t border-slate-200 pt-6">
            <h3 className="font-medium text-slate-900">Working orders</h3>
            {openOrders.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">No open limit/stop orders for this profile.</p>
            ) : (
              <div className="mt-3 max-h-56 overflow-auto rounded-xl border border-slate-200">
                <table className="w-full text-left text-xs sm:text-sm">
                  <thead className="sticky top-0 bg-slate-100">
                    <tr className="border-b border-slate-200 text-slate-500">
                      <th className="px-3 py-2 font-medium">Symbol</th>
                      <th className="px-3 py-2 font-medium">Side</th>
                      <th className="px-3 py-2 font-medium">Type</th>
                      <th className="px-3 py-2 font-medium">Qty</th>
                      <th className="px-3 py-2 font-medium">Stop</th>
                      <th className="px-3 py-2 font-medium">Limit</th>
                      <th className="px-3 py-2 font-medium">Armed</th>
                      <th className="px-3 py-2 font-medium"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {openOrders.map((o) => (
                      <tr key={o.id} className="border-b border-slate-100 font-mono text-slate-700">
                        <td className="px-3 py-2 text-mint-400">{o.symbol}</td>
                        <td className="px-3 py-2 uppercase">{o.side}</td>
                        <td className="px-3 py-2">{o.order_type.replace("_", "-")}</td>
                        <td className="px-3 py-2">{o.qty}</td>
                        <td className="px-3 py-2">
                          {o.stop_price != null ? formatMoney(o.stop_price) : "—"}
                        </td>
                        <td className="px-3 py-2">
                          {o.limit_price != null ? formatMoney(o.limit_price) : "—"}
                        </td>
                        <td className="px-3 py-2">{o.stop_triggered ? "yes" : "—"}</td>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            className="text-amber-700 underline hover:text-amber-900"
                            disabled={busy !== null}
                            onClick={() =>
                              run(`cancel-${o.id}`, async () => {
                                const q = new URLSearchParams({ profile });
                                await apiDelete<{ ok: boolean }>(
                                  `/api/trade/paper/orders/${encodeURIComponent(o.id)}?${q}`,
                                );
                                await loadOpenOrders();
                              })
                            }
                          >
                            Cancel
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
            )}

        <section className="glass p-6 w-full min-w-0">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="font-display text-lg font-semibold text-slate-900">Signal scan</h2>
              <p className="mt-1 text-sm text-slate-600">
                Rule-based demo (SMA / RSI / news filter). Can take a minute for large universes.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={scanSkipNews}
                  onChange={(e) => setScanSkipNews(e.target.checked)}
                  className="rounded border-slate-300 bg-white text-mint-600"
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
            <div className="mt-4 max-h-80 overflow-auto rounded-xl border border-slate-200">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-slate-100">
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="px-4 py-2 font-medium">Symbol</th>
                    <th className="px-4 py-2 font-medium">Side</th>
                    <th className="px-4 py-2 font-medium">Score</th>
                    <th className="px-4 py-2 font-medium">Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {scan.signals.map((s) => (
                    <tr key={s.symbol} className="border-b border-slate-100">
                      <td className="px-4 py-2 font-mono font-medium text-mint-700">{s.symbol}</td>
                      <td className="px-4 py-2 uppercase text-slate-700">{s.side}</td>
                      <td className="px-4 py-2 font-mono text-slate-800">{s.score.toFixed(2)}</td>
                      <td className="px-4 py-2 text-slate-600">{s.reasons.join(" · ")}</td>
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

        <section className="glass p-6 w-full min-w-0">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="font-display text-lg font-semibold text-slate-900">Daily technical rank</h2>
              <p className="mt-1 text-sm text-slate-600">
                Uses your saved{" "}
                <button
                  type="button"
                  className="text-mint-700 underline decoration-mint-500/50 underline-offset-2 hover:text-mint-600"
                  onClick={() => {
                    setPage("settings");
                    setSettingsTab("criteria");
                  }}
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
                    mergeDailyRankSnapshot({
                      picks: data.picks,
                      disclaimer: data.disclaimer,
                      universe_cap: data.universe_cap,
                      candidates_scored: data.candidates_scored,
                      criteria: data.criteria,
                    });
                  })
                }
              >
                {busy === "picks" ? "Running…" : "Get daily picks"}
              </button>
            </div>
          </div>
          {dailyRec && (
            <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
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
            <div className="mt-4 max-h-96 overflow-auto rounded-xl border border-slate-200">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-slate-100">
                  <tr className="border-b border-slate-200 text-slate-500">
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
                    <tr key={p.symbol} className="border-b border-slate-100">
                      <td className="px-4 py-2 text-slate-500">{idx + 1}</td>
                      <td className="px-4 py-2 font-mono font-medium text-mint-700">{p.symbol}</td>
                      <td className="px-4 py-2 font-mono text-slate-800">{p.score.toFixed(1)}</td>
                      <td className="px-4 py-2 font-mono text-slate-700">
                        {p.last_close != null ? formatMoney(p.last_close) : "—"}
                      </td>
                      <td className="px-4 py-2 font-mono text-mint-700">
                        {p.target_buy_price != null ? formatMoney(p.target_buy_price) : "—"}
                      </td>
                      <td className="px-4 py-2 font-mono text-amber-800">
                        {p.target_sell_price != null ? formatMoney(p.target_sell_price) : "—"}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-slate-600">
                        {p.volume_last != null ? Math.round(p.volume_last).toLocaleString() : "—"}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-slate-600">
                        {p.sma200 != null ? formatMoney(p.sma200) : "—"}
                      </td>
                      <td className="px-4 py-2 font-mono text-slate-700">
                        {p.rsi != null ? p.rsi.toFixed(0) : "—"}
                      </td>
                      <td className="px-4 py-2 text-slate-600">{p.reasons.join(" · ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

            {mainTab === "portfolio" && (
        <section className="glass p-6 w-full min-w-0">
          <h2 className="font-display text-lg font-semibold text-slate-900">Data</h2>
          <p className="mt-1 text-sm text-slate-600">
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
            )}
      </div>
        </div>
      )}

      <footer className="mt-12 border-t border-slate-200 py-8 text-center text-xs text-slate-500">
        Educational simulation only. Markets involve risk of loss. Past patterns do not guarantee future
        results.
      </footer>
    </div>
  );

  return shell;
}
