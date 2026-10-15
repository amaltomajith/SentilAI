import type { InboundPayload } from './backend-client.js';

/** Minimal structural view of a Baileys message so this file is unit-testable without Baileys. */
export interface WaMessageLike {
  key: { id?: string | null; remoteJid?: string | null; fromMe?: boolean | null; senderPn?: string; remoteJidAlt?: string };
  message?: {
    conversation?: string | null;
    extendedTextMessage?: { text?: string | null } | null;
    imageMessage?: { caption?: string | null } | null;
    audioMessage?: object | null;
  } | null;
}

export const MAX_AUDIO_BYTES = 3 * 1024 * 1024;

/** Clerk user ids look like user_2abc...; anything else must never become a directory name. */
export const SAFE_USER_ID = /^[A-Za-z0-9_-]{1,64}$/;

/** Phone digits of a 1:1 chat, or null for groups/status/broadcast/unresolvable @lid ids. */
export function peerOf(msg: WaMessageLike): string | null {
  if (msg.key.fromMe) return null;
  const jid = msg.key.remoteJid ?? '';
  if (!jid || jid === 'status@broadcast' || jid.endsWith('@g.us') || jid.endsWith('@broadcast') || jid.endsWith('@newsletter')) return null;
  let id = jid;
  if (jid.endsWith('@lid')) id = msg.key.senderPn ?? msg.key.remoteJidAlt ?? '';
  if (!id.endsWith('@s.whatsapp.net')) return null;
  const digits = id.split('@')[0].split(':')[0].replace(/\D/g, '');
  return digits.length >= 8 ? digits : null;
}

export async function toInbound(msg: WaMessageLike, userId: string, targets: Set<string>,
                                download: (m: WaMessageLike) => Promise<Buffer>): Promise<InboundPayload | null> {
  const peer = peerOf(msg);
  if (!peer || !targets.has(peer) || !msg.key.id) return null;   // privacy: other contacts never leave this process
  const m = msg.message;
  if (m?.audioMessage) {
    const buf = await download(msg);
    if (buf.length > MAX_AUDIO_BYTES) return null;
    return { user_id: userId, inbound_id: msg.key.id, peer, kind: 'voice', audio_b64: buf.toString('base64'), filename: 'voice.ogg' };
  }
  const text = (m?.conversation ?? m?.extendedTextMessage?.text ?? m?.imageMessage?.caption ?? '').trim();
  return text ? { user_id: userId, inbound_id: msg.key.id, peer, kind: 'text', text } : null;
}

/** Each user's target numbers, as last reported by the backend. Unknown user => empty set (fail closed). */
export class TargetStore {
  private m = new Map<string, Set<string>>();
  replace(all: Record<string, string[]>): void {
    for (const [u, nums] of Object.entries(all)) this.m.set(u, new Set(nums));
  }
  get(userId: string): Set<string> { return this.m.get(userId) ?? new Set(); }
  has(userId: string, peer: string): boolean { return this.get(userId).has(peer); }
  forget(userId: string): void { this.m.delete(userId); }
}