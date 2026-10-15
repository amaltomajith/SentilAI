// Cloudflare Worker: pings the API on a schedule so a free host does not spin down while WhatsApp must stay connected.
// Deploy:  cd deploy/cloudflare && npx wrangler deploy      (set TARGET_URL in wrangler.toml first)
// Cost: free (5 cron triggers and 100k requests/day on the Workers free plan; this uses about 288 requests/day).
// Note: some hosts frown on keep-alive pings on free plans. Use it for a demo or small beta, and remove the cron to let the service sleep.
export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(ping(env.TARGET_URL));
  },
  // Visiting the Worker URL shows the last result (handy for checking that it works).
  async fetch(_req, env) {
    const r = await ping(env.TARGET_URL);
    return new Response(JSON.stringify(r, null, 2), { headers: { 'content-type': 'application/json' } });
  },
};

async function ping(url) {
  const started = Date.now();
  try {
    const res = await fetch(url, { cf: { cacheTtl: 0 }, signal: AbortSignal.timeout(25000), headers: { 'user-agent': 'sentinel-keepwarm/1' } });
    return { url, status: res.status, ms: Date.now() - started, at: new Date().toISOString() };
  } catch (e) {
    return { url, error: String(e), ms: Date.now() - started, at: new Date().toISOString() };
  }
}