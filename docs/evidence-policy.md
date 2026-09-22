# Evidence policy

Evidence must let a reviewer connect a claim to an exact revision, environment, action, and result without exposing credentials or customer data.

## Required metadata

Every evidence package records:

- Git commit and image digests;
- workflow run and job URLs;
- customer/environment labels using approved non-sensitive identifiers;
- execution surface: unit, GitHub service containers, browser CI, kind, or GKE;
- start/end timestamps and tool versions;
- command or scenario name;
- pass, fail, skipped, or incomplete status;
- known limitations and unresolved follow-up.

Static validation cannot satisfy a live criterion. A rendered chart is not a deployed workload; a Terraform validate is not a provider plan; kind is not GKE; an application rollback is not database recovery; a destroy exit code is not final inventory.

## Allowed public evidence

- deterministic synthetic-data screenshots;
- WebM recordings that show no credential entry or secret output;
- redacted command summaries and test counts;
- workflow/job URLs and immutable artifact IDs;
- image digests and release revisions;
- resource counts/names already designed as non-sensitive demo identifiers;
- sanitized cost estimates and delayed-charge status;
- aggregate request success/error/latency measurements.

## Forbidden public evidence

- bearer tokens, temporary passwords, service-account keys, cookies, or browser storage state;
- raw Playwright traces, HAR files, or network logs containing authorization headers;
- `.env` files, mounted secret contents, database/Redis URLs, kubeconfigs, or Terraform state;
- uploaded CSV contents or real contact fields;
- unfiltered cluster/application logs or telemetry exports;
- customer billing-account numbers, user identities, or unrelated project inventory.

If a published artifact may contain forbidden content, delete it, verify artifact absence through the provider API, record the removal in the implementation ledger, and regenerate a sanitized replacement.

## Screenshot standard

Screenshots must come from working screens at the stated revision. Before capture:

1. load deterministic synthetic state;
2. remove debug overlays and inherited branding;
3. scroll the target into a stable position;
4. use viewport capture for layouts with sticky elements, or capture a bounded component;
5. check desktop and mobile clipping, focus state, readable labels, and empty/error/loading behavior;
6. inspect the resulting image before committing it.

Captions identify local/CI/kind/GKE origin. Application screenshots never substitute for Grafana, trace, alert, rollout, or teardown evidence.

## Browser recordings

The CI browser suite disables traces and uploads only its HTML report, explicit PNG evidence, and WebM recordings. Authentication setup uses request contexts rather than recording credential entry. The artifact path excludes `playwright/.auth`.

Before promoting browser media into `docs/media`, an independent reviewer checks the actual pixels and verifies the tested SHA from the workflow artifact.

## Cloud evidence package

The final sanitized archive should include:

- manifest with SHA-256 hashes for every included file;
- deployment configuration with secret references only;
- Terraform plan/apply summaries and resource inventory;
- Kubernetes/Helm rollout and rollback summaries;
- browser flow screenshots/video;
- Grafana dashboard, Tempo trace, Loki search, and alert firing/resolution images;
- backup/restore record counts;
- rolling request measurement;
- cost ledger and final residue inventory;
- handover record with incomplete criteria clearly marked.

Keep private raw evidence only in the approved restricted location and for the agreed retention period.
