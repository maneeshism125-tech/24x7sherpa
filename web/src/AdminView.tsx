import { useCallback, useEffect, useState } from "react";
import { useAuth } from "./AuthContext";
import { apiGet, apiPatch, apiPost } from "./lib/api";

type UserRow = {
  user_id: string;
  is_admin: boolean;
  disabled: boolean;
  created_at: number;
  email: string | null;
  address: string | null;
};

type Props = {
  onBack: () => void;
};

export function AdminView({ onBack }: Props) {
  const { user } = useAuth();
  const [rows, setRows] = useState<UserRow[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [newId, setNewId] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newAddress, setNewAddress] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newAdmin, setNewAdmin] = useState(false);

  const load = useCallback(async () => {
    setErr(null);
    const data = await apiGet<UserRow[]>("/api/admin/users");
    setRows(data);
  }, []);

  useEffect(() => {
    void load().catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, [load]);

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setErr(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-4 pb-24 pt-10 sm:px-6 lg:px-8">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-display text-sm font-semibold uppercase tracking-widest text-mint-500">
            Admin
          </p>
          <h1 className="font-display mt-2 text-3xl font-bold tracking-tight text-white">
            User accounts
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Signed in as <span className="font-mono text-slate-200">{user?.user_id}</span>. Users can also
            self-register when signup is enabled. Data lives in{" "}
            <code className="text-slate-500">data/users.sqlite</code>.
          </p>
        </div>
        <button type="button" className="btn-ghost" onClick={onBack}>
          Back to app
        </button>
      </header>

      {err && (
        <div
          className="mb-6 rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 text-sm text-red-200"
          role="alert"
        >
          {err}
        </div>
      )}

      <section className="glass mb-8 p-6">
        <h2 className="font-display text-base font-semibold text-white">Create user (manual)</h2>
        <p className="mt-1 text-xs text-slate-500">
          Optional email/address. User id: letters, digits, underscore (3–32). Password ≥ 8.
        </p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <div className="min-w-[120px]">
            <label className="mb-1 block text-xs text-slate-500">User id</label>
            <input
              className="input font-mono text-sm"
              value={newId}
              onChange={(e) => setNewId(e.target.value)}
              spellCheck={false}
            />
          </div>
          <div className="min-w-[180px] flex-1">
            <label className="mb-1 block text-xs text-slate-500">Email (optional)</label>
            <input
              className="input text-sm"
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
            />
          </div>
          <div className="min-w-[200px] flex-1">
            <label className="mb-1 block text-xs text-slate-500">Address (optional)</label>
            <input
              className="input text-sm"
              value={newAddress}
              onChange={(e) => setNewAddress(e.target.value)}
              placeholder="Mailing address"
            />
          </div>
          <div className="min-w-[120px]">
            <label className="mb-1 block text-xs text-slate-500">Password</label>
            <input
              className="input text-sm"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-400">
            <input
              type="checkbox"
              checked={newAdmin}
              onChange={(e) => setNewAdmin(e.target.checked)}
              className="rounded border-white/20 bg-night-850 text-mint-500"
            />
            Admin
          </label>
          <button
            type="button"
            className="btn-primary"
            disabled={busy !== null}
            onClick={() =>
              run("create", async () => {
                const body: Record<string, unknown> = {
                  user_id: newId.trim(),
                  password: newPassword,
                  is_admin: newAdmin,
                };
                const em = newEmail.trim();
                if (em) body.email = em;
                const ad = newAddress.trim();
                if (ad) body.address = ad;
                await apiPost<UserRow>("/api/admin/users", body);
                setNewId("");
                setNewEmail("");
                setNewAddress("");
                setNewPassword("");
                setNewAdmin(false);
              })
            }
          >
            {busy === "create" ? "Creating…" : "Create"}
          </button>
        </div>
      </section>

      <section className="glass overflow-x-auto p-6">
        <h2 className="font-display text-base font-semibold text-white">All users</h2>
        <table className="mt-4 w-full min-w-[900px] text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 text-slate-500">
              <th className="py-2 pr-3 font-medium">User id</th>
              <th className="py-2 pr-3 font-medium">Email</th>
              <th className="py-2 pr-3 font-medium">Address</th>
              <th className="py-2 pr-3 font-medium">Admin</th>
              <th className="py-2 pr-3 font-medium">Disabled</th>
              <th className="py-2 font-medium">Update</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <UserEditRow key={r.user_id} row={r} busy={busy} onRun={run} selfId={user?.user_id ?? ""} />
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function clip(s: string | null, n: number) {
  if (!s) return "—";
  return s.length <= n ? s : `${s.slice(0, n)}…`;
}

function UserEditRow({
  row,
  busy,
  onRun,
  selfId,
}: {
  row: UserRow;
  busy: string | null;
  onRun: (label: string, fn: () => Promise<void>) => Promise<void>;
  selfId: string;
}) {
  const [pw, setPw] = useState("");
  const [em, setEm] = useState(row.email ?? "");
  const [addr, setAddr] = useState(row.address ?? "");
  const [adm, setAdm] = useState(row.is_admin);
  const [dis, setDis] = useState(row.disabled);

  useEffect(() => {
    setAdm(row.is_admin);
    setDis(row.disabled);
    setEm(row.email ?? "");
    setAddr(row.address ?? "");
  }, [row.is_admin, row.disabled, row.user_id, row.email, row.address]);

  const label = `patch-${row.user_id}`;
  return (
    <tr className="border-b border-white/5 align-top">
      <td className="py-3 pr-3 font-mono text-mint-400">{row.user_id}</td>
      <td className="max-w-[140px] py-3 pr-3 text-xs text-slate-400" title={row.email ?? ""}>
        {clip(row.email, 24)}
      </td>
      <td className="max-w-[160px] py-3 pr-3 text-xs text-slate-400" title={row.address ?? ""}>
        {clip(row.address, 32)}
      </td>
      <td className="py-3 pr-3">
        <input
          type="checkbox"
          checked={adm}
          onChange={(e) => setAdm(e.target.checked)}
          className="rounded border-white/20 bg-night-850 text-mint-500"
          aria-label={`Admin ${row.user_id}`}
        />
      </td>
      <td className="py-3 pr-3">
        <input
          type="checkbox"
          checked={dis}
          onChange={(e) => setDis(e.target.checked)}
          className="rounded border-white/20 bg-night-850 text-mint-500"
          aria-label={`Disabled ${row.user_id}`}
        />
      </td>
      <td className="py-3">
        <div className="flex min-w-[280px] flex-col gap-2">
          <input
            className="input text-xs"
            type="email"
            placeholder="Email"
            value={em}
            onChange={(e) => setEm(e.target.value)}
          />
          <textarea
            className="input min-h-[52px] resize-y text-xs"
            placeholder="Address"
            value={addr}
            onChange={(e) => setAddr(e.target.value)}
            maxLength={512}
          />
          <div className="flex flex-wrap items-center gap-2">
            <input
              className="input max-w-[140px] text-xs"
              type="password"
              placeholder="New password"
              value={pw}
              onChange={(e) => setPw(e.target.value)}
            />
            <button
              type="button"
              className="btn-ghost text-xs"
              disabled={busy !== null}
              onClick={() =>
                onRun(label, async () => {
                  const body: Record<string, unknown> = {
                    is_admin: adm,
                    disabled: dis,
                    email: em.trim() ? em.trim() : null,
                    address: addr.trim() ? addr.trim() : null,
                  };
                  if (pw.trim().length > 0) {
                    if (pw.length < 8) throw new Error("Password must be at least 8 characters");
                    body.password = pw;
                  }
                  await apiPatch<UserRow>(`/api/admin/users/${encodeURIComponent(row.user_id)}`, body);
                  setPw("");
                })
              }
            >
              {busy === label ? "Saving…" : "Save"}
            </button>
            {row.user_id === selfId && <span className="text-xs text-slate-600">(you)</span>}
          </div>
        </div>
      </td>
    </tr>
  );
}
