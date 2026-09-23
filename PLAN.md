# FDE Deployment Template — implementation plan

Status: implementation authorized on 2026-09-22; execution in progress. All cost, safety, evidence, and acceptance constraints below remain binding.

## 1. Outcome and fixed decisions

Build a reusable, public repository demonstrating: **given a customer, deploy an observable application into that customer's environment, release it safely, diagnose a failure, recover, and hand it over.**

| Decision | Selected approach |
| --- | --- |
| Repository | `Abdul-RehmanCU/FDE_Deploy_Template`, public, MIT licensed |
| Cloud | GCP only; AWS and Azure are outside version one |
| Demonstration project | `example-fde-project` |
| Region / demo zone | Set privately as repository Actions secrets `GCP_REGION` / `GCP_ZONE`; record the approved Canadian location outside the public repository |
| Budget | Maximum authorized GCP spend: **USD 25 total**, not monthly |
| Cloud lifetime | Short-lived demonstration; capture evidence and tear down |
| Application | Customer data onboarding and searchable contact directory |
| Deployment model | One installation per customer |
| Users | Administrator, operator, viewer; no public signup |
| Interface | Polished enterprise light theme, responsive and accessible |
| Build/test execution | Standard GitHub-hosted Linux runners; local Docker is optional |
| Kubernetes execution | GKE for the live demonstration; kind inside CI for inexpensive integration checks |
| Production extension | Opt-in GCP managed-services profile, validated but not deployed under this budget |
| Delivery | Work toward completion; cloud runtime has its own independent expiry |
| History | Plan for **128 new substantive commits**; at least 120, excluding inherited upstream history |

### Starting point and provenance

