import { useState } from "react";
import { useAuth } from "./AuthContext";

type Props = {
  onBack: () => void;
};

export function SignUpView({ onBack }: Props) {
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [userId, setUserId] = useState("");
  const [address, setAddress] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <div className="glass w-full max-w-md p-8">
        <p className="font-display text-sm font-semibold uppercase tracking-widest text-mint-600">
          24×7 Sherpa
        </p>
        <h1 className="font-display mt-2 text-2xl font-bold text-slate-900">Create account</h1>
        <p className="mt-2 text-sm text-slate-600">
          Choose a user id (letters, numbers, underscore), your email, mailing address, and a password
          (8+ characters). You will be signed in after registering.
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
            if (password !== password2) {
              setErr("Passwords do not match.");
              return;
            }
            if (password.length < 8) {
              setErr("Password must be at least 8 characters.");
              return;
            }
            if (address.trim().length < 4) {
              setErr("Please enter a full address (at least 4 characters).");
              return;
            }
            setBusy(true);
            try {
              await register({
                email: email.trim(),
                user_id: userId.trim(),
                address: address.trim(),
                password,
              });
            } catch (ex) {
              setErr(ex instanceof Error ? ex.message : String(ex));
            } finally {
              setBusy(false);
            }
          }}
        >
          <div>
            <label className="mb-1 block text-xs text-slate-500">Email</label>
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">User id</label>
            <input
              className="input font-mono"
              value={userId}
              onChange={(e) => setUserId(e.target.value.replace(/[^a-zA-Z0-9_]/g, ""))}
              autoComplete="username"
              spellCheck={false}
              minLength={3}
              maxLength={32}
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Address</label>
            <textarea
              className="input min-h-[88px] resize-y font-sans text-sm"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              autoComplete="street-address"
              maxLength={512}
              required
              placeholder="Street, city, region, postal code…"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Password</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Confirm password</label>
            <input
              className="input"
              type="password"
              value={password2}
              onChange={(e) => setPassword2(e.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </div>
          <button type="submit" className="btn-primary w-full" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
          </button>
          <button type="button" className="btn-ghost mt-2 w-full text-sm" onClick={onBack}>
            Back to sign in
          </button>
        </form>
      </div>
    </div>
  );
}
