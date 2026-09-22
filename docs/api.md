# Backend API

The OpenAPI document at `/api/v1/openapi.json` is authoritative. All application
routes use `/api/v1`; `/internal/metrics` is a separate internal route.

## Authentication and errors

Obtain a short-lived bearer token with `POST /login/access-token`. Role,
activation, and password resets increment a token version so previously issued
tokens stop working. Temporary-password users may only inspect their own user
record and change their password.

Safe errors use:

```json
{"detail":{"code":"machine_readable_code","message":"Safe message","fields":{}}}
```

Request validation omits submitted values, including passwords and contact
data. List responses use `{data, next_cursor, has_more}`. Cursors are opaque.
When OpenTelemetry is configured, responses include `X-Trace-Id`; clients must
treat it as diagnostic metadata rather than an authorization token.

## Resources

- `POST /imports` uploads multipart field `file`.
- `GET /imports`, `GET /imports/{id}`, and `GET /imports/{id}/preview` read
  imports and a bounded preview.
- `PUT /imports/{id}/mapping` accepts `{mapping:{canonical:header}}`.
- `POST /imports/{id}/validate`, `/confirm`, `/retry`, and `/cancel` mutate
  workflow state. Confirmation requires `Idempotency-Key` (8–128 characters).
- `GET /imports/{id}/rows?outcome=...` reads validation outcomes.
- `GET /imports/{id}/reports/{accepted|errors|duplicates}` streams authorized
  safe CSV output.
- `GET /jobs/{id}` and `/jobs/{id}/attempts` read durable execution state.
- `GET /contacts?q=...` searches with cursor pagination.
- Administrator routes are `GET/POST /users`, `GET/PATCH /users/{id}`,
  `POST /users/{id}/temporary-password`, and `GET /audit-events`.
- Self-service routes are `GET /users/me` and `POST /users/me/password`.

Import states are `uploaded`, `mapped`, `validating`, `validated`, `importing`,
`completed`, `failed`, and `cancelled`. Job states are `queued`, `running`,
`succeeded`, `failed`, `cancel_requested`, and `cancelled`.

Confirmation idempotency is scoped to the import URL. Reusing the same key on
the same import returns the existing confirmation job. A different key for an
already-confirmed import returns `idempotency_conflict`; the same client key can
be used for a different import.
