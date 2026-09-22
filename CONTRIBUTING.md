# Contributing

Contributions should preserve the repository's central promise: customer-scoped deployments are explicit, observable, recoverable, cost-bounded, and evidence-backed.

## Before changing code

Read [PLAN.md](PLAN.md), the [API contract](backend/API_CONTRACT.md), and the relevant guide under `docs/`. Open an issue before changing public API shapes, persistence, authorization, deployment topology, IAM, cost gates, cleanup targeting, or evidence policy.

Never include credentials, customer data, raw state, kubeconfigs, browser auth storage, HAR/trace archives, or unredacted provider output.

## Development checks

Install locked dependencies:

```bash
uv sync --locked --all-groups
bun install --frozen-lockfile
```

Run backend checks:

```bash
uv run --package app ruff check backend/app backend/tests
uv run --package app ruff format --check backend
uv run --package app mypy backend/app backend/tests
uv run --package app pytest -q backend/tests
```

Run frontend checks:

```bash
bunx biome ci --no-errors-on-unmatched --files-ignore-unknown=true frontend
bun run --filter frontend build
cd frontend && bunx playwright test --list
```

Run deployment and infrastructure checks:

```bash
uv run --project tooling/fde --with pytest pytest -q tooling/fde/tests infra/terraform/tests
terraform fmt -check -recursive infra/terraform
helm lint infra/helm/fde --strict
helm lint observability/helm --strict
```

GitHub CI supplies PostgreSQL, Redis, image builds, real browser journeys, Terraform provider initialization, Helm/kubeconform, and kind. A local skip is not a substitute for that evidence.

## Change expectations

- Keep commits coherent and substantive. Formatting-only commits do not count toward the implementation ledger.
- Add Alembic migrations for every schema change.
- Preserve `/api/v1`, stable error envelopes, opaque cursors, and generated-client compatibility.
- Enforce permissions in the API and cover direct requests, not only hidden navigation.
- Keep job replay, cancellation, confirmation, and cleanup idempotent.
- Use immutable image digests outside the explicit kind profile.
- Keep managed-profile claims labeled static until live evidence exists.
- Update the implementation ledger with exact SHAs and workflow URLs.
- Inspect generated screenshots/video before publishing them.

## Pull requests

Describe the concrete trigger and resulting behavior. Include relevant tests, workflow links, screenshots for visible changes, migration/recovery implications, security and cost effects, and any criterion that remains unverified.

Do not trigger paid infrastructure from a pull request. Deployment workflows require protected environments and a reviewed current-head gate.
