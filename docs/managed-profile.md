# Managed production profile

Status: **implemented and statically validated; not live-tested**.

The managed profile is a separate opt-in topology for a real customer environment. It is intentionally blocked by the demo's USD 25 authorization and cannot be selected by the paid-demo workflow.

## Topology

- regional private-node GKE cluster;
- Cloud NAT and private service access;
- regional HA Cloud SQL for PostgreSQL with backups and point-in-time recovery;
- Standard HA Memorystore Redis with transport encryption and authentication;
- regional, versioned GCS storage;
- Secret Manager containers and GKE Workload Identity;
- restricted ingress/TLS configuration;
- environment-specific Terraform state and project boundaries;
- deletion protection on durable data services.

The root composition is `infra/terraform/environments/managed`. Customer input starts from `infra/config/customers/managed.example.yaml`.

## Required customer decisions

Before any plan can be considered deployable, agree on:

- production and recovery projects, organizations/folders, and billing ownership;
- DNS zone, certificate issuer, hostname, and ingress controls;
- workforce identity and administrator/operator/viewer onboarding;
- VPC ranges, peering, egress, firewall, and customer connectivity;
- Cloud SQL sizing, maintenance, backup retention, PITR window, and recovery objectives;
- Redis capacity and acceptable failover behavior;
- GCS retention, lifecycle, legal hold, and deliberate data-deletion process;
- Secret generation/rotation authority and break-glass access;
- logging/telemetry retention and access controls;
- cost owner, budgets, escalation, and ongoing operational ownership.

## Credential boundary

Terraform creates secret containers and IAM relationships, not production credential values. Database credentials are generated and inserted through an approved secret process outside Terraform state. Workloads reference mounted values; repository and Helm values contain no plaintext secret.

No downloaded service-account key is supported. Build, infrastructure, deployment, runtime, and cleanup identities remain separate and use repository/environment-scoped federation.

## Validation that exists

- Terraform formatting and initialization with Linux/Windows provider locks;
- provider-schema validation for the root and module;
- customer configuration validation;
- static IAM regression checks for identity scope;
- Helm schema/render/kubeconform with the common application chart;
- managed profile output explicitly stating `implemented_not_live_tested`.

These checks do not prove quota, private networking, Cloud SQL/Redis creation, GKE rollout, backup restoration, failover, TLS, DNS, cost, or teardown in a real project.

## Pre-production acceptance

Before describing this profile as production-ready:

1. obtain security/network/database review for the exact plan;
2. deploy into a dedicated non-production project with representative policies;
3. run migration compatibility and load tests;
4. measure rolling releases and an unhealthy-release rollback;
5. exercise worker interruption and Redis disruption;
6. restore a backup to an isolated Cloud SQL instance and verify counts;
7. confirm private ingress/TLS/DNS and identity behavior;
8. validate telemetry privacy and alert routing;
9. measure actual costs over a representative period;
10. test documented cleanup without bypassing durable-data deletion protection.

Record external blockers as incomplete criteria rather than replacing live evidence with a static check.
