import { useSyncExternalStore } from 'react';

const BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';

/** The API host is asleep or restarting (free hosts spin down). Never shown to people as an error. */
export class BackendWaking extends Error {
  constructor() { super('backend is waking up'); }
}

type Status = 'checking' | 'ready' | 'waking';
let status: Status = 'checking';
let since = Date.now();
const listeners = new Set<() => void>();
const set = (s: Status) => { if (s !== status) { status = s; if (s !== 'ready') since = Date.now(); listeners.forEach((l) => l()); } };

export const reportWaking = () => set('waking');
export const reportReady = () => set('ready');
export const backendStatus = () => ({ status, since });

/** Fire-and-forget: starts a sleeping host while the visitor is still reading the page. Throttled to once a minute. */
let lastWake = 0;
export function wakeBackend(): void {
  if (Date.now() - lastWake < 60_000) return;
  lastWake = Date.now();
  try { void fetch(`${BASE}/api/health`, { mode: 'no-cors', cache: 'no-store' }).catch(() => undefined); } catch { /* ignore */ }
}

/** One health probe. True only for our own healthy JSON answer (not a host's "starting up" page). */
export async function probeHealth(timeoutMs = 8000): Promise<boolean> {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(`${BASE}/api/health`, { cache: 'no-store', signal: ctl.signal, headers: { Accept: 'application/json' } });
    if (!r.ok) return false;
    const j = (await r.json()) as { ok?: boolean };
    return j.ok === true;
  } catch { return false; } finally { clearTimeout(t); }
}

/** Polls until the backend answers, with gentle backoff. Returns a stop function. */
export function watchBackend(): () => void {
  let stopped = false;
  let delay = 1500;
  const loop = async () => {
    while (!stopped) {
      if (await probeHealth()) { reportReady(); return; }
      if (status !== 'waking') set('waking');
      await new Promise((r) => setTimeout(r, delay));
      delay = Math.min(delay * 1.4, 6000);
    }
  };
  void loop();
  return () => { stopped = true; };
}

export function useBackendStatus() {
  return useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l); }, () => status);
}

/** Test helper. */
export function resetBackendStatus(): void { status = 'checking'; since = Date.now(); listeners.forEach((l) => l()); }