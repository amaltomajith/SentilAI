import { createSseParser } from './sse';
import { BackendWaking, reportReady, reportWaking } from './backend';
import type { LiveEvent } from './types';

const BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';

export class AuthError extends Error {}

type TokenProvider = () => Promise<string | null>;
let tokenProvider: TokenProvider = async () => null;
/** Set once by the auth provider (Clerk's getToken, or the dev token). Every request awaits a fresh token. */
export function setTokenProvider(p: TokenProvider): void { tokenProvider = p; }

async function headers(extra?: HeadersInit): Promise<Headers> {
  const h = new Headers(extra);
  const t = await tokenProvider();
  if (t) h.set('Authorization', `Bearer ${t}`);
  return h;
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const h = await headers(init.headers);
  let body = init.body;
  if (init.json !== undefined) { h.set('Content-Type', 'application/json'); body = JSON.stringify(init.json); }
  let r: Response;
  try { r = await fetch(BASE + path, { ...init, headers: h, body }); }
  catch (e) {
    // A sleeping host answers with a page that has no CORS headers, so the browser reports a plain network failure.
    if (e instanceof TypeError) { reportWaking(); throw new BackendWaking(); }
    throw e;
  }
  if ([502, 503, 504].includes(r.status) && !(r.headers.get('content-type') ?? '').includes('application/json')) { reportWaking(); throw new BackendWaking(); }
  reportReady();
  if (r.status === 401 || r.status === 503) {
    const txt = await r.text().catch(() => 'unauthorized');
    let msg = txt;
    try { msg = (JSON.parse(txt) as { detail?: string }).detail ?? txt; } catch { /* plain text */ }
    throw new AuthError(msg);
  }
  if (!r.ok) {
    const txt = await r.text().catch(() => '');
    let msg = txt;
    try { msg = (JSON.parse(txt) as { detail?: string }).detail ?? txt; } catch { /* plain text */ }
    throw new Error(msg || `HTTP ${r.status}`);
  }
  return r.json() as Promise<T>;
}

/** Fetches an authenticated file (the browser cannot attach a bearer token to <img>/<audio>) and returns an object URL. */
export async function fetchBlobUrl(path: string): Promise<string> {
  const r = await fetch(BASE + path, { headers: await headers() });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return URL.createObjectURL(await r.blob());
}

export async function download(path: string, filename: string): Promise<void> {
  const r = await fetch(BASE + path, { headers: await headers() });
  if (!r.ok) throw new Error(`download failed: HTTP ${r.status}`);
  const url = URL.createObjectURL(await r.blob());
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}

/** Live event stream with auto-reconnect (a fresh token on every reconnect). Returns a stop function. */
export function startStream(onEvent: (e: LiveEvent) => void, onStatus: (live: boolean) => void): () => void {
  const ctl = new AbortController();
  let delay = 1000;
  (async () => {
    while (!ctl.signal.aborted) {
      try {
        const r = await fetch(`${BASE}/api/stream`, { headers: await headers(), signal: ctl.signal });
        if (!r.ok || !r.body) throw new Error(`stream HTTP ${r.status}`);
        onStatus(true); delay = 1000;
        const parse = createSseParser(onEvent);
        const reader = r.body.pipeThrough(new TextDecoderStream()).getReader();
        for (;;) { const { value, done } = await reader.read(); if (done) break; parse(value); }
      } catch { /* fall through to reconnect */ }
      onStatus(false);
      if (ctl.signal.aborted) return;
      await new Promise((res) => setTimeout(res, delay));
      delay = Math.min(delay * 2, 15000);
    }
  })();
  return () => ctl.abort();
}