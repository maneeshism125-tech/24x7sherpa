import { clearToken, getToken } from "../authStorage";

const API = "";

function authHeaders(): Record<string, string> {
  const t = getToken();
  if (t) return { Authorization: `Bearer ${t}` };
  return {};
}

async function parseError(res: Response): Promise<string> {
  if (res.status === 502 || res.status === 503) {
    return (
      "Cannot reach the Python API on port 8000. Open a second terminal, cd into the repo, " +
      "activate your venv, run: pip install -e '.[web]' then sherpa-web — keep it running while " +
      "you use npm run dev (this page)."
    );
  }
  try {
    const j = await res.json();
    if (typeof j?.detail === "string") return j.detail;
    if (Array.isArray(j?.detail)) return j.detail.map((d: { msg?: string }) => d.msg).join("; ");
    return JSON.stringify(j);
  } catch {
    return await res.text().catch(() => res.statusText);
  }
}

function onUnauthorized(): void {
  clearToken();
  window.dispatchEvent(new CustomEvent("sherpa-auth-lost"));
}

async function handleJson<T>(res: Response): Promise<T> {
  if (res.status === 401) onUnauthorized();
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`, { headers: { ...authHeaders() } });
  return handleJson<T>(r);
}

/** 404 → null. Other errors throw; 401 clears token. */
export async function apiGetOrNull<T>(path: string): Promise<T | null> {
  const r = await fetch(`${API}${path}`, { headers: { ...authHeaders() } });
  if (r.status === 404) return null;
  return handleJson<T>(r);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handleJson<T>(r);
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handleJson<T>(r);
}

/** Public POST without Authorization (e.g. login). */
export async function apiPostPublic<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(await parseError(r));
  return r.json() as Promise<T>;
}

/** Public GET (e.g. auth config). */
export async function apiGetPublic<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(await parseError(r));
  return r.json() as Promise<T>;
}
