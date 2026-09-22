# Managed profile handoff

This profile is implemented and statically validated, but it is not deployed by
the bounded demo workflow and has not been live-tested. Run it only in a
customer-controlled production project with private connectivity to the VPC.

After `terraform apply`, connect as a Cloud SQL database administrator from a
private-network execution environment using the managed client certificate and
run the emitted pgAudit bootstrap statement:

```bash
terraform output -raw postgres_bootstrap_sql | psql "$ADMIN_DATABASE_URL"
```

`ADMIN_DATABASE_URL` must use TLS verification and must not be committed or
printed. The statement is `CREATE EXTENSION IF NOT EXISTS pgaudit;`. Terraform
sets the Cloud SQL flags but cannot create the database extension.

Only after pgAudit creation succeeds, render the exact private endpoint values
into the Helm release instead of copying addresses by hand. Helm then runs the
migration Job:

```bash
terraform output -json helm_managed_network_policy > managed-network-policy.json
helm upgrade --install fde ../../../helm/fde \
  --namespace production --create-namespace \
  --values ../../../helm/fde/values-managed.example.yaml \
  --values customer-values.yaml \
  --set-json networkPolicy.managedServices="$(cat managed-network-policy.json)"
```

The emitted map contains the provisioned Cloud SQL private address as a `/32`,
the provisioned Memorystore private address as a `/32`, and the verified Redis
TLS port `6378`. The chart allows API, worker, publisher, and migration traffic
only to those endpoints on PostgreSQL `5432` and Redis `6378`.

The customer must also provide a real domain/TLS path, enable project Data
Access audit logging to its external log sink, and decide whether to add a
Binary Authorization attestor/signing policy. This template requires immutable
image digests but does not claim signed-only admission.
