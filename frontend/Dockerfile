# syntax=docker/dockerfile:1.7
FROM node:22-bookworm-slim AS deps

WORKDIR /app

ENV PNPM_HOME="/root/.local/share/pnpm" \
    PATH="$PNPM_HOME:$PATH" \
    HUSKY=0 \
    HUSKY_SKIP_INSTALL=1 \
    NEXT_TELEMETRY_DISABLED=1

RUN corepack enable && corepack prepare pnpm@9.12.1 --activate

COPY package.json pnpm-lock.yaml .npmrc ./

RUN pnpm install --frozen-lockfile --ignore-scripts

FROM node:22-bookworm-slim AS builder

WORKDIR /app

ENV PNPM_HOME="/root/.local/share/pnpm" \
    PATH="$PNPM_HOME:$PATH" \
    HUSKY=0 \
    HUSKY_SKIP_INSTALL=1 \
    NEXT_TELEMETRY_DISABLED=1

RUN corepack enable && corepack prepare pnpm@9.12.1 --activate

ARG NEXT_PUBLIC_API_BASE_URL="http://localhost:9093"
ARG NEXT_PUBLIC_APP_BASE_URL="http://localhost:3000"

ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_APP_BASE_URL=$NEXT_PUBLIC_APP_BASE_URL

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN pnpm build && pnpm prune --prod --ignore-scripts

FROM node:22-bookworm-slim AS runner

WORKDIR /app

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000 \
    NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.mjs ./next.config.mjs
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000

CMD ["node_modules/.bin/next", "start", "-H", "0.0.0.0", "-p", "3000"]
