# Security policy

## Reporting a vulnerability

Use GitHub private vulnerability reporting for this repository. Do not open a public issue containing exploit details, credentials, customer data, infrastructure identifiers, or proof material that could expose a deployed installation.

Include:

- affected commit, component, route, chart, or Terraform module;
- required role and trust boundary;
- reproducible steps using synthetic data;
- observed and expected behavior;
- potential confidentiality, integrity, availability, cost, or cleanup impact;
- any known mitigation.

Never include live tokens, passwords, service-account keys, kubeconfigs, Terraform state, database dumps, customer CSVs, browser storage, HAR files, or raw traces. Redact provider/project details unless they are essential and approved for the private report.

## Supported scope

Before `v1.0.0`, only the current `main` branch is maintained. After a release, this file will list supported versions and response expectations. The managed GCP profile is currently implemented but not live-tested; that limitation does not make security findings in its code out of scope.

Report issues involving:

- authentication, token invalidation, password handling, and login rate limits;
- administrator/operator/viewer authorization, including direct API requests and report downloads;
- CSV parsing, formula neutralization, object-key/path handling, and data isolation;
- job idempotency, cancellation, replay, outbox locking, and recovery;
- logging, metrics, traces, screenshots, and evidence privacy;
- container, Kubernetes, Helm, ingress, network policy, RBAC, or secret mounts;
- Workload Identity Federation, IAM scope, Terraform state, cleanup ownership, cost gates, and expiry behavior;
- dependency or supply-chain compromise.

## Security properties

- No public signup or email recovery path.
- No universal committed password or cloud credential.
- API authorization is authoritative; hidden UI controls are secondary.
- Viewer accounts cannot mutate imports or download reports.
- PostgreSQL is the durable job authority; queue replay must not duplicate contacts.
- Uploaded names never determine storage paths.
- Secret values stay out of repository, Terraform state, Helm values, logs, and public evidence.
- Internal metrics and Grafana are not exposed through the public frontend proxy.
- Demo cleanup requires exact project, manifest, ownership label, name, and creation fingerprint checks.
- Cleanup never deletes the GCP project or unrelated resources.

## Public discussion

After a fix is available, maintainers may publish a sanitized advisory describing affected versions, impact, remediation, and acknowledgments. Public text must preserve the evidence policy and customer confidentiality.
