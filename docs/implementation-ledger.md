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
| 95–120 | `5b7c03d` … `e18abb9` | Backend formatting correction, PVC ownership, containerized import rehearsal, reproducible frontend image, WIF/IAM regression coverage, accepted responsive evidence, release/customer/observability/evidence/managed/contribution guides |
| 121–144 | `74dedc1` … `9fbe8f6` | Additive migration and restore drill, exact expiry costs, writable proxy, full mobile evidence, managed tests, PostgreSQL 16 alignment, deterministic disks, priced-plan gate, independent telemetry runtime, worker OTLP, runtime branding |
| 145–166 | `eca0f34` … `b43b990` | Rollback recovery, immutable config parity, accepted application media, restore fixes, exact probe policies, signed image manifests, security scans, split kind jobs, paid/residue gates, expiry sentinel, deterministic release rendering, GKE business smoke |
| 167–189 | `e949f4d` … `b7525a0` | Seeded identity/private-cost guard, partial-state cleanup, automatic trace/log/metric evidence, managed TLS, same-digest staging/demo-prod workflow, exact secret grants, run-once paid authorization, vulnerability remediation, phase-classified rolling evidence, owner-only bootstrap retirement |
| 190–237 | `4341138` … `e71419e` | Current delivery docs, schema-compatible readiness, security remediation, Checkov controls, managed private TLS/egress handoff, exact-digest scans, safe all-generation teardown, valid Alloy pipelines, namespace alerts, live-GKE telemetry automation, passing kind observability evidence, and corrected dashboard gauges/panels |

After this ledger and media update, the repository contains **247** new root-history commits and **244 substantive commits**. Mechanical formatting-only commits `d8fafda`, `5b7c03d`, and `3a8b85e` are excluded. All other entries implement a capability, test, fix, contract, evidence gate, or operational document.

## CI evidence

