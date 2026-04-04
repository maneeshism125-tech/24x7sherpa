import { useEffect, useRef, useState } from "react";

export type AppPage = "main" | "news" | "rankHistory" | "settings";
export type MainTab = "portfolio" | "paper";
export type SettingsTab = "criteria" | "admin";

type Props = {
  page: AppPage;
  mainTab: MainTab;
  settingsTab: SettingsTab;
  onGoMain: (tab: MainTab) => void;
  onGoNews: () => void;
  onGoRankHistory: () => void;
  onGoSettings: (tab: SettingsTab) => void;
  user: { user_id: string; is_admin: boolean } | null;
  authRequired: boolean;
  onLogout: () => void;
};

export function TopNav({
  page,
  mainTab,
  settingsTab,
  onGoMain,
  onGoNews,
  onGoRankHistory,
  onGoSettings,
  user,
  authRequired,
  onLogout,
}: Props) {
  const [open, setOpen] = useState<null | "trading" | "settings">(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  /** Avoid "admin" twice when the login id is already `admin` and the role pill says admin. */
  const showAdminBadge = (u: NonNullable<Props["user"]>) =>
    u.is_admin && u.user_id.trim().toLowerCase() !== "admin";

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(null);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const navBtn =
    "rounded-lg px-3 py-2 text-sm font-medium text-night-950/85 transition hover:bg-night-950/10 hover:text-night-950";
  const navBtnActive = "bg-night-950/15 text-night-950 font-semibold";
  const dropPanel =
    "absolute left-0 top-full z-50 mt-1 min-w-[200px] rounded-xl border border-mint-600/30 bg-white py-1 shadow-lg shadow-mint-900/10";

  return (
    <header className="sticky top-0 z-50 border-b border-mint-600/50 bg-mint-500 backdrop-blur-md">
      <div
        ref={wrapRef}
        className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8"
      >
        <div className="flex flex-wrap items-center gap-1 sm:gap-2">
          <button
            type="button"
            className="font-display text-base font-bold tracking-tight text-night-950 sm:text-lg"
            onClick={() => {
              setOpen(null);
              onGoMain("portfolio");
            }}
          >
            24×7 Sherpa
          </button>
          <span className="hidden text-night-950/35 sm:inline" aria-hidden>
            |
          </span>

          <div className="relative">
            <button
              type="button"
              className={`${navBtn} ${open === "trading" ? navBtnActive : ""}`}
              aria-expanded={open === "trading"}
              aria-haspopup="true"
              onClick={() => setOpen((o) => (o === "trading" ? null : "trading"))}
            >
              Trading ▾
            </button>
            {open === "trading" && (
              <div className={dropPanel} role="menu">
                <button
                  type="button"
                  role="menuitem"
                  className={`block w-full px-4 py-2.5 text-left text-sm ${
                    page === "main" && mainTab === "portfolio"
                      ? "bg-mint-500/10 font-medium text-mint-700"
                      : "text-slate-700 hover:bg-slate-50"
                  }`}
                  onClick={() => {
                    setOpen(null);
                    onGoMain("portfolio");
                  }}
                >
                  Portfolio
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className={`block w-full px-4 py-2.5 text-left text-sm ${
                    page === "main" && mainTab === "paper"
                      ? "bg-mint-500/10 font-medium text-mint-700"
                      : "text-slate-700 hover:bg-slate-50"
                  }`}
                  onClick={() => {
                    setOpen(null);
                    onGoMain("paper");
                  }}
                >
                  Paper trading
                </button>
              </div>
            )}
          </div>

          <button
            type="button"
            className={`${navBtn} ${page === "news" ? navBtnActive : ""}`}
            onClick={() => {
              setOpen(null);
              onGoNews();
            }}
          >
            Business news
          </button>

          <button
            type="button"
            className={`${navBtn} ${page === "rankHistory" ? navBtnActive : ""}`}
            onClick={() => {
              setOpen(null);
              onGoRankHistory();
            }}
          >
            Daily technical rank
          </button>

          <div className="relative">
            <button
              type="button"
              className={`${navBtn} ${open === "settings" ? navBtnActive : ""} ${
                page === "settings" ? "ring-1 ring-night-950/25" : ""
              }`}
              aria-expanded={open === "settings"}
              aria-haspopup="true"
              onClick={() => setOpen((o) => (o === "settings" ? null : "settings"))}
            >
              Settings ▾
            </button>
            {open === "settings" && (
              <div className={dropPanel} role="menu">
                <button
                  type="button"
                  role="menuitem"
                  className={`block w-full px-4 py-2.5 text-left text-sm ${
                    page === "settings" && settingsTab === "criteria"
                      ? "bg-mint-500/10 font-medium text-mint-700"
                      : "text-slate-700 hover:bg-slate-50"
                  }`}
                  onClick={() => {
                    setOpen(null);
                    onGoSettings("criteria");
                  }}
                >
                  Daily pick criteria
                </button>
                {user?.is_admin && (
                  <button
                    type="button"
                    role="menuitem"
                    className={`block w-full px-4 py-2.5 text-left text-sm ${
                      page === "settings" && settingsTab === "admin"
                        ? "bg-mint-500/10 font-medium text-mint-700"
                        : "text-slate-700 hover:bg-slate-50"
                    }`}
                    onClick={() => {
                      setOpen(null);
                      onGoSettings("admin");
                    }}
                  >
                    User admin
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          {authRequired && user && (
            <span className="max-w-[140px] truncate font-mono text-xs text-night-950/65 sm:max-w-[200px]">
              {user.user_id}
              {showAdminBadge(user) && (
                <span className="ml-1.5 rounded bg-night-950/15 px-1.5 py-0.5 font-medium text-night-950">
                  admin
                </span>
              )}
            </span>
          )}
          {authRequired && (
            <button
              type="button"
              className="rounded-lg px-3 py-2 text-xs font-medium text-night-950/90 ring-1 ring-night-950/25 transition hover:bg-night-950/10"
              onClick={onLogout}
            >
              Sign out
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
