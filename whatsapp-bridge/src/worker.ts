import type { BackendClient, OutboundJob } from './backend-client.js';

export interface SendSocket {
  sendMessage(jid: string, content: Record<string, unknown>): Promise<unknown>;
  sendPresenceUpdate?(type: 'composing' | 'paused', jid: string): Promise<unknown>;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Sends exactly what the backend approved. Leases a job, sends it, acks it. At-most-once by design. */
export class OutboundWorker {
  constructor(private client: BackendClient, private getSock: (userId: string) => SendSocket | null,
              private opts: { humanDelay: boolean; sleepFn?: (ms: number) => Promise<void>; rand?: () => number;
                              /** Send-side privacy guard: only ever message numbers the operator added as targets. */
                              isTarget?: (userId: string, peer: string) => Promise<boolean>;
                              /** Users whose WhatsApp is connected right now: the backend only leases jobs for these. */
                              connectedUsers?: () => string[] } = { humanDelay: false }) {}

  /** @returns true if a job was processed (so the caller can immediately poll again) */
  async tick(): Promise<boolean> {
    const users = this.opts.connectedUsers?.();
    if (users && users.length === 0) return false;
    const job = await this.client.nextJob(users);
    if (!job) return false;
    try {
      const sock = this.getSock(job.user_id);
      if (!sock) throw new Error('that user is not linked right now; job not sent');
      if (this.opts.isTarget && !(await this.opts.isTarget(job.user_id, job.peer))) throw new Error('peer is not a target number; refusing to send');
      await this.send(sock, job);
      await this.client.ack(job.id, true);
    } catch (e) {
      await this.client.ack(job.id, false, String((e as Error)?.message ?? e).slice(0, 200)).catch(() => undefined);
    }
    return true;
  }

  private async send(sock: SendSocket, job: OutboundJob): Promise<void> {
    const jid = `${job.peer}@s.whatsapp.net`;
    const sl = this.opts.sleepFn ?? sleep;
    if (this.opts.humanDelay) {
      await sock.sendPresenceUpdate?.('composing', jid);
      await sl(1200 + Math.floor((this.opts.rand ?? Math.random)() * 2300));
    }
    if (job.kind === 'text') {
      if (!job.payload.text) throw new Error('empty text job');
      await sock.sendMessage(jid, { text: job.payload.text });
    } else if (job.kind === 'image') {
      const buf = await this.client.media(job.payload.sha256 ?? '');
      await sock.sendMessage(jid, { image: buf, caption: job.payload.caption ?? '' });
    } else if (job.kind === 'voice') {
      const buf = await this.client.media(job.payload.sha256 ?? '');
      await sock.sendMessage(jid, { audio: buf, ptt: Boolean(job.payload.ptt), mimetype: job.payload.mime ?? 'audio/ogg; codecs=opus' });
    } else {
      throw new Error(`unknown job kind ${(job as OutboundJob).kind}`);
    }
    if (this.opts.humanDelay) await sock.sendPresenceUpdate?.('paused', jid);
  }
}