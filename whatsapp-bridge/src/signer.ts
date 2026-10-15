import { createHash, createHmac, randomBytes } from 'node:crypto';

/** Must stay byte-for-byte compatible with backend/sentinel/security: sign(). */
export function sign(secret: string, method: string, path: string, ts: number, nonce: string, body: Buffer | string): string {
  const bodyHash = createHash('sha256').update(body).digest('hex');
  const msg = [method.toUpperCase(), path, String(ts), nonce, bodyHash].join('\n');
  return createHmac('sha256', secret).update(msg).digest('hex');
}

export function signedHeaders(secret: string, method: string, path: string, body: Buffer | string,
                              nowMs: number = Date.now(), nonce: string = randomBytes(12).toString('hex')): Record<string, string> {
  const ts = Math.floor(nowMs / 1000);
  return {
    'X-Bridge-Timestamp': String(ts),
    'X-Bridge-Nonce': nonce,
    'X-Bridge-Signature': sign(secret, method, path, ts, nonce, body),
    'Content-Type': 'application/json',
  };
}