| Tested SHA | Workflow run | Result | Evidence boundary |
| --- | --- | --- | --- |
| `eebc040` | [35702605568](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35702605568) | Passed | Repository policy; CLI; frontend lint/build; Python 3.14 Ruff/mypy/Alembic/real PostgreSQL+Redis tests; six Terraform roots; application and observability Helm lint/render/kubeconform |
| `7bf5814` | [35702996222](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35702996222) | Failed | All non-browser jobs passed; 3/5 browser journeys passed. Admin label and confirmation polling failures were fixed in `854a8eb`, `d59ed63`, and `b9a0020`. The failed run's trace-bearing artifact was deleted and confirmed absent. |
| `a9b7c6d` | [35703634671](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35703634671) | Failed | Browser journeys passed; kind and backend exposed lock/format issues fixed by later revisions. |
| `93d9a67` | [35707717123](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35707717123) | Failed | Backend job passed 39 PostgreSQL/Redis tests plus additive migration and disposable PostgreSQL 16 dump/restore. Browser passed. Chart YAML indentation failed before kind runtime and was fixed in `fddf233`. |
| `8b9a5c7` | [35708056837](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35708056837) | Failed | All non-kind jobs passed. App install/import/rollout passed; the isolated request probe exposed a missing exact egress policy, fixed in `d1d2bb0`. |
| `cfce94c` | [35710341930](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35710341930) | Failed | Repository, backend, frontend, browser, CLI, Terraform/Helm/managed tests, and application kind rehearsal passed. The independent telemetry job stopped before installing telemetry because Helm had not waited for its migration Job; `fbc1ba3` adds both Helm and explicit migration waits. |
| `cfce94c` | [35710341995](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35710341995) | Failed | The new security gate found fixed backend base/package CVEs and a Trivy Terraform-adapter crash; immutable slim bases, lock updates, per-image matrix scans, and pinned Checkov are in the next revision. |
| `48b6efe` | [35717933275](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35717933275) | Passed | All eight jobs passed: repository policy; frontend; browser; backend with 50 PostgreSQL/Redis tests and restore drill; CLI; Terraform/managed/Helm/Alloy validation; application kind import/rolling/rollback; and kind metrics/logs/traces/dashboard/alert evidence. |
| `48b6efe` | [35717933305](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35717933305) | Passed | Dependency and secret scan, backend and frontend image scans, and Terraform Checkov policy scan passed. The pull-request-only dependency review is correctly skipped on a push. |
| `e71419e` | [35718898057](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35718898057) | Passed | CI passed all eight jobs at this revision; artifact `10691161653` contains populated Grafana, correlated Tempo/Loki, and namespace-specific alert firing/resolved evidence. |
| `e71419e` | [35718898011](https://github.com/Abdul-RehmanCU/FDE_Deploy_Template/actions/runs/35718898011) | Passed | Dependency, secret, backend/frontend image, and Terraform policy scans passed at this revision. |

Commit count is calculated from this repository's root commit. The target is 128 substantive commits and the acceptance minimum is 120. Empty, cosmetic-only, inherited, or backdated commits do not qualify.

## Required acceptance evidence

### Repository and application

- [x] Public-repository name and license fixed in `PLAN.md`; MIT notice retained.
- [x] Pinned upstream source, revision, imported scope, and exclusions documented.
- [ ] GitHub repository is public; default-branch protection remains pending the final stable required-check set.
- [x] At least 120 substantive new commits exist on the published default branch.
- [x] Guided upload, mapping, validation, confirmation, job, directory, user administration, and audit flows work in real-stack CI.
- [x] Administrator, operator, and viewer authorization is enforced by the API and covered by service-backed tests at `eebc040`.
- [x] CSV limits, normalization, duplicate handling, formula neutralization, idempotency, retries, and cancellation are covered by fixtures and service-backed tests at `eebc040`; later recovery additions are pending current-head CI.
- [x] TypeScript client is generated from the application OpenAPI contract; preview regeneration is recorded at `3236f51`.
- [x] Desktop and mobile Playwright journeys pass against the real application; accepted screenshots are from run `35706376224` at `93d7c85`.

### Delivery and infrastructure

- [x] Validation CI passes on a standard GitHub-hosted Linux runner without deployment credentials at `eebc040`; pull-request execution remains to be observed on an actual PR.
- [ ] Container images are built once and promoted by immutable digest.
- [x] Helm schema/render, managed fixture, kubeconform, application kind, and isolated observability kind rehearsals pass at `48b6efe`.
- [x] Demo Terraform profile passes format/init/validation and expiry contract tests; no apply is claimed.
- [x] Managed profile passes static and mocked Terraform checks and is clearly labeled implemented but not live-tested.
- [x] Deployment CLI validates customer, environment, project, profile, digest, region, and secret references before cloud commands.
- [x] Workload Identity Federation and separate build, infrastructure, deploy, runtime, and cleanup identities are defined without downloaded service-account keys; live federation proof remains pending.
- [ ] Migration, staging smoke, digest promotion, failed-rollout recovery, and unconditional cleanup workflows pass.

### Observability and resilience

- [x] API, SQL, Redis, publisher, and worker spans correlate on one trace in kind without PII at `e71419e`.
- [x] Bounded-cardinality metrics, structured redacted logs, dashboards, and alert rules are verified in kind artifact `10691161653`.
- [x] A namespace-specific controlled alert is captured firing and resolving in kind artifact `10691161653`.
- [x] Rolling-update request measurements and unhealthy-release recovery evidence are captured in kind; the accepted measurement observed 43 rollout successes and 0 errors at `3e260c6`, and the current-head rehearsal also passes.
- [x] Backup/restore into a disposable PostgreSQL 16 database is verified by record counts in job `106680560649` from run `35707717123`.

### Budget, live demonstration, and teardown

- [x] Authenticated baseline and itemized estimate are recorded in `infra/cost/`; estimate is USD 4.96619304 and baseline billing showed CA$0 with delayed-billing caveat. Paid execution also requires a fresh private baseline within 30 minutes.
- [ ] GCP-hosted expiry cleanup is installed and its exact targeting is proven with an innocuous sentinel before GKE creation.
- [ ] Runtime remains within four hours from first billable action.
- [ ] Core journey and environment isolation are repeated on GKE.
- [ ] Sanitized application and observability evidence is exported.
- [ ] Primary and expiry cleanup paths are verified and final GCP inventory shows no billable demo residue.
- [ ] Cost ledger distinguishes estimates, reported charges, pending billing, and final known charges.

### Publication and handover

- [x] README includes branded navigation, architecture/release diagrams, evidence matrix, quickstarts, operations, cost controls, limitations, and acknowledgments; final live-GKE evidence links remain pending.
- [x] Real working-screen screenshots, a synthetic-data walkthrough, and kind Grafana/Tempo/Loki/alert evidence are published with accurate captions; GKE media remain pending.
- [ ] Customer handover states what ran, what remains unverified, costs, and remaining resources.
- [ ] Passing workflow URLs and immutable artifact digests are linked.
- [ ] `v1.0.0` is tagged and released only after all required checks pass; sanitized evidence is attached.

## External-state log

| Time (America/Toronto) | Change | Result |
| --- | --- | --- |
| 2026-09-22 | Implementation authorized | Repository work and non-billable CI allowed; billable GCP remains gated |
| 2026-09-22 | Public repository created | `Abdul-RehmanCU/FDE_Deploy_Template`, public, default branch `main` |
| 2026-09-22 | Failed browser artifact removed | Artifact `10683032031` from run `35702996222` deleted because the old Playwright configuration retained traces; API readback returned zero artifacts |
| 2026-09-22 | Repository published as reusable template | Public visibility confirmed; template mode enabled; accurate description/topics retained; merge branches auto-delete |
| 2026-09-22 | Deployment environments configured | Autonomous demo environments are restricted to protected branches; real `production` requires the repository owner reviewer and remains unused |

## Evidence rules

- Record exact commit SHAs, workflow URLs/run IDs, image digests, commands, timestamps, and output artifacts.
- Label local, CI, kind, and GKE evidence accurately. A static or mocked check cannot satisfy a live criterion.
- Never invent charges, screenshots, uptime, zero-downtime, teardown, or cloud validation.
- Keep secrets, tokens, customer identifiers, contact data, raw Terraform state, and kubeconfigs out of committed evidence.
