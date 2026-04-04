import { useState, type ReactNode } from "react";
import type { PickCriteria } from "./pickCriteria";
import { DEFAULT_PICK_CRITERIA, savePickCriteria, UNIVERSE_OPTIONS } from "./pickCriteria";

type Props = {
  criteria: PickCriteria;
  onSave: (c: PickCriteria) => void;
  onCancel: () => void;
};

export function SettingsView({ criteria, onSave, onCancel }: Props) {
  const [c, setC] = useState<PickCriteria>({ ...criteria });

  const set =
    <K extends keyof PickCriteria>(key: K) =>
    (v: PickCriteria[K]) =>
      setC((prev) => ({ ...prev, [key]: v }));

  return (
    <div className="mx-auto max-w-4xl px-4 pb-24 pt-10 sm:px-6 lg:px-8">
      <header className="mb-10">
        <p className="font-display text-sm font-semibold uppercase tracking-widest text-mint-600">
          Settings
        </p>
        <h1 className="font-display mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Daily pick criteria
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">
          These values tune filters and the rule-based score (RSI band, volume surge, headline penalty,
          suggested sell distance). Saved in this browser only. Not investment advice.
        </p>
      </header>

      <div className="glass space-y-8 p-6">
        <section>
          <h2 className="font-display text-base font-semibold text-slate-900">Universe &amp; output</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label="Index / exchange list">
              <select
                className="input"
                value={c.universe_id}
                onChange={(e) => set("universe_id")(e.target.value as PickCriteria["universe_id"])}
              >
                {UNIVERSE_OPTIONS.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Symbols to score (first N from that list)">
              <input
                className="input"
                type="number"
                min={20}
                max={3500}
                value={c.universe_cap}
                onChange={(e) => set("universe_cap")(parseInt(e.target.value, 10) || 20)}
              />
            </Field>
            <Field label="How many top names to return">
              <input
                className="input"
                type="number"
                min={1}
                max={25}
                value={c.pick_count}
                onChange={(e) => set("pick_count")(parseInt(e.target.value, 10) || 1)}
              />
            </Field>
            <Field label="Min history bars (need ≥200 for SMA(200))">
              <input
                className="input"
                type="number"
                min={200}
                max={400}
                value={c.min_bars}
                onChange={(e) => set("min_bars")(parseInt(e.target.value, 10) || 200)}
              />
            </Field>
            <Field label="Min last-session volume (shares)">
              <input
                className="input"
                type="number"
                min={0}
                step={1000}
                value={c.min_volume}
                onChange={(e) => set("min_volume")(parseFloat(e.target.value) || 0)}
              />
            </Field>
            <label className="flex cursor-pointer items-center gap-3 text-sm text-slate-700 sm:col-span-2">
              <input
                type="checkbox"
                checked={c.skip_news}
                onChange={(e) => set("skip_news")(e.target.checked)}
                className="rounded border-slate-300 bg-white text-mint-600"
              />
              Skip news (faster; no headline penalty)
            </label>
            <label className="flex cursor-pointer items-center gap-3 text-sm text-slate-700 sm:col-span-2">
              <input
                type="checkbox"
                checked={c.require_above_sma200}
                onChange={(e) => set("require_above_sma200")(e.target.checked)}
                className="rounded border-slate-300 bg-white text-mint-600"
              />
              Require close &gt; SMA(200) to enter the ranked set
            </label>
          </div>
        </section>

        <section className="border-t border-slate-200 pt-8">
          <h2 className="font-display text-base font-semibold text-slate-900">Scoring bands</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label="RSI neutral band — low">
              <input
                className="input"
                type="number"
                min={0}
                max={100}
                step={1}
                value={c.rsi_band_low}
                onChange={(e) => set("rsi_band_low")(parseFloat(e.target.value) || 0)}
              />
            </Field>
            <Field label="RSI neutral band — high">
              <input
                className="input"
                type="number"
                min={0}
                max={100}
                step={1}
                value={c.rsi_band_high}
                onChange={(e) => set("rsi_band_high")(parseFloat(e.target.value) || 0)}
              />
            </Field>
            <Field label="RSI overbought (penalty above this)">
              <input
                className="input"
                type="number"
                min={50}
                max={100}
                step={1}
                value={c.rsi_overbought}
                onChange={(e) => set("rsi_overbought")(parseFloat(e.target.value) || 50)}
              />
            </Field>
            <Field label="Volume vs 20d avg — surge ratio for bonus">
              <input
                className="input"
                type="number"
                min={1}
                max={5}
                step={0.05}
                value={c.volume_surge_ratio}
                onChange={(e) => set("volume_surge_ratio")(parseFloat(e.target.value) || 1)}
              />
            </Field>
            <Field label="ATR/price for “elevated” bonus (e.g. 0.015 = 1.5%)">
              <input
                className="input"
                type="number"
                min={0.001}
                max={0.1}
                step={0.001}
                value={c.atr_elevated_pct}
                onChange={(e) => set("atr_elevated_pct")(parseFloat(e.target.value) || 0.015)}
              />
            </Field>
            <Field label="Headline penalty (score points subtracted)">
              <input
                className="input"
                type="number"
                min={0}
                max={100}
                step={1}
                value={c.news_penalty}
                onChange={(e) => set("news_penalty")(parseFloat(e.target.value) || 0)}
              />
            </Field>
            <Field label="Suggested sell: ATR multiple above last close">
              <input
                className="input"
                type="number"
                min={0.1}
                max={5}
                step={0.1}
                value={c.sell_atr_multiplier}
                onChange={(e) => set("sell_atr_multiplier")(parseFloat(e.target.value) || 1)}
              />
            </Field>
          </div>
        </section>

        <div className="flex flex-wrap gap-3 border-t border-slate-200 pt-6">
          <button
            type="button"
            className="btn-primary"
            onClick={() => {
              savePickCriteria(c);
              onSave(c);
            }}
          >
            Save &amp; back
          </button>
          <button type="button" className="btn-ghost" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="btn-ghost"
            onClick={() => setC({ ...DEFAULT_PICK_CRITERIA })}
          >
            Reset form to defaults
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs text-slate-500">{label}</label>
      {children}
    </div>
  );
}
