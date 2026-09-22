FROM oven/bun:1.3.10-alpine@sha256:32f1fcccb1523960b254c4f80973bee1a910d60be000a45c20c9129a1efcffee AS build

WORKDIR /app
COPY package.json bun.lock ./
COPY frontend/package.json ./frontend/package.json
COPY packages/react-email/package.json ./packages/react-email/package.json
RUN bun install --frozen-lockfile

COPY frontend ./frontend
WORKDIR /app/frontend
ARG VITE_API_URL=
RUN bun run build

FROM nginxinc/nginx-unprivileged:1.29.1-alpine@sha256:27985295bdb22a1ef8f712863210bd5877c0f3006494a593e86b3fe0fa55467e

ENV BACKEND_UPSTREAM=http://fde-api:8000
ENV FDE_BRAND_NAME="FDE Deploy"

COPY frontend/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/backend/app/frontend /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
