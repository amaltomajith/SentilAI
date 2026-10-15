# Deploy Sentinel for free

One setup, four free services, no card:

| Part | Where | Why |
|---|---|---|
| Website | Cloudflare Pages | Static, never sleeps, loads instantly |
| API + WhatsApp connector | Render free (one Docker service, `render.yaml`) | Runs the container |
| Database + WhatsApp login | Supabase free Postgres | Render's disk is wiped on restart, so the login is stored encrypted here |
| Keep-awake | Cloudflare Worker cron (`deploy/cloudflare`) | Pings `/api/health` every 5 min so Render doesn't sleep |

If the server does sleep anyway, the site shows a "Waking the server" screen and continues by itself.

## Steps

1. **Supabase**: new project, then Connect, then **Session pooler** URL (port 5432). That is `DATABASE_URL`.
2. **Render**: New, Blueprint, pick this repo. It generates `BRIDGE_SHARED_SECRET` and `SESSION_ENC_KEY` (copy `SESSION_ENC_KEY` somewhere safe). Fill in:
   `DATABASE_URL`, `GROQ_API_KEY`, `SAMBANOVA_API_KEY`, `CLERK_ISSUER`, `PUBLIC_BASE_URL` (the service URL), `CLERK_AUTHORIZED_PARTIES` and `CORS_ORIGINS` (the Pages URL).
3. **Cloudflare Pages**: connect the repo, root directory left empty (the site is at the repo root), build `npm run build`, output `dist`. Env: `VITE_API_BASE_URL` (Render URL), `VITE_CLERK_PUBLISHABLE_KEY`.
4. **Keep-awake**: in `deploy/cloudflare`, set the Render URL in `wrangler.toml`, then `npx wrangler deploy`.
5. **Clerk**: add the Pages URL as an allowed origin; make "Password" optional so Google sign-in works.

Check: open the Pages URL, sign in, Connect page shows a QR.

## Limits

- Free Render allows ~2 linked WhatsApp accounts (`MAX_LINKED_ACCOUNTS=2`) and restarts now and then; the login survives because it is in Postgres.
- Free LLM keys are shared rate limits (~30 requests/min on Groq).
- Pinging a free Render service is a grey area in their rules; fine for a demo or small beta.
- WhatsApp can restrict unofficial clients. Use a spare number and only chat with real scam contacts.

## Alternatives (same image, no code changes)

- **Always on, no pinging**: Oracle Cloud Always Free VM: `docker compose up -d`, `AUTH_STORE=file`.
- **Your own PC**: `docker compose up`, expose with Tailscale Funnel.
