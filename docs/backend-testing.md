# Backend testing and evidence

Local checks do not require Docker:

```console
uv sync --frozen --all-packages
uv run --package app ruff check backend/app backend/tests
uv run --package app mypy backend/app
uv run --package app pytest -q backend/tests
```

Tests marked by `RUN_POSTGRES_TESTS=1` require migrated PostgreSQL and Redis.
GitHub-hosted CI starts both services, then runs:

```console
cd backend
alembic upgrade head
RUN_POSTGRES_TESTS=1 pytest -q tests
bash scripts/test-backup-restore.sh
```

The service-backed suite covers schema constraints/indexes; administrator,
operator, viewer, temporary-password, and token invalidation behavior; upload,
mapping, validation and safe reports; repeated and concurrent confirmation;
queued and running cancellation; simultaneous worker delivery; lost queue
publication and stalled reconciliation; audit rollback; and PostgreSQL-derived
worker metrics. Unit tests cover UTF-8 BOM, malformed and oversized data,
duplicate rules, formula neutralization, object path traversal, secret-file
precedence, safe errors, PII redaction, upload compensation, and retention.
The migration-upgrade test first applies the upstream schema, inserts a legacy
administrator and item, upgrades to head, and proves both legacy reads and the
new FDE schema survive. The backup drill uses real version-matched PostgreSQL
client tools and a disposable database; a fresh Alembic migration alone does
not satisfy recovery evidence.

Published evidence at commit `eebc040e130b10d28c10dff0f339f0399364c78a`
is [GitHub Actions run 35702605568](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35702605568):
Ruff, Mypy, Alembic, PostgreSQL, Redis, and its then-current backend suite
passed. Later worker recovery, metrics, upload lifecycle, audit rollback, and
container changes are **pending service-backed CI and independent re-review**;
do not use the earlier run as evidence for them.

No local result substitutes for kind/GKE, rolling-release, backup/restore,
trace, alert, or teardown evidence. Each such claim must link the tested commit,
workflow run, image digest, and sanitized artifact.
