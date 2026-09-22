# Development guide

GitHub-hosted CI is the canonical integration environment. Local processes are optional conveniences and should use synthetic data only.

## Toolchain

- Python 3.14 and `uv`;
- Bun 1.3.10;
- PostgreSQL 17 and Redis 8 for service-backed behavior;
- Docker, Helm, `kubectl`, kind, and Terraform 1.15.8 for delivery work.

Install locked dependencies from the repository root:

```bash
uv sync --locked --all-groups
bun install --frozen-lockfile
```

Copy `.env.example` to `.env` and replace every generated placeholder. The file is ignored by Git. SMTP is intentionally disabled.

## Start the local services

The Compose files are developer conveniences, not the production deployment model.

```bash
docker compose up -d db redis
```

Apply migrations and create the first administrator:

```bash
cd backend
uv run alembic upgrade head
uv run python -m app.bootstrap_admin admin@example.com --full-name "Local Administrator"
```

Store the printed one-time password temporarily, sign in, and change it. Do not place it in a fixture or documentation.

## Start application processes

Use separate terminals:

```bash
cd backend
uv run fastapi run app/main.py --port 8000
```

```bash
cd backend
uv run python -m app.outbox_publisher
```

```bash
cd backend
uv run celery -A app.worker.celery_app worker --loglevel=info --concurrency=1
```

```bash
bun run --filter frontend dev
```

Open `http://localhost:5173`. The public API is under `http://localhost:8000/api/v1`; internal metrics are not proxied by the frontend.

## Generate the API client

After an API schema change, export the FastAPI OpenAPI document and run the pinned generator. The committed client must match the final backend revision.

```bash
./scripts/generate-client.sh
```

Run the frontend build after generation. The compile-time assertions in `frontend/src/features/api/generated-contract.ts` fail when critical generated response shapes no longer satisfy the UI contract.

## Backend tests

```bash
uv run --package app ruff check backend/app backend/tests
uv run --package app ruff format --check backend
uv run --package app mypy backend/app backend/tests
uv run --package app pytest -q backend/tests
```

Tests marked for PostgreSQL skip when no service is available. In CI, migrations run first and `RUN_POSTGRES_TESTS=1` turns those scenarios into required checks. They cover role changes, token invalidation, replay, cancellation, outbox locking, schema constraints, formula-safe reports, confirmation idempotency, and migration upgrades.

## Frontend tests

```bash
cd frontend
bunx biome ci --no-errors-on-unmatched --files-ignore-unknown=true .
bun run build
bunx playwright test --list
```

The full Playwright suite expects the API, PostgreSQL, Redis, worker, publisher, and Vite server. CI creates deterministic admin/operator/viewer sessions and publishes only sanitized PNG/WebM/report artifacts. Raw traces and authentication storage are excluded.

## Deployment tooling

```bash
uv run --project tooling/fde --with pytest pytest -q tooling/fde/tests
uv run --project tooling/fde fde validate-config infra/config/customers/demo.example.yaml
uv run --project tooling/fde fde doctor infra/config/customers/demo.example.yaml
```

Commands that call Terraform, Helm, `kubectl`, or `gcloud` validate customer/environment/project identity before execution and redact secret-bearing output.

## Kubernetes and Terraform

Use GitHub CI for the authoritative image build and kind rehearsal. It loads separate API and frontend images, installs the chart with test-only Kubernetes secrets, completes an import through the frontend proxy, restarts the worker, measures requests during an API rollout, and verifies recovery from an unhealthy release.

Terraform directories have committed Linux/Windows provider locks. Validate without remote state:

```bash
terraform -chdir=infra/terraform/environments/demo init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/terraform/environments/demo validate
```

Never apply the demo or managed roots merely to test syntax.

## Formatting and generated files

Use Ruff for Python and Biome for TypeScript. Generated client and route-tree files are committed because type checking runs before runtime generation in clean CI. Review generated diffs for removed operations, unexpected optional fields, and unsafe response changes.
