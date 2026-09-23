# Customer handover record

Complete this record for each installation. Replace every `PENDING` value with evidence or leave it explicitly unresolved. Never copy credentials, tokens, raw Terraform state, kubeconfigs, customer contact data, or unsanitized traces into this document.

## Installation identity

| Field | Value |
| --- | --- |
| Customer | PENDING |
| Environment | PENDING |
| GCP project ID / number | PENDING |
| Region / zone | PENDING / PENDING (record privately for the customer) |
| Namespace | PENDING |
| Git commit | PENDING |
| Backend digest | PENDING |
| Frontend digest | PENDING |
| Helm release / revision | PENDING |
| Database revision | PENDING |

## What was run

| Check | Status | Evidence |
| --- | --- | --- |
| Current-head CI | PENDING | Workflow URL |
| Real PostgreSQL/Redis tests | PENDING | Job URL and test count |
| Desktop/mobile browser journeys | PENDING | Job URL and sanitized artifact |
| kind deployment and core import | PENDING | Job URL, image IDs, pod/job status |
| Expiry sentinel | PENDING | Workflow execution and exact manifest hash |
| Terraform reviewed plan | PENDING | Redacted plan summary and saved-plan hash |
| Staging deployment and smoke | PENDING | Workflow URL and digests |
| Production-demo promotion | PENDING | Workflow URL and same digests |
| Rolling request measurement | PENDING | Attempts/successes/errors/latency |
| Unhealthy release and rollback | PENDING | Failed revision, restored revision, smoke |
| Worker interruption/replay | PENDING | Job/attempt IDs and final counts |
| Backup restore drill | PENDING | Disposable target and record counts |
| Alert firing/resolution | PENDING | Rule, timestamps, screenshots |
| Trace/log/metrics correlation | PENDING | Sanitized trace ID and screenshots |

## Accounts and access

- [ ] Named administrator account transferred through an approved secret channel.
- [ ] Temporary password changed and the initial credential discarded.
- [ ] Operator and viewer accounts match the agreed least-privilege assignments.
- [ ] GitHub environments and required reviewers are documented.
- [ ] GCP Workload Identity providers and service-account purposes are documented.
- [ ] No downloaded service-account key exists.
- [ ] Kubernetes and Grafana access uses authenticated, time-bounded port forwarding.

## Operating procedures

- [ ] Customer knows how to upload/map/validate/confirm a CSV.
- [ ] Customer understands invalid, file-duplicate, and existing-contact outcomes.
- [ ] Customer knows viewer accounts cannot mutate or download reports.
- [ ] Release, verification, application rollback, and database recovery procedures were reviewed.
- [ ] Upload/report retention and deliberate contact deletion responsibilities were reviewed.
- [ ] Dashboard, trace, log, metric, and alert locations were reviewed.
- [ ] Escalation path and ownership boundaries were recorded outside this public repository.

## Cost record

| Field | Value |
| --- | --- |
| Baseline timestamp and currency | PENDING |
| Estimated total through teardown | PENDING |
| First billable action | PENDING |
| Primary / recovery / final expiry | PENDING |
| Runtime end | PENDING |
| Charges currently reported | PENDING |
| Charges pending provider delay | PENDING |

The provider does not enforce the repository's USD 25 authorization as a hard cap. The handover must preserve that limitation.

## Teardown reconciliation

Record a final inventory for:

- GKE clusters and node pools;
- Compute Engine instances, disks, snapshots, and addresses;
- Artifact Registry repositories and temporary image versions;
- GCS buckets and every object generation;
- Secret Manager secrets created for the demonstration;
- Cloud Workflows and Scheduler jobs;
- Helm releases, namespaces, PVCs, Jobs, Services, and LoadBalancers;
- temporary identities, bindings, and bootstrap cleanup resources.

Final state: **PENDING**. Do not write “clean” until the inventory is empty for the exact demo manifest and delayed charges are correctly labeled.

## Known limitations and unresolved items

- Demo staging and production-demo share one zonal cluster and are not independent failure domains.
- Demo PostgreSQL and Redis are in-cluster services.
- The managed profile is implemented but not live-tested unless separately evidenced here.
- No compliance certification is implied.
- PENDING: list every external blocker or skipped live check.

## Acceptance

| Role | Name | Date | Decision / notes |
| --- | --- | --- | --- |
| Delivery engineer | PENDING | PENDING | PENDING |
| Customer administrator | PENDING | PENDING | PENDING |
| Independent reviewer | PENDING | PENDING | PENDING |
