import { useState } from "react";
import { useAuth } from "./AuthContext";

type Props = {
  onCreateAccount?: () => void;
};

export function LoginView({ onCreateAccount }: Props) {
  const { login } = useAuth();
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="glass w-full max-w-md p-8">
        <p className="font-display text-sm font-semibold uppercase tracking-widest text-mint-600">
          24×7 Sherpa
        </p>
        <h1 className="font-display mt-2 text-2xl font-bold text-slate-900">Sign in</h1>
        <p className="mt-2 text-sm text-slate-600">
          {onCreateAccount ? (
            <>
              Sign in with your user id and password. New here? Use{" "}
              <button
                type="button"
                className="text-mint-700 underline decoration-mint-500/50 underline-offset-2 hover:text-mint-600"
                onClick={onCreateAccount}
              >
                Create account
              </button>
              . The first server user is still               <code className="text-slate-800">admin</code> /{" "}
              <code className="text-slate-800">changeme</code> unless bootstrap password is set.
            </>
          ) : (
            <>
              Public signup is turned off — use an account from your administrator. First deploy:{" "}
              <code className="text-slate-800">admin</code> / <code className="text-slate-800">changeme</code>{" "}
              unless <code className="text-slate-800">SHERPA_BOOTSTRAP_ADMIN_PASSWORD</code> is set.
            </>
          )}
        </p>
        {err && (
          <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {err}
          </p>
        )}
        <form
          className="mt-6 space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setErr(null);
            setBusy(true);
            try {
              await login(userId, password);
            } catch (ex) {
              setErr(ex instanceof Error ? ex.message : String(ex));
            } finally {
              setBusy(false);
            }
          }}
        >
          <div>
            <label className="mb-1 block text-xs text-slate-500">User id</label>
            <input
              className="input font-mono"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              autoComplete="username"
              spellCheck={false}
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Password</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          <button type="submit" className="btn-primary w-full" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        {onCreateAccount && (
          <p className="mt-4 text-center text-xs text-slate-600">
            By creating an account you confirm your details are accurate. This tool is for educational use
            only.
          </p>
        )}
      </div>
    </div>
  );
}
