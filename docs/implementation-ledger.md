# Implementation ledger

This ledger records repository-owned commits and verifiable acceptance evidence. It does not count the upstream FastAPI template's history. A checked item means evidence exists for the exact repository revision; an unchecked item must not be described as complete.

## Repository history

| # | Commit | Unit | Evidence |
| ---: | --- | --- | --- |
| 1 | `6f87852` | Attributed upstream import | New root commit; `docs/upstream-provenance.md`; retained `LICENSE`; no upstream parent history |
| 2 | `a20ef89` | Repository safety defaults | Secret/state ignore rules, local `.env.example`, unrelated release scripts removed |
| 3 | `3c82d96` | Application API and runtime contract | `backend/API_CONTRACT.md` freezes endpoints, roles, errors, runtime entrypoints, and cross-component requirements |

Commit count is calculated from this repository's root commit. The target is 128 substantive commits and the acceptance minimum is 120. Empty, cosmetic-only, inherited, or backdated commits do not qualify.

## Required acceptance evidence

### Repository and application

- [x] Public-repository name and license fixed in `PLAN.md`; MIT notice retained.
- [x] Pinned upstream source, revision, imported scope, and exclusions documented.
- [ ] GitHub repository is public and the default branch is protected by passing CI.
- [ ] At least 120 substantive new commits exist on the published default branch.
- [ ] Guided upload, mapping, validation, confirmation, job, directory, user administration, and audit flows work.
- [ ] Administrator, operator, and viewer authorization is enforced by the API and covered by tests.
- [ ] CSV limits, normalization, duplicate handling, formula neutralization, idempotency, retries, and cancellation are covered by fixtures and tests.
- [ ] TypeScript client is generated from the final OpenAPI contract.
- [ ] Desktop and mobile Playwright journeys pass against the real application.

### Delivery and infrastructure

- [ ] Pull-request CI passes on standard GitHub-hosted Linux runners without deployment credentials.
- [ ] Container images are built once and promoted by immutable digest.
- [ ] Helm chart passes schema, render, and kind rehearsal checks.
- [ ] Demo Terraform profile passes format, validation, provider-schema, and mocked tests.
- [ ] Managed profile passes static and mocked checks and is clearly labeled implemented but not live-tested.
- [ ] Deployment CLI validates customer, environment, project, profile, digest, region, and secret references before cloud commands.
- [ ] Workload Identity Federation and separate build, infrastructure, deploy, runtime, and cleanup identities are configured without downloaded service-account keys.
- [ ] Migration, staging smoke, digest promotion, failed-rollout recovery, and unconditional cleanup workflows pass.

### Observability and resilience

- [ ] API, SQL, Redis, and worker traces correlate without PII.
- [ ] Bounded-cardinality metrics, structured redacted logs, dashboards, and alert rules are verified.
- [ ] A controlled alert is captured firing and resolving.
- [ ] Rolling-update request measurements and unhealthy-release recovery evidence are captured.
- [ ] Backup/restore into a disposable database is verified by record counts.

### Budget, live demonstration, and teardown

- [ ] Current GCP baseline and an itemized estimate are recorded; total demo estimate is at most USD 10.
- [ ] GCP-hosted expiry cleanup is installed and its exact targeting is proven with an innocuous sentinel before GKE creation.
- [ ] Runtime remains within four hours from first billable action.
- [ ] Core journey and environment isolation are repeated on GKE.
- [ ] Sanitized application and observability evidence is exported.
- [ ] Primary and expiry cleanup paths are verified and final GCP inventory shows no billable demo residue.
- [ ] Cost ledger distinguishes estimates, reported charges, pending billing, and final known charges.

### Publication and handover

- [ ] README includes branded navigation, accurate badges, architecture/release diagrams, evidence matrix, quickstarts, operations, cost controls, limitations, and acknowledgments.
- [ ] Real working-screen screenshots and a short walkthrough are published with accurate local/CI/GKE captions.
- [ ] Customer handover states what ran, what remains unverified, costs, and remaining resources.
- [ ] Passing workflow URLs and immutable artifact digests are linked.
- [ ] `v1.0.0` is tagged and released only after all required checks pass; sanitized evidence is attached.

## External-state log

| Time (America/Toronto) | Change | Result |
| --- | --- | --- |
| 2026-09-22 | Implementation authorized | Repository work and non-billable CI allowed; billable GCP remains gated |

## Evidence rules

- Record exact commit SHAs, workflow URLs/run IDs, image digests, commands, timestamps, and output artifacts.
- Label local, CI, kind, and GKE evidence accurately. A static or mocked check cannot satisfy a live criterion.
- Never invent charges, screenshots, uptime, zero-downtime, teardown, or cloud validation.
- Keep secrets, tokens, customer identifiers, contact data, raw Terraform state, and kubeconfigs out of committed evidence.