Adapt [FastAPI's full-stack template](https://github.com/fastapi/full-stack-fastapi-template/tree/cb740b656d7a0a6c5e12c7bf8e50343ec94ee9c7), pinned to `cb740b656d7a0a6c5e12c7bf8e50343ec94ee9c7`. Retain the MIT notice and document the imported files, upstream revision, and original work. Import it as an attributed baseline; do not count upstream commits toward our commitment.

Reuse its React/TypeScript/Vite/Tailwind foundation, FastAPI/SQLModel/Alembic application structure, authentication primitives, generated API client, and useful tests. Replace upstream deployment and maintainer automation with workflows owned by this repository. Use its Python 3.14 baseline in cloud containers and CI; pin dependencies and container versions in committed lockfiles/manifests.

No AI API, CRM, email provider, paid domain, or additional cloud account is required. All demonstration data is synthetic. Canadian placement applies to GCP application resources and stored application data; GitHub-hosted CI is not represented as Canada-resident infrastructure.

### Agent orchestration and work ownership

The main GPT-6 Astra agent is the root orchestrator and information relay only. It may read agent messages, dispatch and steer work through collaboration tools, synthesize progress and final answers, and make scope or budget decisions from worker reports. It does not code, search the repository or web, inspect files through shell/browser tools, edit documentation, operate account interfaces, run tests, or perform verification directly. It verifies completion through worker-written evidence and independent reviewer reports, and delegates any follow-up inspection or search.

All substantive work is performed by delegated agents explicitly launched as **GPT-5.6 Luna with Max reasoning**. Every further delegation must also set `model='gpt-5.6-luna'`, `reasoning_effort='max'`, and `fork_turns='none'` or a positive bounded turn count; do not rely on parent-model inheritance or silently substitute another model. The working capacity is four concurrent agents total: the root plus three worker slots. Those three slots rotate among application, infrastructure, and verification/documentation work as dependencies allow; they are not permanent roles and do not imply a fourth simultaneous integration or review worker.

The root maintains a dependency-aware work queue from the commit ledger. Before dispatching a task, it gives one worker a bounded outcome, prerequisites, exact owned files or path globs, allowed shared files, required checks, and a handoff format. Parallel tasks must have disjoint write ownership. A worker that discovers an out-of-scope dependency reports it instead of editing another worker's paths. Shared contracts, generated clients, lockfiles, workflow files, root documentation, and other cross-cutting files are serialized behind their prerequisite handoffs.

Only one worker at a time is designated as the integration/commit worker. That designation can rotate, but while active that worker alone may stage files, modify the Git index, create or amend commits, rebase, merge, tag, or push. Other workers may edit only their assigned paths and must not perform concurrent Git-index or history operations. The integration worker checks the current tree and ownership ledger, incorporates completed handoffs in dependency order, runs the required integration checks, records the resulting commit SHA and evidence, and reports conflicts rather than discarding another worker's changes.

Every worker handoff states the assigned scope, paths changed or inspected, decisions and assumptions, commands/checks run with outcomes, generated evidence locations, unresolved risks, dependencies, and whether any cloud or external state changed. When a change crosses application, infrastructure, security, release, cost, or public-documentation boundaries, the root schedules an independent GPT-5.6 Luna / Max review after the implementation handoff is ready. That review uses an available worker slot, does not wait for a nonexistent extra slot, and returns findings to the root; the root then delegates any correction and revalidation.

Subagents do not make local orchestration continue while the host session is suspended. GitHub Actions or other cloud jobs may continue after a worker dispatches them, but observing results, making the next decision, and coordinating follow-up work still require an active orchestration session. Implementation is authorized. Workers may initialize Git, implement features, create the public GitHub repository, run non-billable CI, and make commits within the ownership rules above. Billable GCP provisioning remains blocked until every budget and independent-cleanup gate in this plan passes.

## 2. Application, interfaces, and behavior

### Customer workflow

1. Sign in and see a dashboard of imports, accepted/rejected/duplicate rows, recent activity, and worker status.
2. Upload a CSV, inspect a preview, and map its columns to contact fields.
3. Run background validation and review row-level errors and duplicate counts.
4. Explicitly confirm importing the valid rows; invalid and duplicate rows are excluded and available in reports.
5. Follow job progress, inspect the completed result, search the directory, and download clean/error reports.

Canonical fields: required `email`, `first_name`, and `last_name`; optional `company`, `country_code`, and `external_id`. Accept UTF-8 CSV including BOM, at most 10 MiB and 10,000 data rows. Reject invalid encoding, missing/duplicate mapped headers, oversized fields, and malformed rows with actionable messages. Do not execute formulas or accept spreadsheets, archives, or URLs as uploads.

Normalize surrounding whitespace, canonicalize email for matching, and uppercase valid two-letter country codes. Deduplicate by normalized email within the file and against the installation's directory. Keep the first valid occurrence; do not silently overwrite existing contacts. Produce distinct reasons for invalid records, within-file duplicates, and existing contacts. Neutralize spreadsheet-formula prefixes in downloadable CSVs.

Validation does not change the directory. Confirmation imports accepted records in a transaction, rechecks existing-contact conflicts, and records the actual inserted/skipped counts. Retry or duplicate delivery must not create duplicate contacts. Cancellation is allowed before the import transaction begins; an already-committing import finishes atomically.

### Access and user experience

- **Administrator:** manage users and roles, perform imports, inspect audit activity and operational information.
- **Operator:** upload, map, validate, confirm, retry/cancel eligible jobs, search contacts, and download reports.
- **Viewer:** read the dashboard, import results, and directory; no mutations or downloads.
- Seed an administrator through a protected bootstrap command. Generate credentials; never commit a universal cloud demo password. Disable public registration and SMTP-dependent flows. Administrators can issue temporary passwords with a required password change.
- Enforce permissions in the API, not only in navigation. Use short-lived access tokens, password hashing, login rate limits, explicit CORS origins, and server-side checks of current user state/role. Never log tokens, passwords, CSV contents, or contact PII.
- Screens: sign-in, overview, import wizard, validation review, job detail, searchable directory, user administration, and audit activity. Use a consistent sidebar, typography, restrained accent colors, clear status badges, charts, skeletons, empty/error states, pagination, and keyboard-accessible forms.

### API and durable state

Use the upstream `/api/v1` prefix and generate the TypeScript client from OpenAPI. Add resource groups for imports (upload, mapping, validate, confirm, retry, cancel, reports), jobs (status and attempts), contacts (search and pagination), administrator user management, and audit events. Accept an idempotency key on import confirmation. Return stable machine-readable error codes with safe user-facing messages.

Postgres stores users/roles, imports and mappings, validation row outcomes, contacts, job attempts, a transactional job outbox, and audit events. Index normalized contact email, job status/creation time, and foreign keys used by list/detail queries. Bound connection pools per API/worker process. Use Alembic for every schema change.

Redis is the Celery broker; Postgres is the durable authority for job status. A transactional outbox bridges database commits to queue publication. Workers claim jobs safely, propagate trace context, use bounded retries for transient failures, and reconcile stalled work after a restart. Replayed messages must be harmless. Show validation errors separately from infrastructure failures.

Store uploads/reports through a storage adapter: a shared filesystem volume for optional local use and private regional GCS buckets on GCP. Generate object keys; never trust upload filenames as paths. All downloads pass authorization checks. Expire intermediate files after seven days in the reusable profile and delete all demo objects at teardown; contacts remain until the customer deliberately removes the installation/data.

Expose separate liveness, dependency-aware readiness, and version endpoints. Serve Prometheus metrics on an internal-only endpoint. Display the deployed version and environment in the administrator view.

## 3. Infrastructure, delivery, observability, and cost controls

### Cloud-first execution

GitHub Actions builds and tests the images, publishes immutable image digests to the configured regional Artifact Registry repository, executes Terraform, deploys to GKE, runs browser tests, and collects evidence. Authenticate to GCP with Workload Identity Federation scoped to this repository and the appropriate GitHub environment. Separate build, infrastructure, deploy, runtime, and cleanup identities; no downloaded service-account keys.

Cloud integration tests use real Postgres and Redis containers on GitHub runners. A kind test exercises the Helm chart on a GitHub runner before any GKE provisioning. Keep Docker Compose, PowerShell instructions, and Unix instructions as optional developer conveniences.

Provide a small cross-platform Python deployment CLI with commands for `doctor`, configuration validation, `plan`, `deploy`, `verify`, `rollback`, `evidence`, and `destroy`. Every cloud operation requires an explicit customer, environment, and project. Customer configuration contains branding, region, project, environment, profile, image digest, namespace, resource sizing, and optional domain; secret values are referenced, never embedded. Validate configuration before invoking tools and redact secret-bearing outputs.

### Demo topology

- One zonal GKE Standard cluster, one fixed `e2-standard-4` node, bounded disks, no node autoscaling, and the regular release channel. Confirm quota, machine availability, and current prices before provisioning; do not silently choose another country or a larger machine.
- Separate staging and production-demo namespaces, credentials, databases, and Redis instances on the shared cluster. Clearly label this as a demonstration of environment separation, not independent production failure domains.
- Run Postgres and Redis inside the demo cluster with persistent volumes. Use a separate namespace for the compact observability stack.
- Use Helm for application deployments, workers, services, ingress configuration, resource limits, startup/readiness/liveness probes, service accounts, network policies, and migration Jobs. Two API replicas demonstrate rolling updates. Keep worker and data-service counts fixed for the budget demo.
- Reach app/Grafana through authenticated Kubernetes port forwarding. No public load balancer, DNS purchase, or unauthenticated operational dashboard is needed. Test ingress routing in kind; include opt-in TLS ingress configuration for customer deployments.
- Use Workload Identity for GCS and Secret Manager access. Generate secrets outside Terraform values/state and mount them into workloads through the GKE-supported secrets integration. Do not store plaintext secrets in Kubernetes manifests or repository files.

### Production profile

Implement a separate, explicit `managed` profile using a regional GKE cluster with private nodes, Cloud SQL PostgreSQL with backups/PITR, private Memorystore Redis, regional GCS, Secret Manager, restricted ingress/TLS, and environment-specific project/state boundaries. Give this profile conservative fixed sizing and deletion protection for durable data. Keep production database credential provisioning separate from Terraform's tracked secret values.

This profile receives Terraform validation, provider-schema checks, security checks, mocked Terraform tests, and rendered workload checks. It must be labeled **implemented, not live-tested**. The demonstration workflow must refuse to provision it under the USD 25 authorization. The customer guide explains the additional DNS, identity, networking, cost, and recovery prerequisites.

### Releases and recovery

- Pull requests run lint/type checks, backend tests, frontend build/tests, image build checks, dependency/secret scans, Terraform checks, and Helm/kind verification without deployment credentials.
- Build once and promote the exact image digest from staging to production-demo. Serialize releases per customer/environment and never use floating `latest` tags.
- Run an explicit migration Job before the application rollout. Use expand/contract changes compatible with the previous application version. Block release on migration failure.
- Verify readiness, rollout completion, and a business-flow smoke test. On rollout/smoke failure, restore the prior application release and report what failed. Never automatically reverse a database migration.
- Demonstrate a successful rolling release, a deliberately unhealthy release that cannot become ready, and recovery to the last good version. Keep failure injection disabled by default and restricted to demo tooling.
- Provide a separate backup/restore drill into a disposable database, verify record counts, and document the difference between application rollback and data recovery.
- Configure a protected production environment for actual customer use. Use a separately named `demo-prod` environment for the automated overnight rehearsal so it does not bypass real production approval rules.

### Observability

Use OpenTelemetry instrumentation for API requests, SQL, Redis, and worker jobs. Send traces through the collector to Tempo; scrape bounded-cardinality metrics with Prometheus; collect structured JSON logs with Grafana Alloy into Loki; use Grafana for all three. Correlate request/job logs through trace IDs without placing row contents, emails, or arbitrary IDs in metric labels.

Provision dashboards for request throughput/errors/latency, import outcomes, queue age, job attempts, worker health, and database connections. Add alert rules for unavailable API, elevated error ratio, oldest queued job, failed-job increase, and worker heartbeat loss. Capture a controlled alert firing and resolving. Alertmanager remains internal; external email/Slack notifications are not required.

### Budget and teardown contract

USD 25 is the total authorization. Do not treat free credits as permission to increase resource usage. GCP alerts and spend caps do not provide a hard limit for persistent GKE infrastructure: [Google's documented limitations](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps).

1. Complete inexpensive CI and kind tests before creating billable infrastructure.
2. Establish the project's current cost/resource baseline and obtain a current itemized estimate covering GKE management, VM, disks, IPs, storage, registry, telemetry, and cleanup services. If the baseline or estimate cannot be established, keep cloud provisioning blocked and continue other work.
3. Allow a single demo only when the estimated total through teardown is at most **USD 10**, including existing project usage attributable to this work. Reserve the remaining **USD 15** for delayed charges and cleanup; no automatic second paid attempt.
4. Limit cloud runtime to four hours from the first billable provisioning action. Start teardown earlier when evidence is complete. Do not extend the deadline to finish coding.
5. Install and verify a GCP-hosted expiry mechanism before GKE creation: Cloud Scheduler invokes a Cloud Workflows cleanup routine using an exact project/resource manifest. It must operate without this computer or the main GitHub run. Test its targeting/control flow using an innocuous sentinel before authorizing the real cluster.
6. The main workflow uses unconditional cleanup; the expiry workflow independently deletes the named demo cluster and allowlisted billable residues after the deadline. Neither cleanup path may delete unrelated resources or the GCP project. Retain enough private state to reconcile an interrupted cleanup.
7. Export sanitized evidence, destroy runtime resources, then remove temporary registry contents, uploads, unused disks/IPs, secrets, and bootstrap cleanup infrastructure once safe. Verify the remaining resource inventory rather than equating a successful destroy command with completion.
8. Record estimates, timestamps, resources, actual reported charges, and pending billing in a cost ledger. Do not invent final costs while billing is delayed. If cleanup fails, stop feature work, prioritize cleanup, and report the exact outstanding resource.

These controls reduce exposure but cannot promise a provider-enforced dollar cap. No cloud run proceeds unless its cost and independent teardown checks pass.

## 4. Tests, evidence, and acceptance criteria

### Functional and security checks

- Exercise the complete guided flow with valid, mixed-quality, duplicate-heavy, malformed, BOM, oversized, and formula-like CSV fixtures. Confirm expected row totals and exported contents.
- Test every role against protected API actions, including direct URL access, report downloads, disabled users, and role changes. Confirm no public signup and no sensitive fields in API errors or logs.
- Verify repeated confirmation, double-clicks, queue redelivery, Redis interruption, worker termination, and retry behavior do not duplicate directory records or strand jobs silently.
- Test a fresh migration, additive upgrade with existing records, the old application's compatibility after upgrade, and backup restoration into a fresh database.
- Use Playwright on the real application for the import journey, administration, directory search, error handling, keyboard navigation, and desktop/mobile layouts. Screenshots must come from working screens with deterministic synthetic fixtures.

### Deployment and operations checks

- Validate and test Terraform demo/managed profiles, configuration rejection, Helm rendering/schema rules, RBAC/network policy intent, and secret-reference handling.
- In CI kind, run migrations, deploy all core components, execute the import journey, restart a worker, roll forward, and roll back a failed release.
- Repeat the core journey on GKE. Confirm staging and production-demo cannot share application secrets or database contents.
- Run continuous requests during an API rolling update and report observed success/error counts; do not claim zero downtime without the measurement.
- Capture a correlated API-to-worker trace, searchable structured logs, populated metrics, and an alert firing/resolving.
- Verify primary and expiry cleanup behavior and the final GCP resource inventory.

### Public evidence and README

Create an extensive but navigable README with a branded repository banner, purposeful emojis, working CI badges, a table of contents, architecture and release-flow diagrams, and a feature/evidence matrix.

Embed actual screenshots of the overview, column mapping, validation results, completed import, directory, Grafana dashboard, trace waterfall, and alert state. Add a short demonstration recording or animated walkthrough. Distinguish local/CI screenshots from GKE screenshots in captions. Optimize media sizes, include alt text, and use repository-relative links. Do not use generated artwork as a substitute for application screenshots.

Include quickstarts for the cloud-first workflow and optional local setup, prerequisites, a sample customer configuration, deployment/promotion/rollback/teardown instructions, secret handling, troubleshooting, cost controls, and a customer handover checklist. Add source/license acknowledgments and an honest limitations section: shared demo cluster, in-cluster demo data services, production profile not live-tested, and no compliance certification claims.

Publish a tagged `v1.0.0` release only after required checks pass. Attach sanitized demo evidence and link passing workflow runs. The handover must state what ran, what remains unverified, the observed/estimated costs, and whether any billable resources remain.

Acceptance requires a usable public repository, at least 120 new substantive commits, passing required CI, a functioning guided import and directory, demonstrated deployment/recovery/observability, real screenshots, reproducible how-tos, and verified teardown. If an external blocker prevents a required live check, label the delivery incomplete for that criterion rather than substituting a fabricated result.

## 5. Implementation sequence and commit ledger

Target **128 new commits**, grouped below into 16 batches of eight. Each listed unit is a coherent change with appropriate validation, not a quota for whitespace edits. Keep the history truthful, with normal timestamps and the configured author. Extra corrective commits are allowed. Track actual commit SHAs and check results against this ledger during implementation.

| Batch | Eight substantive commit units |
| --- | --- |
| 1. Foundation | attributed upstream import; runtime/dependency locks; project configuration; obsolete automation removal; application branding; customer config contract; developer commands; contribution/architecture guidance |
| 2. Identity | role model/migration; API authorization; disabled public signup; admin bootstrap; user administration API; temporary-password flow; login hardening; authorization regression coverage |
| 3. Import persistence | import models; contact models/indexes; row-outcome storage; job-attempt model; outbox model; audit model; migration fixtures; bounded database sessions |
| 4. Validation | bounded CSV parser; column-mapping rules; field validation; canonicalization; within-file duplicate detection; directory conflict detection; report generation/formula protection; edge-case parser tests |
| 5. Job execution | Celery integration; outbox publication; validation worker; confirmation transaction; idempotency handling; bounded retry/reconciliation; cancellation semantics; worker failure/replay tests |
| 6. Application API | upload storage adapter; mapping/preview endpoints; validation/review endpoints; confirmation endpoints; job status/history; retry/cancel endpoints; contact search/pagination; authorized report downloads |
| 7. Import interface | responsive application shell; dashboard summary; upload interaction; column mapper; validation review; confirmation flow; job progress/detail; accessible error/empty/loading states |
| 8. Customer interface | directory table; directory search/filter/pagination; contact detail; import history; report downloads; administrator users/roles; audit view; frontend journey coverage |
| 9. Containers and local support | API image; worker image; frontend image/proxy; Compose core services; optional local telemetry; bootstrap/fixtures; Windows/Unix commands; container integration checks |
| 10. Kubernetes | Helm contract; API deployment/probes; worker deployment/health; services/ingress; demo stateful dependencies; environment namespaces/limits; RBAC/network policies; migration/release hooks |
| 11. GCP demo | provider/state bootstrap; regional artifact storage; VPC/subnet; zonal cluster/node pool; runtime identities; secret integration; GCS uploads/reports; customer provisioning outputs |
| 12. Managed profile and safeguards | managed cluster isolation; Cloud SQL/backups; Memorystore/private connectivity; production TLS/data protections; budget estimate gate; expiry cleanup workflow; scheduler/cleanup identity; teardown inventory reconciliation |
| 13. Delivery automation | PR validation pipeline; cloud image build/publish; GitHub federation bootstrap; infrastructure plan/apply; staging deployment/smoke; digest promotion; release rollback; end-to-end demo cleanup orchestration |
| 14. Observability | structured redacted logs; API/database instrumentation; worker trace propagation; application/job metrics; collector/Tempo; Alloy/Loki; Grafana dashboards; Prometheus/Alertmanager rules |
| 15. Acceptance and resilience | kind rehearsal; cloud-readiness checks; import load/replay exercise; rolling-release probe; unhealthy-release rollback drill; backup/restore drill; alert/trace evidence checks; cost/teardown evidence validation |
| 16. Publication and handover | architecture diagrams/banner; app screenshot gallery; observability screenshot gallery; recorded walkthrough; cloud quickstart; operations/recovery how-tos; customer handover/evidence matrix; release notes/final verification |

### Execution order and completion behavior

The root dispatches the next ready ledger units only after their prerequisites are supported by worker evidence. It keeps all three worker slots useful by assigning independent application, infrastructure, or verification/documentation tasks with non-overlapping path ownership, while reserving serialized work for shared contracts and integration. Finish bootstrap access and cloud identity configuration before the unattended portion where possible. A delegated worker uses Chrome for necessary account UI and visual verification; do not assume an interactive authentication challenge can always be completed without the user. Continue independent work if an external approval blocks one step.

Delegated workers run the development/test loop in GitHub-hosted runners and return validation/evidence handoffs. The root confirms milestones from those handoffs and independent Luna/Max review reports, without opening files or running checks itself. The local orchestration session still needs network access and must remain active while coordinating work; cloud jobs can finish independently once dispatched, but they do not autonomously trigger further orchestration while the host is suspended. Do not start paid resources simply to wait for application implementation.

Build and prove the app in CI first, then rehearse the chart in kind, then run the bounded GKE demonstration, collect evidence, verify teardown, and finish the README/release. Successful tests must correspond to the final code, and evidence must identify the tested revision and deployed image digests.

Implementation began with the user's explicit authorization on 2026-09-22. This document still does not itself provision resources; actual external changes and evidence are recorded in the implementation ledger.
