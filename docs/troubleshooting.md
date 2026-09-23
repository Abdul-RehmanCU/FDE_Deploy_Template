# Troubleshooting

Start with the execution surface and exact revision. A local success does not diagnose a GitHub runner, kind, GKE, or managed-service failure.

## Configuration is rejected

Run `fde validate-config` and read the exact field error. Common causes are a missing customer/environment/project, region and zone mismatch, mutable image tag where a digest is required, plaintext secret value, managed profile under demo authorization, or customer mismatch between the command and configuration.

Do not bypass validation with direct Terraform or Helm commands.

## API starts but readiness fails

Liveness proves only that the process runs. Readiness also checks dependencies.

```bash
curl -fsS http://localhost:8000/api/v1/health/live
curl -fsS http://localhost:8000/api/v1/health/ready
```

Check mounted `DATABASE_URL_FILE`, `REDIS_URL_FILE`, and `SECRET_KEY_FILE` paths without printing their contents. Verify PostgreSQL and Redis service names, network policies, credentials, migrations, connection-pool limits, and statement timeout configuration.

## Login is rate-limited or immediately invalidated

The limiter is shared through Redis and fails closed. Confirm Redis connectivity and wait for the bounded window rather than disabling the limit. Tokens become invalid after role, active-state, or password changes; sign in again. A temporary-password account may access only its password-change path until rotation succeeds.

## Upload is rejected

The API accepts one UTF-8 CSV with optional BOM, at most 10 MiB and 10,000 data rows. Spreadsheet, archive, URL, invalid encoding, malformed quoting, duplicate/missing mapped headers, or fields above business limits produce stable error codes.

Use the deterministic fixtures under `fixtures/customer-data/` to separate parser behavior from customer-file quality. Do not paste real rows into logs or issues.

## Validation or confirmation remains queued

PostgreSQL is the job authority. Inspect the import, job, attempts, and outbox rows using approved read-only diagnostics. Then check:

- publisher process and its bounded broker timeout;
- Redis availability;
- worker heartbeat/metrics endpoint;
- queue age and attempt count;
- stale reconciliation interval;
- cancellation state;
- shared upload storage visibility between API and worker.

Replayed messages should be harmless. Do not manually mark a job successful.

## Report download returns 403 or 404

Viewers cannot download reports. Operators and administrators can download only reports belonging to imports they may read. A 404 after retention may mean the intermediate object expired; the contact directory remains durable. Check audit activity without logging the object content.

## Frontend shows API authorization errors

Verify the frontend proxy's `BACKEND_UPSTREAM`, the browser-facing origin in CORS, and that `/api/` is proxied while `/internal/metrics` is not. Confirm the generated client matches the current OpenAPI contract and that the token belongs to the expected role.

## Helm install times out

```bash
kubectl -n CUSTOMER-ENV get pod,job,pvc
kubectl -n CUSTOMER-ENV describe pod POD_NAME
kubectl -n CUSTOMER-ENV logs POD_NAME --all-containers --tail=200
helm -n CUSTOMER-ENV status RELEASE_NAME
```

Check image availability, secret volume keys, PVC ownership, PostgreSQL/Redis readiness, migration Job output, read-only-root writable mounts, resource quotas, and network policies. Sanitize logs before sharing them.

For the first live GKE staging attempt, Cloud Logging recorded `FailedMount` on `runtime-secrets` with `secretmanager.versions.access` denied. The chart annotates its Kubernetes service account to impersonate a per-environment IAM service account, so the secret-level `roles/secretmanager.secretAccessor` grant must target that IAM service account. A direct grant to the Kubernetes principal alone does not authorize the impersonated identity. See [GKE workload identity impersonation](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/workload-identity) and [GKE Secret Manager CSI setup](https://docs.cloud.google.com/secret-manager/docs/secret-manager-managed-csi-component). Confirm the secret policy member and the service-account annotation match without reading or printing secret versions.

The same attempt's frontend log also reported `host not found in upstream` for the API Service. The GKE Calico policy now permits TCP/UDP port 53 to the cluster's service CIDR, consistent with [GKE's kube-dns network-policy guidance](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/nodelocal-dns-cache). Check the actual `kube-dns` Service IP and a Pod's `/etc/resolv.conf` on a future cluster before attributing any remaining lookup failure to policy. Kubernetes [default-deny egress](https://kubernetes.io/docs/concepts/services-networking/network-policies/) blocks DNS unless allowed.

After an atomic Helm rollback removes the Pods, use [Cloud Logging's historical GKE logs](https://docs.cloud.google.com/kubernetes-engine/docs/troubleshooting/introduction-logging) to inspect prior `events` and staging container logs. Do not redeploy solely to recover a deleted Pod's events.

## Terraform provider checksum mismatch

Provider locks include Linux and Windows hashes. Do not delete the lockfile. Regenerate it in the affected root with the pinned Terraform version:

```bash
terraform providers lock -platform=linux_amd64 -platform=windows_amd64
```

Review and commit only the expected hash additions.

## Expiry sentinel or cleanup is incomplete

Stop feature/deployment work. Compare the authoritative expiry ID, project number, manifest SHA, resource labels, names, and creation timestamps. Check all three exact-minute schedules and Workflow executions. A stale trigger must no-op; an ownership mismatch must not delete. Reconcile partial results and rerun only the exact allowlisted cleanup path.

Cloud Asset Inventory is an [eventually consistent metadata index](https://docs.cloud.google.com/asset-inventory/docs/asset-inventory-overview). A deleted node pool can remain in search results after the GKE deletion operation has completed. The cleanup workflow records that as `asset_index_pending` and relies on direct GKE, Compute, Storage, Artifact Registry, Secret Manager, Workflow, and Scheduler reads to establish whether billable resources remain. Recheck the index later; do not relaunch resources to clear it.

## Billing appears unchanged

Billing data is delayed. Record the query timestamp, currency, billing period, and pending status. Do not infer zero final cost from a current zero row. Keep the cleanup reserve and continue inventory checks.

## Evidence is unsafe or misleading

Delete a published artifact that may contain tokens, browser storage, raw traces, customer data, or secret-bearing output. Confirm deletion through the provider API and record it in the implementation ledger. Regenerate evidence under [the evidence policy](evidence-policy.md).
