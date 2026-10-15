import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { api, AuthError, setTokenProvider } from '@/lib/api';
import { BackendWaking, backendStatus, probeHealth, resetBackendStatus, wakeBackend } from '@/lib/backend';
import { ApiGate } from '@/components/ApiGate';

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('cold start handling', () => {
  beforeEach(() => { resetBackendStatus(); setTokenProvider(async () => null); });
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

  it('a network or CORS failure (what a sleeping host looks like) becomes BackendWaking, not an error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(api('/api/x')).rejects.toBeInstanceOf(BackendWaking);
    expect(backendStatus().status).toBe('waking');
  });

  it('a host loading page (502/503/504 without JSON) is waking, but our own JSON 503 is not', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>starting</html>', { status: 503, headers: { 'content-type': 'text/html' } })));
    await expect(api('/api/x')).rejects.toBeInstanceOf(BackendWaking);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(503, { detail: 'auth is not configured on the server' })));
    await expect(api('/api/x')).rejects.toBeInstanceOf(AuthError);                    // control: a real server answer is never mistaken for sleep
  });

  it('a normal answer marks the backend ready', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(200, { ok: 1 })));
    await api('/api/x');
    expect(backendStatus().status).toBe('ready');
  });

  it('probeHealth is true only for our healthy JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(200, { ok: true })));
    expect(await probeHealth()).toBe(true);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>wait</html>', { status: 200 })));
    expect(await probeHealth()).toBe(false);
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('x')));
    expect(await probeHealth()).toBe(false);
  });

  it('wakeBackend sends one no-cors request and is throttled', () => {
    const f = vi.fn().mockResolvedValue(new Response(''));
    vi.stubGlobal('fetch', f);
    vi.useFakeTimers(); vi.setSystemTime(new Date('2030-01-01T00:00:00Z'));
    wakeBackend(); wakeBackend();
    expect(f).toHaveBeenCalledTimes(1);
    expect((f.mock.calls[0][1] as RequestInit).mode).toBe('no-cors');
  });

  it('the gate shows the waking screen while the server sleeps, then continues by itself', async () => {
    vi.useFakeTimers();
    let up = false;
    vi.stubGlobal('fetch', vi.fn(async () => (up ? json(200, { ok: true }) : Promise.reject(new TypeError('sleeping')))));
    render(<ApiGate><p>the app</p></ApiGate>);
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    expect(screen.getByRole('status').textContent).toMatch(/Waking the server/);
    expect(screen.queryByText('the app')).toBeNull();
    up = true;
    await act(async () => { await vi.advanceTimersByTimeAsync(7000); });
    expect(screen.getByText('the app')).toBeTruthy();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('a healthy server never flashes the waking screen', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn(async () => json(200, { ok: true })));
    render(<ApiGate><p>the app</p></ApiGate>);
    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    expect(screen.getByText('the app')).toBeTruthy();
    expect(screen.queryByText(/Waking the server/)).toBeNull();
  });
});

describe('mid-session sleep', () => {
  it('after the app has loaded once, a sleeping host shows a banner and keeps the page mounted', async () => {
    resetBackendStatus();
    vi.useFakeTimers();
    let up = true;
    vi.stubGlobal('fetch', vi.fn(async () => (up ? json(200, { ok: true }) : Promise.reject(new TypeError('sleeping')))));
    render(<ApiGate><input aria-label="draft" /></ApiGate>);
    await act(async () => { await vi.advanceTimersByTimeAsync(100); });
    const input = screen.getByLabelText('draft') as HTMLInputElement;
    input.value = 'half-typed text';
    up = false;
    await act(async () => { setTokenProvider(async () => null); try { await api('/api/x'); } catch { /* waking */ } });
    expect(screen.getByRole('status').textContent).toMatch(/Reconnecting/);
    expect((screen.getByLabelText('draft') as HTMLInputElement).value).toBe('half-typed text');   // not remounted, nothing lost
    vi.useRealTimers(); vi.unstubAllGlobals();
  });
});