# syntax=docker/dockerfile:1
FROM node:22-alpine AS builder
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY tsconfig.json ./
COPY src/ ./src/
RUN npm run build

FROM node:22-alpine AS runtime
RUN addgroup -S sentinel && adduser -S sentinel -G sentinel
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts && npm cache clean --force
COPY --from=builder /build/dist ./dist
RUN mkdir -p /app/wa_session && chown sentinel:sentinel /app/wa_session
VOLUME ["/app/wa_session"]
USER sentinel
ENV NODE_ENV=production WA_SESSION_DIR=/app/wa_session HEARTBEAT_FILE=/tmp/bridge.heartbeat
# No listening port. Healthy = the poll loop touched the heartbeat file within the last 2 minutes.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD node -e "const s=require('fs').statSync(process.env.HEARTBEAT_FILE);process.exit(Date.now()-s.mtimeMs<120000?0:1)"
CMD ["node", "dist/index.js"]