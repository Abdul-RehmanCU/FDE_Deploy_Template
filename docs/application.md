# Application guide

The FDE sample application onboards a bounded customer CSV into a searchable
contact directory. It is one installation per customer: users, contacts,
uploads, jobs, and audit events are not shared between installations.

## Roles

| Capability | Administrator | Operator | Viewer |
| --- | --- | --- | --- |
| View dashboard, import results, jobs, and contacts | Yes | Yes | Yes |
| Upload, map, validate, confirm, retry, or cancel | Yes | Yes | No |
| Download accepted, error, or duplicate reports | Yes | Yes | No |
| Create, disable, or change user roles | Yes | No | No |
| Read audit events | Yes | No | No |

There is no public signup or email recovery. Create the first administrator from
a protected shell after migrations:

```console
python -m app.bootstrap_admin create --email administrator@example.com
```

The command prints a generated temporary password once. Store it securely and
change it at first sign-in. Administrators create later users and issue new
temporary passwords through the user administration screen.

## Import workflow

1. Upload one UTF-8 CSV, optionally with a BOM. The API accepts at most 10 MiB
   and 10,000 data rows. It returns exact headers and a bounded 20-row preview.
2. Map canonical fields to uploaded headers. `email`, `first_name`, and
   `last_name` are required. Optional fields are `company`, `country_code`, and
   `external_id`.
3. Start validation. The durable job classifies each row as accepted, invalid,
   a duplicate within the file, or an existing directory contact. Validation
   never changes the directory.
4. Review totals and row errors. Administrators and operators may download
   formula-neutralized reports; viewers cannot download source-derived CSVs.
5. Confirm with an idempotency key. The worker rechecks contact conflicts and
   inserts accepted contacts in one PostgreSQL transaction. Repeated clicks or
   message replay do not duplicate contacts.

Cancellation is accepted while work is queued or validating and immediately
before the confirmation transaction begins. Once `confirmation_started_at` is
set, the import finishes atomically and cancellation returns
`import_commit_started`.

## Runtime commands

Run these from `backend/` with the required environment or mounted secret files:

```console
alembic upgrade head
fastapi run app/main.py --port 8000 --workers 1
celery -A app.worker.celery_app worker
python -m app.outbox_publisher
python -m app.cleanup_storage
```

The API serves liveness at `/api/v1/health/live`, dependency readiness at
`/api/v1/health/ready`, version data at `/api/v1/version`, and internal metrics
at `/internal/metrics`. The worker serves internal metrics at `/metrics` on port
9100. Neither metrics endpoint belongs on the public frontend route.

Uploads and reports expire after seven days. GCS deployments use bucket
lifecycle policy; shared-filesystem deployments run `app.cleanup_storage`
daily. Contacts remain until the installation owner deliberately removes data.
