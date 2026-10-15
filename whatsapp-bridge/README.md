# whatsapp-bridge

Authenticated transport between WhatsApp (Baileys) and the Sentinel backend. **No AI, no HTTP listener.** One bridge process serves many users: one WhatsApp socket per signed-in user.

- Every call to the backend is HMAC-signed (timestamp + nonce). The bridge refuses to start without `BACKEND_URL` and a `BRIDGE_SHARED_SECRET` of at least 32 characters (it loads `.env` itself).
- Linking is driven from the dashboard: the backend queues a `link` command for a user, the bridge starts that user's socket and reports the QR / pairing code through `POST /bridge/sync`. QR codes are never printed to the terminal or logs.
- Credentials: `wa_session/<user id>/` (git-ignored; treat as secrets). Logout, or unlinking from the phone, deletes that user's directory.
- Privacy: inbound messages are forwarded only if the sender is one of **that user's** target numbers (1:1 chats only; groups, status and everything else are dropped). Outbound jobs are sent only on the owner's socket and only to that user's targets.
- Delivery is at-most-once: the backend leases a job, the bridge sends it and acks it.

```
cp .env.example .env     # BACKEND_URL, BRIDGE_SHARED_SECRET (same as backend), optional WA_SESSION_DIR, HUMAN_DELAY
npm install && npm run dev
npm test                 # includes multi-user routing and isolation tests
docker build -t sentinel-bridge . && docker run --rm --env-file .env -v sentinel_wa:/app/wa_session sentinel-bridge
```
Baileys is an unofficial client; a linked account can be restricted by WhatsApp.