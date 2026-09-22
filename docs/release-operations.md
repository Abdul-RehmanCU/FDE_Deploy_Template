# Release and recovery operations

This runbook keeps application rollout, database migration, data recovery, and infrastructure cleanup as separate decisions. Commands are examples; customer configuration and the current evidence gate remain authoritative.

## Release inputs

Before a release, record:

- customer, environment, GCP project, namespace, and Git commit;
- backend and frontend image digests built from that commit;
- current database revision and proposed migration revision;
- previous Helm revision and image digests;
- passing CI and kind workflow URLs;
- cost/expiry gate state for any paid environment.

Never promote `latest` or rebuild between environments.

## Staging rollout

1. Validate the customer configuration and current HEAD.
2. Fetch the immutable image digests from the build output.
3. Render the chart and confirm only the intended customer/environment changes.
4. Run the migration Job. Stop on failure.
5. Deploy staging with Helm's atomic wait behavior and a bounded timeout.
6. Verify liveness, readiness, version, login, upload, mapping, validation, confirmation, report authorization, and directory search.
7. Confirm API, worker, publisher, PostgreSQL, Redis, and telemetry components report healthy state.

```bash
uv run --project tooling/fde fde verify path/to/customer.yaml
kubectl -n CUSTOMER-STAGING get deploy,statefulset,job,pod
helm -n CUSTOMER-STAGING history RELEASE_NAME
```

## Digest promotion

Promote the exact tested digests to production-demo. The release record must show that staging and production-demo refer to the same content hashes. Run the migration Job again against the target database, then deploy and smoke-test.

Serialize release workflows per customer/environment so a second rollout cannot replace the recorded rollback target.

## Rolling update measurement

Run a continuous bounded request probe before the rollout, through readiness convergence, and after the rollout. Record total attempts, successes, connection failures, HTTP error counts, latency distribution, start/end timestamps, previous/new digests, and Kubernetes events.

Do not claim zero downtime from rollout status alone. Report the observed counts.

## Unhealthy-release drill

Failure injection is disabled by default and restricted to the demo workflow.

1. Record the last good Helm revision and application version.
2. Deploy the deliberately unhealthy image/configuration.
3. Confirm the new pods do not become ready and the smoke check fails.
4. Roll back only the application release:

   ```bash
   uv run --project tooling/fde fde rollback path/to/customer.yaml
   ```

5. Verify the previous application version, readiness, business smoke flow, and request-probe results.
6. Preserve the failed rollout events and rollback evidence.

The rollback command does not reverse an Alembic migration. Releases must use expand/contract schema changes compatible with the prior application.

## Worker recovery drill

During validation, terminate the worker pod after durable job creation. Verify the publisher/reconciler requeues stale work, a replacement worker claims it, attempt history remains bounded, and no directory record is duplicated. Repeat confirmation delivery and confirm the idempotency key and normalized email constraint keep the result stable.

## Backup and restore drill

Application rollback and data recovery are different operations. Follow [database recovery](database-recovery.md) to restore into a disposable database, verify record counts and selected synthetic checksums, then delete the disposable target. Do not overwrite the active database for a demonstration.

## Alert and telemetry evidence

Capture a synthetic request through API, outbox, and worker with one correlated trace ID. Verify:

- request and job spans in Tempo;
- structured API/worker logs in Loki without query strings, emails, row data, or tokens;
- request, import, queue, worker, attempt, and database metrics in Prometheus/Grafana;
- each alert rule can fire and resolve under a controlled condition.

Alertmanager stays internal; no external notification provider is required.

## Teardown

Export sanitized evidence before deletion. Invoke guarded destroy, then independently reconcile the exact resource inventory. If any cluster, VM, disk, address, registry content, bucket/object generation, secret, workflow, scheduler job, Helm release, or Kubernetes resource remains, cleanup is incomplete.

Delayed billing stays marked pending until the provider reports it. A successful Terraform destroy is not final teardown evidence.
