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
uv run --project tooling/fde fde validate-config --config path/to/customer.yaml
uv run --project tooling/fde fde doctor --config path/to/customer.yaml --cloud
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

The authorized cost evidence is supplied privately to the protected workflow as `DEMO_COST_EVIDENCE_JSON`. It must set `paid_provisioning_allowed: true` and contain a billing/resource baseline observed within 30 minutes. The committed planning ledger intentionally keeps this flag false.

## 4. Seed keyless identity once, then install expiry

The first bootstrap cannot authenticate through a federation provider that does not yet exist. An authorized project owner performs this one-time, non-GKE seed with Application Default Credentials:

```bash
uv run --project tooling/fde fde bootstrap \
  --config path/to/customer.yaml --customer CUSTOMER --environment staging --project PROJECT_ID \
  --terraform-dir infra/terraform/bootstrap --state-bucket STATE_BUCKET \
  --github-repository OWNER/FDE_Deploy_Template --confirm-project PROJECT_ID
```

Configure these exact GitHub environments and variables from the bootstrap outputs:

| Environment | Identity contract |
| --- | --- |
| `demo-build` | build provider and `GCP_BUILD_SERVICE_ACCOUNT` |
| `demo-infrastructure` | infrastructure provider and `GCP_INFRA_SERVICE_ACCOUNT` |
| `demo-staging` | deploy provider and `GCP_DEPLOY_SERVICE_ACCOUNT` |
| `demo-prod` | deploy provider and `GCP_DEPLOY_SERVICE_ACCOUNT`; separate from real protected `production` |
| `demo-cleanup` | cleanup provider and `GCP_CLEANUP_SERVICE_ACCOUNT` |

Set `GCP_WIF_PROVIDER` in each environment to its exact provider output. Then manually dispatch `Bootstrap and expiry guard`, or the gated `Bounded GCP demo rehearsal`. The workflow applies the separate expiry state, proves correct sentinel success, wrong-fingerprint rejection, and early-cleanup refusal before GKE. A generation-zero state-bucket object consumes the single paid-run authorization so another dispatch cannot start a second paid run. No recurring paid trigger is configured.

## 5. Create and apply reviewed plans

```bash
uv run --project tooling/fde fde plan \
  --config path/to/customer.yaml --customer CUSTOMER --environment staging --project PROJECT_ID \
  --terraform-dir infra/terraform/environments/demo --backend-bucket STATE_BUCKET \
  --state-prefix demo/EXPIRY_ID --out /absolute/path/demo.tfplan --expiry-id EXPIRY_ID

uv run --project tooling/fde fde deploy-infrastructure \
  --config path/to/customer.yaml --customer CUSTOMER --environment staging --project PROJECT_ID \
  --gate path/to/release-gate.json --cost path/to/private-current-cost.yaml \
  --terraform-dir infra/terraform/environments/demo --plan /absolute/path/demo.tfplan \
  --expiry-terraform-dir infra/terraform/environments/expiry \
  --expiry-evidence path/to/expiry-evidence.json
```

After apply, render configuration and Helm values from the signed image manifest plus live Terraform outputs. Validate parity, then deploy each environment:

```bash
uv run --project tooling/fde fde deploy-release \
  --config path/to/rendered-staging.yaml --customer CUSTOMER --environment staging --project PROJECT_ID \
  --chart infra/helm/fde --values path/to/rendered-staging-values.yaml
```

The saved plan must be fresh, tied to current HEAD and customer/environment/project, and pass the release gate. The first billable action starts the four-hour maximum runtime clock. The repository workflow builds once after Artifact Registry exists and promotes those exact signed digests from staging to `demo-prod`.

## 6. Verify and collect evidence

```bash
uv run --project tooling/fde fde verify \
  --config path/to/customer.yaml --customer CUSTOMER --environment staging --project PROJECT_ID
uv run --project tooling/fde fde evidence \
  --config path/to/customer.yaml --customer CUSTOMER --environment staging --project PROJECT_ID \
  --output-dir path/to/private-evidence
```

Verify staging before production-demo. Promote exact image digests, run the migration Job, complete the browser smoke journey, measure continuous requests during rollout, inject the controlled unhealthy release, verify Helm rollback, restore a backup into a disposable database, and capture the observability evidence.

## 7. Destroy and reconcile

```bash
uv run --project tooling/fde fde destroy \
  --config path/to/customer.yaml --customer CUSTOMER --environment staging --project PROJECT_ID \
  --terraform-dir infra/terraform/environments/demo --confirm-customer CUSTOMER \
  --expiry-id EXPIRY_ID --expiry-terraform-dir infra/terraform/environments/expiry \
  --manifest-file path/to/reviewed-fallback-manifest.json
```

Confirm the remaining inventory for GKE clusters, Compute Engine instances/disks/addresses, Artifact Registry repositories, GCS buckets and object generations, Workflows, Scheduler jobs, secrets, Helm releases, and Kubernetes resources. Preserve delayed billing as pending; never report an invented final cost.

Immediately after runtime and expiry cleanup are proven and sanitized evidence is exported, the project owner retires the bootstrap identity with local ADC. Automation must not revoke the WIF/cleanup identity it is currently using. Billing can be queried later with zero resources:

```bash
python scripts/finalize_bootstrap.py \
  --project PROJECT_ID --state-bucket STATE_BUCKET --github-repository OWNER/FDE_Deploy_Template \
  --confirm FINALIZE-BOOTSTRAP --evidence-out path/to/private-final-bootstrap-evidence.json
```

This command targets only bootstrap-managed IAM/WIF/service-state resources, confirms that only the labeled state bucket remains in Terraform state, removes all state-object generations, deletes that exact bucket last, and fails if the FDE WIF pool, four automation service accounts, or their project IAM bindings remain. The selected Google APIs intentionally remain enabled because the Terraform resources set `disable_on_destroy=false`; enabled APIs alone have no runtime charge and disabling them could affect unrelated project defaults.
