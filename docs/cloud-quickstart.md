# Cloud-first quickstart

This guide prepares one short-lived GCP demonstration in Montréal. It does not authorize provisioning. The deployment gate must pass at the exact commit being deployed.

## Prerequisites

- A dedicated GCP project with billing attached and no unrelated workloads.
- Repository administrator access for GitHub environments and Workload Identity Federation.
- `gcloud`, Terraform 1.15.8, Helm, `kubectl`, Python 3.14, and `uv`.
- Current passing CI, including real PostgreSQL/Redis tests, browser journeys, image builds, and kind rehearsal.
- Independent review of the exact resource manifest and expiry cleanup revision.

Do not create a service-account key. The bootstrap stack creates repository-scoped Workload Identity Federation providers and separate build, infrastructure, deployment, runtime, and cleanup identities.

## 1. Select and verify the project

```bash
gcloud config set project YOUR_DEDICATED_PROJECT
gcloud auth list
gcloud projects describe YOUR_DEDICATED_PROJECT
gcloud billing projects describe YOUR_DEDICATED_PROJECT
```

Record the project number, active account, billing-account attachment, enabled APIs, and current resource inventory. Stop if the project contains unrelated resources that cannot be cleanly separated from the exact allowlist.

## 2. Prepare customer configuration

Copy `infra/config/customers/demo.example.yaml`. Replace the customer, project, immutable image digests, expiry, and resource-manifest placeholders. Secret fields must be references; never place secret values in the file.

```bash
uv run --project tooling/fde fde validate-config path/to/customer.yaml
uv run --project tooling/fde fde doctor path/to/customer.yaml
```

The demo profile accepts only `northamerica-northeast1` and the bounded topology in the plan. The CLI refuses the managed profile under the demo authorization.

## 3. Reconcile cost evidence

Review `infra/cost/demo-estimate.yaml` and `infra/cost/ledger.demo.json`. Refresh catalog prices and the authenticated billing baseline if either is stale. The paid gate requires:

- estimated work-attributable total at or below USD 10;
- USD 15 held back for delayed charges and cleanup;
- current CI and kind success at the exact HEAD;
- expiry start at an exact UTC minute, with all attempts inside four hours;
- an exact resource manifest and matching project number;
- independent review recorded for the same revision.

```bash
uv run --project tooling/fde fde gate path/to/customer.yaml path/to/evidence.json
```

## 4. Install expiry before runtime

The expiry state is separate from the demo state so it can be installed and proven first.

```bash
terraform -chdir=infra/terraform/environments/expiry init
terraform -chdir=infra/terraform/environments/expiry plan -out=expiry.tfplan
terraform -chdir=infra/terraform/environments/expiry apply expiry.tfplan
```

Invoke the workflow with an innocuous sentinel manifest. Confirm exact project/resource targeting, retry behavior, stale-trigger refusal, and Scheduler-to-Workflows authorization. Do not create GKE until this evidence is captured.

## 5. Create and apply reviewed plans

```bash
uv run --project tooling/fde fde plan path/to/customer.yaml
uv run --project tooling/fde fde deploy path/to/customer.yaml
```

The saved plan must be fresh, tied to current HEAD and customer/environment/project, and pass the release gate. The first billable action starts the four-hour maximum runtime clock.

## 6. Verify and collect evidence

```bash
uv run --project tooling/fde fde verify path/to/customer.yaml
uv run --project tooling/fde fde evidence path/to/customer.yaml
```

Verify staging before production-demo. Promote exact image digests, run the migration Job, complete the browser smoke journey, measure continuous requests during rollout, inject the controlled unhealthy release, verify Helm rollback, restore a backup into a disposable database, and capture the observability evidence.

## 7. Destroy and reconcile

```bash
uv run --project tooling/fde fde destroy path/to/customer.yaml
uv run --project tooling/fde fde evidence path/to/customer.yaml
```

Confirm the remaining inventory for GKE clusters, Compute Engine instances/disks/addresses, Artifact Registry repositories, GCS buckets and object generations, Workflows, Scheduler jobs, secrets, Helm releases, and Kubernetes resources. Preserve delayed billing as pending; never report an invented final cost.
