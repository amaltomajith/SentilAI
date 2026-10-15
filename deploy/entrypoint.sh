#!/bin/sh
# Starts the WhatsApp connector (restarted if it exits) and the API (main process; if it exits the container exits).
set -e

PORT="${PORT:-8000}"

case "${DATABASE_URL:-}" in
  postgres*) echo "[entrypoint] applying database migrations"; alembic upgrade head ;;
esac

if [ "${BRIDGE_ENABLED:-1}" = "1" ]; then
  if [ -z "${BRIDGE_SHARED_SECRET:-}" ]; then
    echo "[entrypoint] BRIDGE_SHARED_SECRET is not set; the WhatsApp connector is disabled"
  else
    (
      export BACKEND_URL="http://127.0.0.1:${PORT}"
      cd /app/bridge
      while true; do
        until python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:${PORT}/api/health',timeout=2)" 2>/dev/null; do sleep 1; done
        node dist/index.js || echo "[entrypoint] connector exited with $?"
        sleep 5
      done
    ) &
  fi
fi

exec python -m sentinel.api