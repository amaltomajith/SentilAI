# Deploying Sentinel for free

Facts below were checked in October 2026 against provider docs where available. Free tiers change, so confirm anything that matters on the provider's own pricing page.

## What a host must provide
1. A process that **stays up**, holding one outbound WhatsApp connection per linked user. WhatsApp queues messages while it is offline, but nothing wakes a sleeping host when one arrives, so a sleeping host means late replies.
2. WhatsApp login that **survives restarts**: files on a disk (`AUTH_STORE=file`) or an encrypted copy in Postgres (`AUTH_STORE=db`).
3. About 250 MB for the API, 80 MB for the connector and about 60 MB per linked account.
4. Public HTTPS for the web app (CORS and the live event stream) and a Postgres or a disk for SQLite.

## Choose a path
| | A. Free, no card, no hardware | B. Dependable free VM | C. Your own machine |
|---|---|---|---|
| Web app | Cloudflare Pages | Cloudflare Pages | Cloudflare Pages |
| API + WhatsApp | Render free web service (one container) | Oracle Always Free VM, same container | Docker on a PC or Raspberry Pi |
| Database | Supabase free Postgres | SQLite on the VM disk (or Supabase) | SQLite on disk |
| WhatsApp login | `AUTH_STORE=db` (required) | `AUTH_STORE=file` | `AUTH_STORE=file` |
| Stays awake | Cloudflare Worker pings every 5 min | always on | as long as the machine is on |
| Public URL | `*.onrender.com` | Caddy plus a domain | Tailscale Funnel (`*.ts.net`) |
| Main risks | cold start, restarts, 512 MB, host says "not for production" | card for signup, no free capacity, idle reclaim | machine off means app off |
| Account-ban risk | higher (datacenter IP) | higher (datacenter IP) | lowest (home IP) |

Out: Fly.io (no free tier for new accounts), Koyeb (sleeps, 0.1 vCPU), Railway (one-time trial credit), Hugging Face Spaces (Docker Spaces need a paid plan), Google Cloud Run (CPU is throttled between requests, so a held WhatsApp connection is unreliable).

All three run the **same container image** built from the root `Dockerfile`. You can move between them without code changes.

## Path A: Cloudflare Pages + Render + Supabase
1. **Supabase**: create a free project. Settings > Database > Connection string > **Session pooler** (port 5432, IPv4). Free projects are IPv6 only on the direct host, so do not use that one. Copy the URL (it looks like `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`). The container runs the migrations itself on start.
2. **Render**: New > Blueprint > pick this GitHub repo (it reads `render.yaml`). Fill the variables marked in the dashboard:
   - `DATABASE_URL` = the Supabase URL above
   - `GROQ_API_KEY` (and the optional SambaNova or OpenRouter keys)
   - `CLERK_ISSUER` = `https://<your-instance>.clerk.accounts.dev`
   - `CLERK_AUTHORIZED_PARTIES` and `CORS_ORIGINS` = your Pages URL (step 3)
   - `PUBLIC_BASE_URL` = the service URL Render shows
   - Copy the generated `SESSION_ENC_KEY` somewhere safe. Losing it logs everyone out of WhatsApp.
3. **Cloudflare Pages**: Workers & Pages > Create > Pages > connect the repo. Build command `npm run build`, output `dist`. Environment variables: `VITE_CLERK_PUBLISHABLE_KEY` and `VITE_API_BASE_URL=https://<your-service>.onrender.com`. `public/_redirects` already makes deep links work.
4. **Clerk** (dashboard): add the Pages URL as an allowed origin. A development instance is free but capped (about 100 users) and not meant for production. A production instance needs a domain you own.
5. **Keep it awake (only if WhatsApp must stay connected)**: `cd deploy/cloudflare`, edit `TARGET_URL` in `wrangler.toml`, `npx wrangler deploy`. It pings `/api/health` every 5 minutes. One always-awake free service uses about 744 of the 750 free hours a month, so you can run only one. Render's docs say free services are not for production, and pinging is a grey area, so treat this as a demo or small beta.

