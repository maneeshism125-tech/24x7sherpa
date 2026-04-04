import { useCallback, useEffect, useState } from "react";
import {
  DAILY_RANK_SNAPSHOTS_STORAGE_KEY,
  lastNDateKeys,
  loadDailyRankSnapshots,
  type DailyRankSnapshot,
} from "./lib/dailyRankSnapshots";
import { universeLabel } from "./pickCriteria";

function formatMoney(n: number) {
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatDayHeading(dateKey: string): string {
  const [y, m, d] = dateKey.split("-").map((x) => parseInt(x, 10));
  if (!y || !m || !d) return dateKey;
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString(undefined, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function PicksTable({
  snap,
  dateKey,
}: {
  snap: DailyRankSnapshot;
  dateKey: string;
}) {
  const mult = snap.criteria?.sell_atr_multiplier ?? 1;
  if (snap.picks.length === 0) {
    return <p className="mt-3 text-sm text-slate-500">No picks passed filters for this run.</p>;
  }
  return (
    <>
      <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
        {snap.disclaimer}
      </p>
      <p className="mt-2 text-xs text-slate-500">
        Scored {snap.candidates_scored} candidates from universe cap {snap.universe_cap}.
      </p>
      <p className="mt-2 text-xs text-slate-600">
        *Suggested buy ≈ pullback above SMA(200); suggested sell ≈ last close + {mult}×ATR (capped). Not limit/stop
        advice.
      </p>
      <div
        id={`rank-detail-${dateKey}`}
        className="mt-4 max-h-[28rem] overflow-auto rounded-xl border border-slate-200"
      >
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
            {snap.picks.map((p, idx) => (
              <tr key={`${dateKey}-${p.symbol}`} className="border-b border-slate-100">
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
    </>
  );
}

export function DailyRankHistoryView() {
  const [snapshots, setSnapshots] = useState<Record<string, DailyRankSnapshot>>(() =>
    loadDailyRankSnapshots(),
  );
  const [openKey, setOpenKey] = useState<string | null>(null);

  const sync = useCallback(() => setSnapshots(loadDailyRankSnapshots()), []);

  useEffect(() => {
    sync();
    const onStorage = (e: StorageEvent) => {
      if (e.key === null || e.key === DAILY_RANK_SNAPSHOTS_STORAGE_KEY) sync();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [sync]);

  const weekKeys = lastNDateKeys(7);

  useEffect(() => {
    const keys = lastNDateKeys(7);
    const m = window.location.hash.match(/^#rank-(\d{4}-\d{2}-\d{2})$/);
    if (m && keys.includes(m[1])) setOpenKey(m[1]);
  }, []);

  useEffect(() => {
    if (!openKey) return;
    const t = window.setTimeout(() => {
      document.getElementById(`rank-detail-${openKey}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
    return () => window.clearTimeout(t);
  }, [openKey]);

  const selectDay = (dateKey: string) => {
    setOpenKey(dateKey);
    window.history.replaceState(null, "", `#rank-${dateKey}`);
  };

  return (
    <div className="mx-auto max-w-6xl px-4 pb-24 pt-10 sm:px-6 lg:px-8">
      <header className="mb-10">
        <p className="font-display text-sm font-semibold uppercase tracking-widest text-mint-600">
          Daily technical rank
        </p>
        <h1 className="font-display mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Last seven days
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">
          Each day links to a saved snapshot from when you ran <strong>Get daily picks</strong> on the Trading page
          (stored in this browser). Days without a run show as empty. Not investment advice.
        </p>
      </header>

      <ul className="flex flex-col gap-3">
        {weekKeys.map((dateKey) => {
          const snap = snapshots[dateKey];
          return (
            <li key={dateKey}>
              <div className="glass flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="font-display text-base font-semibold text-slate-900">{formatDayHeading(dateKey)}</p>
                  <p className="mt-0.5 font-mono text-xs text-slate-500">{dateKey}</p>
                  {snap?.criteria && (
                    <p className="mt-1 text-xs text-slate-600">
                      Universe: {universeLabel(snap.criteria.universe_id)} · top {snap.criteria.pick_count} picks
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  {snap ? (
                    <a
                      href={`#rank-${dateKey}`}
                      className="btn-primary inline-flex text-sm no-underline"
                      onClick={(e) => {
                        e.preventDefault();
                        selectDay(dateKey);
                      }}
                      aria-expanded={openKey === dateKey}
                    >
                      {openKey === dateKey ? "Showing results" : "View technical rank"}
                    </a>
                  ) : (
                    <span className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                      No saved run
                    </span>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      {openKey && snapshots[openKey] && (
        <section className="glass mt-8 w-full min-w-0 p-6" aria-live="polite">
          <h2 className="font-display text-lg font-semibold text-slate-900">
            {formatDayHeading(openKey)}
          </h2>
          <PicksTable snap={snapshots[openKey]} dateKey={openKey} />
        </section>
      )}
    </div>
  );
}
