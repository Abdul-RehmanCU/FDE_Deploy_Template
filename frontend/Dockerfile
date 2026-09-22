FROM oven/bun:1.3.10-alpine AS build

WORKDIR /app
COPY package.json bun.lock ./
COPY frontend/package.json ./frontend/package.json
RUN bun install --frozen-lockfile

COPY frontend ./frontend
WORKDIR /app/frontend
ARG VITE_API_URL=
RUN bun run build

FROM nginxinc/nginx-unprivileged:1.29.1-alpine

ENV BACKEND_UPSTREAM=http://fde-api:8000

COPY frontend/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/backend/app/frontend /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
