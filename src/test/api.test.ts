import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, AuthError, setTokenProvider } from '@/lib/api';

const reply = (status: number, body: unknown = {}) => vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })));
const sentHeaders = () => ((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit).headers as Headers;

describe('api client auth', () => {
  afterEach(() => { vi.unstubAllGlobals(); setTokenProvider(async () => null); });

  it('attaches a fresh bearer token from the provider on every call', async () => {
    let n = 0;
    setTokenProvider(async () => `tok${++n}`);
    reply(200, { ok: 1 });
    await api('/api/x');
    expect(sentHeaders().get('Authorization')).toBe('Bearer tok1');
    reply(200, { ok: 1 });
    await api('/api/x');
    expect(sentHeaders().get('Authorization')).toBe('Bearer tok2');
  });

  it('sends no Authorization header when signed out', async () => {
    setTokenProvider(async () => null);
    reply(200);
    await api('/api/x');
    expect(sentHeaders().get('Authorization')).toBeNull();
  });

  it('turns 401 and 503 into AuthError and other failures into a readable message', async () => {
    reply(401, { detail: 'sign in required' });
    await expect(api('/api/x')).rejects.toBeInstanceOf(AuthError);
    reply(503, { detail: 'auth is not configured on the server' });
    await expect(api('/api/x')).rejects.toBeInstanceOf(AuthError);
    reply(422, { detail: 'number must include the country code' });
    await expect(api('/api/x')).rejects.toThrow('number must include the country code');
  });
});