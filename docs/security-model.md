# Application security model

The application assumes one trusted customer installation with authenticated
employees. The internet, uploaded CSVs, filenames, bearer tokens, and browser
inputs are untrusted. PostgreSQL, Redis, and object storage are private runtime
dependencies.

Server-side dependencies enforce `admin`, `operator`, and `viewer` permissions
on every route. Navigation visibility is not a security boundary. Viewer access
is read-only and report downloads require operator or administrator role.

Passwords use Argon2 with bcrypt verification for migrated hashes. Access
tokens expire after 30 minutes by default and include a server-checked token
version. Login attempts are counted in Redis using a SHA-256 digest of client
address and normalized email; the API fails closed when this control is
unavailable. Public signup, SMTP recovery, and development user creation are
disabled.

Cloud secrets may be supplied through `SECRET_KEY_FILE`, `DATABASE_URL_FILE`,
and `REDIS_URL_FILE` for GKE CSI mounts. File values take precedence. Repository
configuration contains references, not secret values. The runtime image uses
UID/GID 10001 and one API worker; Kubernetes supplies read-only secrets and a
writable storage mount only where needed.

Object keys are generated from server UUIDs. Upload filenames never become
paths. Downloads pass authorization before storage access. Upload failure after
object creation performs a compensating delete, and the seven-day cleanup also
reconciles old orphan objects.

Logs and metrics must not contain passwords, tokens, CSV values, contact email,
search terms, or arbitrary IDs as labels. Access logging and OpenTelemetry spans
replace query-bearing URL attributes with the request path. SQL instrumentation
records statements with placeholders, not bound contact values. Audit metadata
contains action, actor/resource IDs, counts, roles, and status; it excludes PII.

Prometheus routes are internal: API `/internal/metrics` on 8000 and worker
`/metrics` on 9100. Network policy allows the observability namespace, not the
public frontend proxy.
