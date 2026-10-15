# syntax=docker/dockerfile:1
# One image runs the API and the WhatsApp connector (the connector restarts on its own; the API is the main process).
# Build:  docker build -t sentinel .        Run: see docker-compose.yml or render.yaml

FROM node:22-bookworm-slim AS bridge-build
WORKDIR /bridge
COPY whatsapp-bridge/package.json whatsapp-bridge/package-lock.json ./
RUN npm ci --ignore-scripts
COPY whatsapp-bridge/tsconfig.json ./
COPY whatsapp-bridge/src ./src
RUN npm run build && npm prune --omit=dev --ignore-scripts

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 NODE_ENV=production
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates tini && rm -rf /var/lib/apt/lists/*
COPY --from=bridge-build /usr/local/bin/node /usr/local/bin/node
RUN useradd --create-home --uid 10001 sentinel
WORKDIR /app

COPY backend /app/backend
# Editable install on purpose: the code resolves its data/ folder relative to the source tree.
RUN pip install -e "/app/backend[prod]"
COPY --from=bridge-build /bridge/dist /app/bridge/dist
COPY --from=bridge-build /bridge/node_modules /app/bridge/node_modules
COPY --from=bridge-build /bridge/package.json /app/bridge/package.json
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh && mkdir -p /app/backend/data /app/bridge/wa_session && chown -R sentinel:sentinel /app

USER sentinel
WORKDIR /app/backend
ENV HOST=0.0.0.0 PORT=8000 WA_SESSION_DIR=/app/bridge/wa_session HEARTBEAT_FILE=/tmp/bridge.heartbeat
VOLUME ["/app/backend/data", "/app/bridge/wa_session"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/api/health'%os.environ.get('PORT','8000'),timeout=4)"
ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]