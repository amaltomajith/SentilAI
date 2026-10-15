import { signedHeaders } from './signer.js';

export interface InboundPayload {
  user_id: string;
  inbound_id: string;
  peer: string;
  kind: 'text' | 'voice';
  text?: string;
  audio_b64?: string;
  filename?: string;
}

export interface OutboundJob {
  id: string;
  user_id: string;
  peer: string;
  kind: 'text' | 'image' | 'voice';
  payload: { text?: string; sha256?: string; mime?: string; ptt?: boolean; caption?: string };
}

export interface AccountState {
  user_id: string;
  state: 'connecting' | 'qr' | 'open' | 'logged_out';
  qr?: string;
  pairing_code?: string;
  me?: string;
}

export interface Command { user_id: string; type: 'link' | 'logout' | 'pairing_code'; phone?: string }
export interface SyncResult { commands: Command[]; targets: Record<string, string[]> }

type FetchFn = typeof fetch;

/** The ONLY thing the bridge says to the backend. Every call is HMAC-signed with timestamp + nonce. */
export class BackendClient {
  constructor(private baseUrl: string, private secret: string, private fetchImpl: FetchFn = fetch) {}

  private async req(method: 'GET' | 'POST', path: string, body?: unknown): Promise<Response> {
    const raw = body === undefined ? '' : JSON.stringify(body);
    return this.fetchImpl(this.baseUrl + path, {
      method,
      headers: signedHeaders(this.secret, method, path, raw),
      body: method === 'POST' ? raw : undefined,
      signal: AbortSignal.timeout(30_000),
    });
  }

  async postInbound(p: InboundPayload): Promise<{ accepted: boolean; action?: string }> {
    const r = await this.req('POST', '/bridge/inbound', p);
    if (!r.ok) throw new Error(`backend inbound ${r.status}`);
    return r.json() as Promise<{ accepted: boolean; action?: string }>;
  }

  /** Heartbeat + state report for every linked account. Returns queued per-user commands and each user's target numbers. */
  async sync(accounts: AccountState[]): Promise<SyncResult> {
    const r = await this.req('POST', '/bridge/sync', { accounts });
    if (!r.ok) throw new Error(`backend sync ${r.status}`);
    return r.json() as Promise<SyncResult>;
  }

  /** Encrypted auth store (AUTH_STORE=db). The backend encrypts at rest; this channel is HMAC-signed. */
  async authGet(userId: string, names: string[]): Promise<Record<string, string | null>> {
    const r = await this.req('POST', '/bridge/auth/get', { user_id: userId, names });
    if (!r.ok) throw new Error(`backend auth get ${r.status}`);
    return ((await r.json()) as { items: Record<string, string | null> }).items;
  }

  async authSet(userId: string, items: Record<string, string | null>): Promise<void> {
    const r = await this.req('POST', '/bridge/auth/set', { user_id: userId, items });
    if (!r.ok) throw new Error(`backend auth set ${r.status}`);
  }

  async authUsers(): Promise<string[]> {
    const r = await this.req('POST', '/bridge/auth/users', {});
    if (!r.ok) throw new Error(`backend auth users ${r.status}`);
    return ((await r.json()) as { users: string[] }).users;
  }

  async authWipe(userId: string): Promise<void> {
    const r = await this.req('POST', '/bridge/auth/wipe', { user_id: userId });
    if (!r.ok) throw new Error(`backend auth wipe ${r.status}`);
  }

  async nextJob(users?: string[]): Promise<OutboundJob | null> {
    const r = await this.req('POST', '/bridge/outbox/next', { users: users ?? [] });
    if (!r.ok) throw new Error(`backend outbox ${r.status}`);
    return ((await r.json()) as { job: OutboundJob | null }).job;
  }

  async ack(id: string, ok: boolean, error = ''): Promise<void> {
    const r = await this.req('POST', `/bridge/outbox/${id}/ack`, { ok, error });
    if (!r.ok) throw new Error(`backend ack ${r.status}`);
  }

  async media(sha: string): Promise<Buffer> {
    const r = await this.req('GET', `/bridge/media/${sha}`);
    if (!r.ok) throw new Error(`backend media ${r.status}`);
    return Buffer.from(await r.arrayBuffer());
  }
}