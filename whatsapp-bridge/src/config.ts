/** Strict env loading. The bridge refuses to start without a strong shared secret: auth is not optional. */
export interface Config {
  backendUrl: string;
  secret: string;
  sessionDir: string;
  logLevel: string;
  pollMs: number;
  humanDelay: boolean;
  heartbeatFile: string;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const backendUrl = (env.BACKEND_URL ?? '').trim().replace(/\/$/, '');
  const secret = (env.BRIDGE_SHARED_SECRET ?? '').trim();
  if (!backendUrl) throw new Error('BACKEND_URL is required');
  if (!/^https?:\/\//.test(backendUrl)) throw new Error('BACKEND_URL must start with http:// or https://');
  if (secret.length < 32) throw new Error('BRIDGE_SHARED_SECRET is required and must be at least 32 characters');
  return {
    backendUrl,
    secret,
    sessionDir: (env.WA_SESSION_DIR ?? './wa_session').trim(),
    logLevel: (env.LOG_LEVEL ?? 'info').trim(),
    pollMs: Math.max(500, parseInt(env.POLL_INTERVAL_MS ?? '2000', 10) || 2000),
    humanDelay: (env.HUMAN_DELAY ?? '1') !== '0',
    heartbeatFile: (env.HEARTBEAT_FILE ?? '/tmp/bridge.heartbeat').trim(),
  };
}