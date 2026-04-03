const API = "";

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

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(await parseError(r));
  return r.json() as Promise<T>;
}

/** 404 → null (no body). Other errors throw. */
export async function apiGetOrNull<T>(path: string): Promise<T | null> {
  const r = await fetch(`${API}${path}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(await parseError(r));
  return r.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(await parseError(r));
  return r.json() as Promise<T>;
}
