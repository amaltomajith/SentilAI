import uvicorn

from sentinel.api.app import create_app

if __name__ == "__main__":
    from sentinel.config import get_settings

    cfg = get_settings()
    if cfg.dev_auth:
        print('[sentinel] WARNING: DEV_AUTH=1 - anyone who can reach this port can sign in as any name. Local testing only; never deploy like this.', flush=True)
    else:
        print(f"[sentinel] auth: {'Clerk issuer ' + cfg.clerk_issuer if cfg.clerk_issuer else 'NOT CONFIGURED (set CLERK_ISSUER) - every /api call answers 503'}", flush=True)
    import os

    uvicorn.run(create_app(), host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")), proxy_headers=True, forwarded_allow_ips="*")