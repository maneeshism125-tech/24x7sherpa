import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { clearToken, getToken, setToken } from "./authStorage";
import { apiGetPublic, apiGet, apiPostPublic } from "./lib/api";

export type AuthUser = {
  user_id: string;
  is_admin: boolean;
  email?: string | null;
  address?: string | null;
};

type AuthContextValue = {
  ready: boolean;
  authRequired: boolean;
  allowSignup: boolean;
  user: AuthUser | null;
  err: string | null;
  login: (userId: string, password: string) => Promise<void>;
  register: (p: {
    email: string;
    user_id: string;
    address: string;
    password: string;
  }) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [authRequired, setAuthRequired] = useState(true);
  const [allowSignup, setAllowSignup] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refreshMe = useCallback(async () => {
    const t = getToken();
    if (!t) {
      setUser(null);
      return;
    }
    try {
      const me = await apiGet<AuthUser>("/api/auth/me");
      setUser(me);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cfg = await apiGetPublic<{
          auth_required: boolean;
          allow_signup: boolean;
        }>("/api/auth/config");
        if (cancelled) return;
        setAuthRequired(cfg.auth_required);
        setAllowSignup(cfg.allow_signup);
        if (!cfg.auth_required) {
          setUser({ user_id: "local", is_admin: true });
          setReady(true);
          return;
        }
        await refreshMe();
      } catch {
        if (!cancelled) setErr("Could not load auth configuration from the API.");
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshMe]);

  useEffect(() => {
    const onLost = () => setUser(null);
    window.addEventListener("sherpa-auth-lost", onLost);
    return () => window.removeEventListener("sherpa-auth-lost", onLost);
  }, []);

  const login = useCallback(async (userId: string, password: string) => {
    setErr(null);
    const r = await apiPostPublic<{ access_token: string }>("/api/auth/login", {
      user_id: userId.trim(),
      password,
    });
    setToken(r.access_token);
    await refreshMe();
  }, [refreshMe]);

  const register = useCallback(
    async (p: { email: string; user_id: string; address: string; password: string }) => {
      setErr(null);
      const r = await apiPostPublic<{ access_token: string }>("/api/auth/register", {
        email: p.email.trim(),
        user_id: p.user_id.trim(),
        address: p.address.trim(),
        password: p.password,
      });
      setToken(r.access_token);
      await refreshMe();
    },
    [refreshMe],
  );

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      ready,
      authRequired,
      allowSignup,
      user,
      err,
      login,
      register,
      logout,
      refreshMe,
    }),
    [ready, authRequired, allowSignup, user, err, login, register, logout, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
