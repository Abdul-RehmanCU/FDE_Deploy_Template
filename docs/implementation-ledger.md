# Implementation ledger

This ledger records repository-owned commits and verifiable acceptance evidence. It does not count the upstream FastAPI template's history. A checked item means evidence exists for the exact repository revision; an unchecked item must not be described as complete.

## Repository history

| # | Commit | Unit | Evidence |
| ---: | --- | --- | --- |
| 1 | `6f87852` | Attributed upstream import | New root commit; `docs/upstream-provenance.md`; retained `LICENSE`; no upstream parent history |
| 2 | `a20ef89` | Repository safety defaults | Secret/state ignore rules, local `.env.example`, unrelated release scripts removed |
| 3 | `3c82d96` | Application API and runtime contract | `backend/API_CONTRACT.md` freezes endpoints, roles, errors, runtime entrypoints, and cross-component requirements |

### Integrated commit ranges

| Repository commits | SHAs | Delivered scope |
| ---: | --- | --- |
| 4–10 | `79c676f` … `31e3407` | Execution ledger, guarded deployment config, pinned frontend toolchain, cloud-runner CI, durable schema, GCP bootstrap, CI credential correction |
| 11–29 | `f8eb822` … `3394fd4` | Enterprise UI shell, GKE demo/managed/expiry modules, identity, CLI doctor/cost gates, dashboard, import/directory/job interfaces, Helm base |
| 30–48 | `d6e42a1` … `ee70ffe` | Durable import engine, service-backed CI, Helm workloads, audit/admin UI, backend resilience tests, observability chart, Terraform/Helm cloud validation |
| 49–64 | `073087c` … `eebc040` | Executable expiry schedules, generated API client, managed authentication, cleanup of unsupported flows, guarded CLI operations, kind profiles, Linux provider locks |
| 65–75 | `cfa69a9` … `c0f2a73` | Customer configurations, real-stack browser suite, backend privacy/recovery/audit fixes, managed root, cost ledger, frontend proxy image, sanitized evidence policy |
| 76–94 | `cd29498` … `a9b7c6d` | Kind image/storage contract, browser corrections, worker metrics/reconciliation, upload preview/lifecycle, separate API image, IAM tightening, kind rehearsal, application/security/recovery docs |

Raw repository commit count at `a9b7c6d` is **94**. Substantive count is **93** because formatting-only commit `d8fafda` is excluded. All other entries implement a capability, test, fix, contract, evidence gate, or operational document.

## CI evidence

| Tested SHA | Workflow run | Result | Evidence boundary |
| --- | --- | --- | --- |
| `eebc040` | [35702605568](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35702605568) | Passed | Repository policy; CLI; frontend lint/build; Python 3.14 Ruff/mypy/Alembic/real PostgreSQL+Redis tests; six Terraform roots; application and observability Helm lint/render/kubeconform |
| `7bf5814` | [35702996222](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35702996222) | Failed | All non-browser jobs passed; 3/5 browser journeys passed. Admin label and confirmation polling failures were fixed in `854a8eb`, `d59ed63`, and `b9a0020`. The failed run's trace-bearing artifact was deleted and confirmed absent. |
| `a9b7c6d` | [35703634671](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35703634671) | In progress | Full current-head validation including corrected browser journeys, sanitized PNG/WebM evidence, separate image builds, kind install/probes/proxy/worker restart, and the latest backend/infra fixes |

Commit count is calculated from this repository's root commit. The target is 128 substantive commits and the acceptance minimum is 120. Empty, cosmetic-only, inherited, or backdated commits do not qualify.

## Required acceptance evidence

### Repository and application

- [x] Public-repository name and license fixed in `PLAN.md`; MIT notice retained.
- [x] Pinned upstream source, revision, imported scope, and exclusions documented.
- [ ] GitHub repository is public and the default branch is protected by passing CI.
- [ ] At least 120 substantive new commits exist on the published default branch.
- [ ] Guided upload, mapping, validation, confirmation, job, directory, user administration, and audit flows work.
- [x] Administrator, operator, and viewer authorization is enforced by the API and covered by service-backed tests at `eebc040`.
- [x] CSV limits, normalization, duplicate handling, formula neutralization, idempotency, retries, and cancellation are covered by fixtures and service-backed tests at `eebc040`; later recovery additions are pending current-head CI.
- [x] TypeScript client is generated from the application OpenAPI contract; preview regeneration is recorded at `3236f51`.
- [ ] Desktop and mobile Playwright journeys pass against the real application.

### Delivery and infrastructure

- [x] Validation CI passes on a standard GitHub-hosted Linux runner without deployment credentials at `eebc040`; pull-request execution remains to be observed on an actual PR.
- [ ] Container images are built once and promoted by immutable digest.
- [ ] Helm chart passes schema/render checks at `eebc040`; kind rehearsal is running at `a9b7c6d`.
- [x] Demo Terraform profile passes format/init/validation and expiry contract tests; no apply is claimed.
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

- [x] Authenticated baseline and itemized estimate are recorded in `infra/cost/`; estimate is USD 4.50619304 and baseline billing showed CA$0 with delayed-billing caveat.
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
| 2026-09-22 | Public repository created | `Abdul-RehmanCU/FDE_Deploy_Template`, public, default branch `main` |
| 2026-09-22 | Failed browser artifact removed | Artifact `10683032031` from run `35702996222` deleted because the old Playwright configuration retained traces; API readback returned zero artifacts |

## Evidence rules

- Record exact commit SHAs, workflow URLs/run IDs, image digests, commands, timestamps, and output artifacts.
- Label local, CI, kind, and GKE evidence accurately. A static or mocked check cannot satisfy a live criterion.
- Never invent charges, screenshots, uptime, zero-downtime, teardown, or cloud validation.
- Keep secrets, tokens, customer identifiers, contact data, raw Terraform state, and kubeconfigs out of committed evidence.
