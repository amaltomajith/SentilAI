import { writeFileSync } from 'node:fs';
import pino from 'pino';
import { loadConfig } from './config.js';
import { BackendClient } from './backend-client.js';
import { LinkManager } from './whatsapp.js';
import { OutboundWorker } from './worker.js';

try { process.loadEnvFile('.env'); } catch { /* no .env file: rely on real environment variables (Docker, CI) */ }
const cfg = (() => {
  try { return loadConfig(); } catch (e) { console.error(`[bridge] ${(e as Error).message}`); process.exit(1); }
})();
const log = pino({ level: cfg.logLevel, name: 'bridge' });
const backend = new BackendClient(cfg.backendUrl, cfg.secret);
const links = new LinkManager(cfg, backend);
const worker = new OutboundWorker(backend, (userId) => links.getSock(userId) as never, {
  humanDelay: cfg.humanDelay,
  isTarget: async (userId, peer) => links.targets.has(userId, peer),
  connectedUsers: () => [...links.links.values()].filter((l) => l.connected).map((l) => l.userId),
});

await links.restore();

let stopping = false;
let lastSync = 0;
async function sync(): Promise<void> {
  if (Date.now() - lastSync < 3000) return;
  lastSync = Date.now();
  const res = await backend.sync(links.snapshot());
  links.targets.replace(res.targets);
  for (const c of res.commands) await links.apply(c);
  links.prune();
}

(async function loop() {
  while (!stopping) {
    try { await sync(); } catch (e) { log.warn({ err: String((e as Error)?.message ?? e) }, 'sync failed'); }
    try {
      if (await worker.tick()) continue;
    } catch (e) {
      log.warn({ err: String((e as Error)?.message ?? e) }, 'outbox poll failed');
    }
    try { writeFileSync(cfg.heartbeatFile, String(Date.now())); } catch { /* heartbeat is best-effort */ }
    await new Promise((r) => setTimeout(r, cfg.pollMs));
  }
})();

for (const s of ['SIGINT', 'SIGTERM'] as const) process.on(s, () => { stopping = true; log.info('shutting down'); process.exit(0); });