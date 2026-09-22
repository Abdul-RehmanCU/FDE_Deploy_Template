# Backend contract

This file is the stable application contract for the frontend, generated client,
deployment manifests, and test harness. OpenAPI remains authoritative for exact
schemas. All application routes use `/api/v1`; Prometheus metrics use the
separate internal-only `/internal/metrics` route and must not be exposed by the
public frontend proxy.

## Authentication and authorization

- OAuth2 password login: `POST /api/v1/login/access-token`.
- Roles: `admin`, `operator`, `viewer`.
- There is no public signup or email-based password recovery.
- Administrators create users with a generated temporary password. The response
  returns it once and the user must change it before using protected resources.
- Viewer access is read-only and cannot download reports.

| Capability | Admin | Operator | Viewer |
| --- | --- | --- | --- |
| dashboard/import/contact reads | yes | yes | yes |
| upload/map/validate/confirm/retry/cancel | yes | yes | no |
| report download | yes | yes | no |
| user and audit administration | yes | no | no |

## Routes

- Users: `GET/POST /users`, `GET/PATCH /users/{id}`,
  `POST /users/{id}/temporary-password`, `GET /users/me`, and
  `POST /users/me/password`.
- Dashboard: `GET /dashboard`.
- Imports: `POST /imports`, `GET /imports`, `GET /imports/{id}`,
  `GET /imports/{id}/preview`,
  `PUT /imports/{id}/mapping`, `POST /imports/{id}/validate`,
  `POST /imports/{id}/confirm`, `POST /imports/{id}/retry`,
  `POST /imports/{id}/cancel`, `GET /imports/{id}/rows`, and
  `GET /imports/{id}/reports/{accepted|errors|duplicates}`.
- Jobs: `GET /jobs/{id}` and `GET /jobs/{id}/attempts`.
- Contacts: `GET /contacts`.
- Audit: `GET /audit-events` (administrator only).
- Operations: `GET /health/live`, `GET /health/ready`, and `GET /version`.

`POST /imports/{id}/confirm` requires an `Idempotency-Key` header. Mutating
import routes return the current import and durable job identifiers. CSV upload
is multipart with one UTF-8 (optional BOM) file of at most 10 MiB and 10,000
data rows.

## Common response shapes

Errors use a stable, safe envelope:

```json
{"detail":{"code":"machine_readable_code","message":"Safe message","fields":{}}}
```

Keyset-paginated lists use:

```json
{"data":[],"next_cursor":null,"has_more":false}
```

Import summaries expose `accepted_count`, `rejected_count`,
`duplicate_count`, `existing_contact_count`, `inserted_count`, and
`skipped_count`. Validation failures and infrastructure failures have separate
status/error codes.

## Runtime and configuration

Entrypoints:

- API: `fastapi run app/main.py --port 8000`
- Worker: `celery -A app.worker.celery_app worker`
- Transactional outbox publisher: `python -m app.outbox_publisher`
- Seven-day local intermediate cleanup: `python -m app.cleanup_storage`
- Database migration: `alembic upgrade head`

Secrets support either direct variables for local/CI use or CSI-mounted files:
`SECRET_KEY`/`SECRET_KEY_FILE`, `DATABASE_URL`/`DATABASE_URL_FILE`, and
`REDIS_URL`/`REDIS_URL_FILE`. File values take precedence. Other settings are
`BACKEND_CORS_ORIGINS`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`,
`STORAGE_BACKEND=local|gcs`, `STORAGE_LOCAL_ROOT`, `GCS_BUCKET`,
`APP_ENVIRONMENT`, and `APP_VERSION`.

The outbox publisher holds a claimed row lock only during one broker publication
attempt. Redis connect timeout is 5 seconds, the configurable socket timeout is
`OUTBOX_PUBLISH_TIMEOUT_SECONDS` (default 10), Celery publish retries are off,
and the publisher retries from PostgreSQL on its next pass. It also reconciles
stale running and queued jobs every `JOB_RECONCILE_INTERVAL_SECONDS` (default
30). The worker serves internal Prometheus metrics at `/metrics` on
`WORKER_METRICS_PORT` (default 9100).

PostgreSQL is the durable authority for job state. Redis only transports Celery
messages. Upload and report object names are server-generated; all downloads
are streamed after an authorization check.