### What visitors see when the free host is asleep
- The landing page is static on Cloudflare, so it loads instantly. It also sends a background request that starts the API while the visitor reads.
- Signing in with Clerk does not need our server.
- If the API is still starting, the app shows a "Waking the server" screen that continues by itself (about a minute). Network failures and host loading pages are treated as "waking", never as errors. If the host goes to sleep mid-session, a banner appears and the page keeps what you typed.
- After a restart the WhatsApp connector reconnects using the encrypted login in Postgres, so nobody has to scan again. Messages that arrived while it was down are delivered by WhatsApp and answered once (recent ones only).

## Path B: Oracle Always Free VM
Verified in Oracle's docs: Ampere A1 is now 2 OCPU and 12 GB (it used to be 4 and 24), you can also have two AMD Micro VMs (1 GB RAM each), 200 GB disk, 10 TB outbound a month. Instances Oracle judges idle for 7 days (CPU p95 under 20% and network under 20%, and memory under 20% on A1) **may be reclaimed**. The docs page does not describe signup verification; other sources say a card is required for verification. Free A1 capacity is often "out of stock".
1. Create a VM (Ubuntu), open ports 80 and 443 in the VCN security list and the instance firewall.
2. `curl -fsSL https://get.docker.com | sh`, then clone the repo, `cp deploy/.env.example .env`, fill it (`AUTH_STORE=file`, leave `DATABASE_URL` empty for SQLite).
3. Point a domain's A record at the VM, edit `deploy/Caddyfile`, then `docker compose --profile https up -d --build`.
4. Set the web app's `VITE_API_BASE_URL` to `https://your-domain` and add it to `CORS_ORIGINS` and `CLERK_AUTHORIZED_PARTIES`.
Google Cloud e2-micro works the same way (1 GB RAM, 1 GB outbound a month, US regions only, card required).

## Path C: your own machine
1. Install Docker (Docker Desktop on Windows). `cp deploy/.env.example .env`, fill it, `docker compose up -d --build`.
2. Expose it with **Tailscale Funnel** (free, stable `*.ts.net` HTTPS name, available on all plans, beta): install Tailscale, enable MagicDNS and HTTPS in the admin console, then `tailscale funnel 8000`. A Cloudflare Tunnel also works but a stable name needs a domain; quick tunnels change URL on every restart.
3. Deploy the web app on Cloudflare Pages as in Path A with `VITE_API_BASE_URL` set to your `*.ts.net` URL.
4. Disable sleep on the machine. A home IP is the safest choice for WhatsApp.

## Day two
- **Update**: Render redeploys on every push to `main`. VM or home: `git pull && docker compose up -d --build`.
- **Backups**: SQLite lives in the `sentinel_data` volume and WhatsApp login in `sentinel_wa` (Path B and C): back both up. Path A: the Supabase database holds everything, and the free plan has no backups, so run `pg_dump` now and then.
- **Re-linking**: if someone is logged out, they press "Link my WhatsApp" again in Connect.
- **Logs**: Render dashboard, or `docker compose logs -f sentinel`.
- **Checks**: `GET /api/health` returns `{"ok": true, ...}`. CI builds the image, boots it and runs the migrations plus an API smoke test against real Postgres on every push.

## Limits to tell your users
- Free LLM tiers are shared by everyone (Groq is roughly 30 requests a minute), so keep `MAX_LINKED_ACCOUNTS` small (2 on Render, 5 elsewhere).
- WhatsApp does not allow unofficial clients, so linked accounts can be restricted, and datacenter IPs are riskier than a home IP. Use a secondary number and run it as an invite-only beta.
- With `AUTH_STORE=db`, a database leak **plus** `SESSION_ENC_KEY` would allow takeover of linked WhatsApp accounts. The key lives only in the host's environment and the blobs are bound to their user and name.