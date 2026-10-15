import { join } from 'node:path';
import { existsSync, readdirSync, rmSync } from 'node:fs';
import {
  makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore, downloadMediaMessage, type WASocket,
} from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import pino from 'pino';
import type { Config } from './config.js';
import type { AccountState, BackendClient, Command } from './backend-client.js';
import { SAFE_USER_ID, TargetStore, toInbound, type WaMessageLike } from './inbound.js';

const MAX_RECONNECTS = 10;

type State = AccountState['state'];

/** One user's WhatsApp account. Credentials live in <sessionDir>/<userId>/ and never leave this process. */
export class WhatsAppLink {
  sock: WASocket | null = null;
  state: State = 'connecting';
  qr: string | null = null;
  pairingCode: string | null = null;
  me: string | null = null;
  dead = false;
  private attempts = 0;
  private log;

  constructor(readonly userId: string, private cfg: Config, private backend: BackendClient, private targets: TargetStore) {
    if (!SAFE_USER_ID.test(userId)) throw new Error('unsafe user id');
    this.log = pino({ level: cfg.logLevel, name: `wa:${userId.slice(-6)}` });
  }

  get dir(): string { return join(this.cfg.sessionDir, this.userId); }
  get connected(): boolean { return this.state === 'open'; }

  snapshot(): AccountState {
    return { user_id: this.userId, state: this.state, ...(this.qr ? { qr: this.qr } : {}), ...(this.pairingCode ? { pairing_code: this.pairingCode } : {}), ...(this.me ? { me: this.me } : {}) };
  }

  async start(): Promise<void> {
    if (this.dead) return;
    const { state, saveCreds } = await useMultiFileAuthState(this.dir);
    const { version } = await fetchLatestBaileysVersion();
    const quiet = pino({ level: 'silent' }) as never;
    const sock = makeWASocket({
      version, logger: quiet, printQRInTerminal: false, syncFullHistory: false, markOnlineOnConnect: false,
      auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, quiet) },
      getMessage: async () => undefined,
    });
    this.sock = sock;

    sock.ev.on('creds.update', saveCreds);
    sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
      if (this.dead || this.sock !== sock) return;
      if (qr) { this.state = 'qr'; this.qr = qr; }
      if (connection === 'connecting' && this.state !== 'qr') this.state = 'connecting';
      if (connection === 'open') {
        this.attempts = 0; this.state = 'open'; this.qr = null; this.pairingCode = null;
        this.me = (sock.user?.id ?? '').split(':')[0].split('@')[0].replace(/\D/g, '') || null;
        this.log.info('connected');
      }
      if (connection === 'close') {
        const code = (lastDisconnect?.error as Boom | undefined)?.output?.statusCode;
        if (code === DisconnectReason.loggedOut) {   // unlinked from the phone: forget credentials; the user links again from the dashboard
          this.log.warn('logged out from the phone; credentials removed');
          this.state = 'logged_out'; this.qr = null; this.pairingCode = null; this.me = null;
          this.wipe();
          return;
        }
        this.state = 'connecting';
        if (++this.attempts > MAX_RECONNECTS) { this.log.error('too many reconnect attempts; giving up'); this.state = 'logged_out'; this.dead = true; return; }
        const delay = Math.min(2000 * 2 ** (this.attempts - 1), 60_000);
        this.log.warn({ code, delay }, 'connection closed; reconnecting');
        setTimeout(() => this.start().catch((e) => this.log.error(e)), delay);
      }
    });

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
      if (type !== 'notify') return;
      for (const m of messages) {
        try {
          const payload = await toInbound(m as unknown as WaMessageLike, this.userId, this.targets.get(this.userId), async (wm) =>
            (await downloadMediaMessage(wm as never, 'buffer', {}, { logger: quiet, reuploadRequest: sock.updateMediaMessage })) as Buffer);
          if (!payload) continue;
          const res = await this.backend.postInbound(payload);
          this.log.info({ kind: payload.kind, action: res.action }, 'forwarded to backend');
        } catch (e) {
          this.log.error({ err: String((e as Error)?.message ?? e) }, 'forward failed (message dropped, never answered locally)');
        }
      }
    });
  }

  /** Phone-number linking (for people who only have the phone the account lives on). Valid only while unpaired. */
  async requestPairingCode(phone: string): Promise<void> {
    if (!this.sock || this.state !== 'qr') throw new Error('not waiting to be linked');
    this.pairingCode = await this.sock.requestPairingCode(phone.replace(/\D/g, ''));
  }

  /** Unlink on WhatsApp's side and delete this user's credentials. */
  async logout(): Promise<void> {
    this.dead = true;
    try { await this.sock?.logout(); } catch { /* already unlinked */ }
    this.close();
    this.wipe();
  }

  close(): void {
    this.dead = true;
    try { this.sock?.end(undefined); } catch { /* ignore */ }
  }

  private wipe(): void {
    try { rmSync(this.dir, { recursive: true, force: true }); } catch { /* ignore */ }
  }
}

/** All users' links in one process. Each user is isolated: own socket, own credentials directory, own target list. */
export class LinkManager {
  readonly links = new Map<string, WhatsAppLink>();
  readonly targets = new TargetStore();
  private log;

  constructor(private cfg: Config, private backend: BackendClient) { this.log = pino({ level: cfg.logLevel, name: 'links' }); }

  /** Reconnect every user who linked before this process started. */
  async restore(): Promise<void> {
    if (!existsSync(this.cfg.sessionDir)) return;
    for (const d of readdirSync(this.cfg.sessionDir, { withFileTypes: true })) {
      if (d.isDirectory() && SAFE_USER_ID.test(d.name) && existsSync(join(this.cfg.sessionDir, d.name, 'creds.json'))) await this.ensure(d.name);
    }
  }

  async ensure(userId: string): Promise<WhatsAppLink> {
    let l = this.links.get(userId);
    if (!l || l.dead) {
      l = new WhatsAppLink(userId, this.cfg, this.backend, this.targets);
      this.links.set(userId, l);
      await l.start();
    }
    return l;
  }

  getSock(userId: string): WASocket | null {
    const l = this.links.get(userId);
    return l && l.connected ? l.sock : null;
  }

  snapshot(): AccountState[] { return [...this.links.values()].map((l) => l.snapshot()); }

  async apply(cmd: Command): Promise<void> {
    if (!SAFE_USER_ID.test(cmd.user_id)) return;
    if (cmd.type === 'link') await this.ensure(cmd.user_id);
    else if (cmd.type === 'pairing_code' && cmd.phone) await (await this.ensure(cmd.user_id)).requestPairingCode(cmd.phone).catch((e) => this.log.warn({ err: String(e?.message ?? e) }, 'pairing code failed'));
    else if (cmd.type === 'logout') {
      await this.links.get(cmd.user_id)?.logout();
      this.links.delete(cmd.user_id);
      this.targets.forget(cmd.user_id);
    }
  }

  /** Accounts that reported logged_out have been told to the backend once; drop them so the user can start fresh. */
  prune(): void {
    for (const [u, l] of this.links) if (l.state === 'logged_out' && l.dead) this.links.delete(u);
  }
}