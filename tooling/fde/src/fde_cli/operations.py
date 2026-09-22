from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from .config import InstallationConfig
from .cost import CostGate, load_cost_gate
from .gate import load_release_gate
from .process import executable, redact, run


class OperationError(RuntimeError):
    pass


def validate_paid_cost_gate(cost: CostGate, *, now: datetime | None = None) -> None:
    if not cost.paid_provisioning_allowed:
        raise OperationError("cost evidence has not authorized paid provisioning")
    current = now or datetime.now(timezone.utc)
    baseline_age = current.astimezone(timezone.utc) - cost.baseline_observed_at.astimezone(timezone.utc)
    if baseline_age.total_seconds() < 0 or baseline_age.total_seconds() > 1800:
        raise OperationError("billing/resource cost baseline is older than 30 minutes")


def validate_cleanup_manifest(
    config: InstallationConfig, expiry_id: str, manifest: dict[str, object]
) -> None:
    prefix = f"fde-{config.customer}"
    expected = {
        "project_id": config.project,
        "expiry_id": expiry_id,
        "cluster_name": f"{prefix}-demo",
        "artifact_repository": f"{prefix}-images",
        "bucket_names": sorted([f"{config.project}-{prefix}-production-demo", f"{config.project}-{prefix}-staging"]),
        "disk_names": sorted([
            f"{prefix}-observability-loki",
            f"{prefix}-observability-prometheus",
            f"{prefix}-observability-tempo",
            f"{prefix}-production-demo-postgres",
            f"{prefix}-production-demo-redis",
            f"{prefix}-staging-postgres",
            f"{prefix}-staging-redis",
        ]),
    }
    actual = {
        "project_id": manifest.get("project_id"),
        "expiry_id": manifest.get("expiry_id"),
        "cluster_name": manifest.get("cluster_name"),
        "artifact_repository": manifest.get("artifact_repository"),
        "bucket_names": sorted(manifest.get("bucket_names", [])),
        "disk_names": sorted(item.get("name") for item in manifest.get("disk_resources", [])),
    }
    if actual != expected:
        raise OperationError("cleanup manifest does not match deterministic project/customer/run ownership")


def remaining_instance_names(resources: list[dict[str, object]]) -> list[str]:
    return sorted(str(resource.get("name", "unknown")) for resource in resources)


def validate_helm_values(config: InstallationConfig, path: Path) -> None:
    try:
        values = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise OperationError(f"cannot read Helm values: {exc}") from exc
    if not isinstance(values, dict):
        raise OperationError("Helm values must be a mapping")
    for key, expected in {
        "profile": config.profile,
        "customer": config.customer,
        "environment": config.environment,
        "appVersion": config.app_version,
    }.items():
        if values.get(key) != expected:
            raise OperationError(f"Helm value {key} does not match installation config")
    if values.get("branding", {}).get("name") != config.branding_name:
        raise OperationError("Helm branding name does not match installation config")
    images = values.get("images", {})
    for name, (repository, digest) in {
        "backend": (config.image_repository, config.image_digest),
        "frontend": (config.frontend_image_repository, config.frontend_image_digest),
    }.items():
        image = images.get(name, {})
        if image.get("repository") != repository or image.get("digest") != digest:
            raise OperationError(f"Helm {name} image does not match immutable installation image")
    if values.get("backend", {}).get("replicas") != config.sizing.api_replicas:
        raise OperationError("Helm API replica count differs from installation sizing")
    if values.get("worker", {}).get("replicas") != config.sizing.worker_replicas:
        raise OperationError("Helm worker replica count differs from installation sizing")
    for component, cpu, memory in (
        ("backend", config.sizing.api_cpu, config.sizing.api_memory),
        ("worker", config.sizing.worker_cpu, config.sizing.worker_memory),
    ):
        requests = values.get(component, {}).get("resources", {}).get("requests", {})
        if requests.get("cpu") != cpu or requests.get("memory") != memory:
            raise OperationError(f"Helm {component} requests differ from installation sizing")
    account_id = ("fde-" + config.customer + "-" + config.environment)[:30]
    expected_account = f"{account_id}@{config.project}.iam.gserviceaccount.com"
    if values.get("serviceAccount", {}).get("gcpServiceAccount") != expected_account:
        raise OperationError("Helm runtime service account differs from Terraform identity")
    storage = values.get("storage", {})
    if storage.get("backend") != "gcs" or storage.get("gcsBucket") != f"{config.project}-fde-{config.customer}-{config.environment}":
        raise OperationError("Helm storage does not match the environment GCS bucket")
    provider = values.get("secretProvider", {})
    prefix = f"fde-{config.customer}-{config.environment}"
    expected_secrets = {
        "databaseUrl": f"{prefix}-database-url",
        "redisUrl": f"{prefix}-redis-url",
        "appSecretKey": f"{prefix}-secret-key",
        "postgresPassword": f"{prefix}-postgres-password",
        "redisPassword": f"{prefix}-redis-password",
        "redisCa": f"{prefix}-redis-ca",
        "databaseSslRootCert": f"{prefix}-database-ssl-root-cert",
        "databaseSslCert": f"{prefix}-database-ssl-cert",
        "databaseSslKey": f"{prefix}-database-ssl-key",
    }
    if provider.get("enabled") is not True or provider.get("projectId") != config.project:
        raise OperationError("Helm Secret Manager provider differs from installation project")
    if provider.get("secretNames") != expected_secrets:
        raise OperationError("Helm secret references differ from Terraform secret IDs")
    ingress = values.get("ingress", {})
    if config.domain:
        if ingress.get("enabled") is not True or ingress.get("host") != config.domain:
            raise OperationError("Helm ingress does not match configured domain")
    elif ingress.get("enabled") is True:
        raise OperationError("Helm ingress cannot be enabled without a configured domain")


def validate_expiry_contract(
    *,
    project: str,
    region: str,
    zone: str,
    gate_expires_at: datetime,
    gate_sha: str,
    state_sha: str,
    manifest: dict[str, object],
    sentinel: dict[str, object],
    planned_disks: dict[str, str],
    planned_clusters: dict[str, str],
    planned_buckets: dict[str, str],
    planned_repositories: dict[str, str],
) -> None:
    if state_sha != gate_sha or sentinel.get("manifest_sha") != state_sha:
        raise OperationError("release gate, expiry state, and sentinel manifest SHA do not match")
    if sentinel.get("status") != "sentinel-ok":
        raise OperationError("live expiry sentinel did not succeed")
    if manifest.get("project_id") != project or sentinel.get("expiry_id") != manifest.get("expiry_id"):
        raise OperationError("live sentinel or compiled manifest does not match project/expiry_id")
    try:
        manifest_expiry = datetime.fromisoformat(str(manifest.get("expires_at", "")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise OperationError("compiled manifest expiry is invalid") from exc
    if manifest_expiry.astimezone(timezone.utc) != gate_expires_at.astimezone(timezone.utc):
        raise OperationError("release gate deadline differs from compiled expiry manifest")
    if manifest.get("region") != region or manifest.get("zone") != zone:
        raise OperationError("compiled expiry manifest region/zone differs from configuration")
    manifest_disk_names = sorted(
        str(item["name"]) for item in manifest.get("disk_resources", [])  # type: ignore[union-attr]
    )
    if sorted(planned_disks) != manifest_disk_names:
        raise OperationError("demo plan disk set differs from compiled expiry manifest")
    if not planned_disks or any(label != manifest.get("expiry_id") for label in planned_disks.values()):
        raise OperationError("demo plan expiry_id labels differ from compiled expiry manifest")
    expected = {
        "cluster": [str(manifest.get("cluster_name"))],
        "bucket": sorted(str(name) for name in manifest.get("bucket_names", [])),  # type: ignore[union-attr]
        "repository": [str(manifest.get("artifact_repository"))],
    }
    actual = {
        "cluster": sorted(planned_clusters),
        "bucket": sorted(planned_buckets),
        "repository": sorted(planned_repositories),
    }
    for kind in expected:
        if actual[kind] != expected[kind]:
            raise OperationError(f"demo plan {kind} set differs from compiled expiry manifest")
    for resources in (planned_clusters, planned_buckets, planned_repositories):
        if any(label != manifest.get("expiry_id") for label in resources.values()):
            raise OperationError("demo plan resource expiry_id differs from compiled expiry manifest")


def validate_demo_cost_drivers(resources: list[dict[str, object]], *, zone: str) -> None:
    node_pools = [item["values"] for item in resources if item.get("type") == "google_container_node_pool"]
    clusters = [item["values"] for item in resources if item.get("type") == "google_container_cluster"]
    disks = [item["values"] for item in resources if item.get("type") == "google_compute_disk"]
    forbidden = {
        "google_compute_forwarding_rule",
        "google_compute_global_forwarding_rule",
        "google_compute_region_backend_service",
        "google_sql_database_instance",
        "google_redis_instance",
    }
    if any(item.get("type") in forbidden for item in resources):
        raise OperationError("demo plan contains a public-LB or managed-profile cost driver")
    if len(clusters) != 1 or clusters[0].get("location") != zone:
        raise OperationError("demo plan must contain one zonal Montréal cluster")
    if len(node_pools) != 1 or node_pools[0].get("node_count") != 1:
        raise OperationError("demo plan must contain one fixed node")
    node_configs = node_pools[0].get("node_config")
    if not isinstance(node_configs, list) or len(node_configs) != 1:
        raise OperationError("demo node configuration is unknown")
    node = node_configs[0]
    if (
        node.get("machine_type") != "e2-standard-4"
        or node.get("disk_type") != "pd-standard"
        or node.get("disk_size_gb") != 30
    ):
        raise OperationError("demo node machine or boot disk differs from priced configuration")
    if node_pools[0].get("autoscaling") not in (None, []):
        raise OperationError("demo node autoscaling must remain disabled")
    if not all(isinstance(item.get("size"), (int, float)) for item in disks):
        raise OperationError("demo data disk sizes are unknown")
    sizes = sorted(item.get("size") for item in disks)
    if sizes != [5, 5, 8, 8, 8, 10, 10] or any(item.get("type") != "pd-standard" for item in disks):
        raise OperationError("demo data disks differ from the priced 54 GiB pd-standard set")


def collect_plan_contract(plan_json: dict[str, object]) -> tuple[
    dict[str, str], dict[str, str], dict[str, str], dict[str, str], list[dict[str, object]]
]:
    targets: dict[str, dict[str, str]] = {
        "google_compute_disk": {},
        "google_container_cluster": {},
        "google_storage_bucket": {},
        "google_artifact_registry_repository": {},
    }
    resources: list[dict[str, object]] = []

    def collect(module: dict[str, object]) -> None:
        for resource in module.get("resources", []):  # type: ignore[union-attr]
            resource_type = resource.get("type")  # type: ignore[union-attr]
            values_map = resource.get("values", {})  # type: ignore[union-attr]
            resources.append({"type": resource_type, "values": values_map})
            target = targets.get(str(resource_type))
            if target is not None:
                name = values_map.get("repository_id") if resource_type == "google_artifact_registry_repository" else values_map.get("name")
                labels = values_map.get("resource_labels") if resource_type == "google_container_cluster" else values_map.get("labels")
                if name is None or not isinstance(labels, dict):
                    raise OperationError(f"demo plan has unknown identity or labels for {resource_type}")
                target[str(name)] = str(labels.get("expiry-id"))
        for child in module.get("child_modules", []):  # type: ignore[union-attr]
            collect(child)

    collect(plan_json.get("planned_values", {}).get("root_module", {}))  # type: ignore[union-attr]
    return (
        targets["google_compute_disk"],
        targets["google_container_cluster"],
        targets["google_storage_bucket"],
        targets["google_artifact_registry_repository"],
        resources,
    )


def validate_state_bucket_ownership(
    config: InstallationConfig,
    state_bucket: str,
    metadata: dict[str, object],
    project_buckets: list[dict[str, object]],
) -> None:
    if str(metadata.get("location", "")).lower() != config.region.lower():
        raise OperationError("existing state bucket is not in the configured Canadian region")
    owned_names = {str(item.get("name", "")) for item in project_buckets}
    if state_bucket not in owned_names:
        raise OperationError("existing state bucket does not belong to the configured project")
    labels = metadata.get("labels", {})
    if not isinstance(labels, dict) or labels.get("application") != "fde-template" or labels.get("purpose") != "terraform-state":
        raise OperationError("existing state bucket is not labeled as FDE Terraform state")


def bootstrap_gcp(
    config: InstallationConfig,
    *,
    terraform_dir: Path,
    state_bucket: str,
    github_repository: str,
    confirm_project: str,
) -> None:
    if config.project != confirm_project:
        raise OperationError("--confirm-project must exactly match the configured project")
    gcloud = executable("gcloud")
    ensure_cloud_resource_manager(gcloud, config.project)
    bucket_uri = f"gs://{state_bucket}"
    described = run([gcloud, "storage", "buckets", "describe", bucket_uri, "--format=json"], check=False)
    if described.returncode:
        detail = (described.stderr or described.stdout).lower()
        if "not found" not in detail and "404" not in detail:
            raise OperationError(redact(described.stderr or described.stdout))
        run(
            [
                gcloud,
                "storage",
                "buckets",
                "create",
                bucket_uri,
                f"--project={config.project}",
                f"--location={config.region}",
                "--uniform-bucket-level-access",
                "--public-access-prevention",
            ]
        )
        run(
            [
                gcloud,
                "storage",
                "buckets",
                "update",
                bucket_uri,
                "--clear-soft-delete",
                "--update-labels=application=fde-template,purpose=terraform-state,managed-by=terraform",
            ]
        )
        described = run([gcloud, "storage", "buckets", "describe", bucket_uri, "--format=json"])
    metadata = json.loads(described.stdout)
    project_buckets = json.loads(
        run(
            [
                gcloud,
                "storage",
                "buckets",
                "list",
                f"--project={config.project}",
                f"--filter=name={state_bucket}",
                "--format=json(name)",
            ]
        ).stdout
    )
    validate_state_bucket_ownership(config, state_bucket, metadata, project_buckets)
    terraform = executable("terraform")
    run(
        [
            terraform,
            "init",
            "-input=false",
            "-reconfigure",
            f"-backend-config=bucket={state_bucket}",
            "-backend-config=prefix=bootstrap",
        ],
        cwd=terraform_dir,
    )
    state = run([terraform, "state", "list"], cwd=terraform_dir)
    if "google_storage_bucket.terraform_state" not in state.stdout.splitlines():
        run(
            [
                terraform,
                "import",
                "-input=false",
                f"-var=project_id={config.project}",
                f"-var=region={config.region}",
                f"-var=github_repository={github_repository}",
                f"-var=state_bucket_name={state_bucket}",
                "google_storage_bucket.terraform_state",
                state_bucket,
            ],
            cwd=terraform_dir,
        )
    run(
        [
            terraform,
            "apply",
            "-input=false",
            "-lock-timeout=60s",
            f"-var=project_id={config.project}",
            f"-var=region={config.region}",
            f"-var=github_repository={github_repository}",
            f"-var=state_bucket_name={state_bucket}",
            "-auto-approve",
        ],
        cwd=terraform_dir,
    )


def ensure_cloud_resource_manager(gcloud: str, project: str) -> None:
    """Enable the API before Terraform can refresh project/IAM state.

    Reconciliation identities need only read the already-enabled API. The
    initial owner bootstrap enables it when missing; Terraform dependencies
    alone cannot order reads performed during refresh.
    """
    service = "cloudresourcemanager.googleapis.com"
    query = [
        gcloud,
        "services",
        "list",
        "--enabled",
        f"--project={project}",
        f"--filter=config.name={service}",
        "--format=value(config.name)",
    ]
    if service in run(query).stdout.splitlines():
        return
    try:
        run([gcloud, "services", "enable", service, f"--project={project}", "--quiet"])
    except RuntimeError as exc:
        raise OperationError(
            f"Enable {service} in project {project} with an authorized owner or "
            "Service Usage Admin before retrying bootstrap. No Terraform work "
            f"has started. {redact(str(exc))}"
        ) from exc
    if service not in run(query).stdout.splitlines():
        raise OperationError(
            f"{service} is not yet reported enabled in project {project}; "
            "retry bootstrap after activation. No Terraform work has started."
        )


def assert_scope(config: InstallationConfig, customer: str, environment: str, project: str) -> None:
    supplied = (customer, environment, project)
    expected = (config.customer, config.environment, config.project)
    if supplied != expected:
        raise OperationError(f"explicit scope {supplied!r} does not match configuration {expected!r}")


def terraform_plan(
    config: InstallationConfig,
    terraform_dir: Path,
    backend_bucket: str,
    state_prefix: str,
    output: Path,
    expiry_id: str,
) -> None:
    terraform = executable("terraform")
    run([terraform, "init", "-input=false", f"-backend-config=bucket={backend_bucket}", f"-backend-config=prefix={state_prefix}"], cwd=terraform_dir)
    run([terraform, "validate", "-no-color"], cwd=terraform_dir)
    run(
        [
            terraform,
            "plan",
            "-input=false",
            "-lock-timeout=60s",
            f"-var=project_id={config.project}",
            f"-var=customer={config.customer}",
            f"-var=cluster_name=fde-{config.customer}-demo",
            f"-var=expiry_id={expiry_id}",
            f"-out={output.resolve()}",
        ],
        cwd=terraform_dir,
    )


def deploy_demo_infrastructure(
    config: InstallationConfig,
    *,
    gate_path: Path,
    cost_path: Path,
    terraform_dir: Path,
    plan_path: Path,
    expiry_terraform_dir: Path,
    expiry_evidence_path: Path,
) -> None:
    if config.profile != "demo":
        raise OperationError("managed profile deployment is forbidden under the USD 25 demo authorization")
    cost = load_cost_gate(cost_path)
    gate = load_release_gate(gate_path)
    validate_paid_cost_gate(cost)
    if cost.project != config.project or gate.project != config.project or gate.customer != config.customer:
        raise OperationError("cost/release evidence does not match explicit deployment scope")
    terraform = executable("terraform")
    state_sha = run([terraform, "output", "-raw", "manifest_sha"], cwd=expiry_terraform_dir).stdout.strip()
    manifest_result = run([terraform, "output", "-json", "compiled_manifest"], cwd=expiry_terraform_dir)
    try:
        manifest = json.loads(manifest_result.stdout)
        expiry_evidence = json.loads(expiry_evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OperationError(f"invalid expiry evidence: {exc}") from exc
    if expiry_evidence.get("manifest_sha") != state_sha:
        raise OperationError("expiry evidence file does not match remote expiry state")
    gcloud = executable("gcloud")
    execution = run(
        [
            gcloud,
            "workflows",
            "executions",
            "describe",
            str(expiry_evidence.get("execution_id", "")),
            f"--workflow={expiry_evidence.get('workflow', '')}",
            f"--location={config.region}",
            f"--project={config.project}",
            "--format=json",
        ]
    )
    execution_json = json.loads(execution.stdout)
    try:
        sentinel_result = json.loads(execution_json.get("result", "{}"))
    except json.JSONDecodeError as exc:
        raise OperationError("live sentinel returned invalid result JSON") from exc
    if execution_json.get("state") != "SUCCEEDED":
        raise OperationError("live expiry sentinel did not succeed")
    plan_json = json.loads(run([terraform, "show", "-json", str(plan_path.resolve())], cwd=terraform_dir).stdout)
    (
        planned_disks,
        planned_clusters,
        planned_buckets,
        planned_repositories,
        planned_resources,
    ) = collect_plan_contract(plan_json)
    validate_demo_cost_drivers(planned_resources, zone=config.zone)
    validate_expiry_contract(
        project=config.project,
        region=config.region,
        zone=config.zone,
        gate_expires_at=gate.expires_at,
        gate_sha=gate.exact_manifest_sha,
        state_sha=state_sha,
        manifest=manifest,
        sentinel=sentinel_result,
        planned_disks=planned_disks,
        planned_clusters=planned_clusters,
        planned_buckets=planned_buckets,
        planned_repositories=planned_repositories,
    )
    git = executable("git")
    revision = run([git, "-C", str(terraform_dir), "rev-parse", "HEAD"]).stdout.strip().lower()
    if revision != gate.revision.lower():
        raise OperationError("release gate revision does not match the current repository HEAD")
    if plan_path.stat().st_mtime > gate_path.stat().st_mtime:
        raise OperationError("release gate must be issued after the final Terraform plan")
    run([terraform, "apply", "-input=false", "-lock-timeout=60s", str(plan_path.resolve())], cwd=terraform_dir)


def deploy_release(config: InstallationConfig, *, chart: Path, values: Path) -> None:
    if config.profile != "demo":
        raise OperationError("managed profile deployment is forbidden under the USD 25 demo authorization")
    validate_helm_values(config, values)
    gcloud = executable("gcloud")
    run([gcloud, "container", "clusters", "get-credentials", f"fde-{config.customer}-demo", f"--zone={config.zone}", f"--project={config.project}"])
    helm = executable("helm")
    run(
        [helm, "upgrade", "--install", config.release, str(chart.resolve()), "--namespace", config.namespace, "--create-namespace", "--values", str(values.resolve()), "--atomic", "--wait", "--wait-for-jobs", "--timeout", "12m"],
    )


def deploy_demo(
    config: InstallationConfig,
    *,
    gate_path: Path,
    cost_path: Path,
    terraform_dir: Path,
    plan_path: Path,
    chart: Path,
    values: Path,
    expiry_terraform_dir: Path,
    expiry_evidence_path: Path,
) -> None:
    deploy_demo_infrastructure(
        config,
        gate_path=gate_path,
        cost_path=cost_path,
        terraform_dir=terraform_dir,
        plan_path=plan_path,
        expiry_terraform_dir=expiry_terraform_dir,
        expiry_evidence_path=expiry_evidence_path,
    )
    deploy_release(config, chart=chart, values=values)


def verify_release(config: InstallationConfig, *, local_port: int = 18080) -> dict[str, object]:
    kubectl = executable("kubectl")
    for component in ("api", "worker", "publisher", "frontend"):
        run([kubectl, "rollout", "status", f"deployment/{config.release}-{component}", "--namespace", config.namespace, "--timeout=180s"])
    process = subprocess.Popen(
        [kubectl, "port-forward", f"service/{config.release}-api", f"{local_port}:8000", "--namespace", config.namespace],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{local_port}/api/v1/health/ready", timeout=2) as response:
                    readiness = json.loads(response.read().decode("utf-8"))
                with urllib.request.urlopen(f"http://127.0.0.1:{local_port}/api/v1/version", timeout=2) as response:
                    version = json.loads(response.read().decode("utf-8"))
                return {"ready": readiness, "version": version}
            except (OSError, json.JSONDecodeError):
                time.sleep(1)
        detail = process.stderr.read() if process.poll() is not None and process.stderr else "port-forward did not become ready"
        raise OperationError(redact(detail))
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def rollback_release(config: InstallationConfig) -> dict[str, object]:
    helm = executable("helm")
    run([helm, "rollback", config.release, "--namespace", config.namespace, "--wait", "--timeout", "8m"])
    run([executable("kubectl"), "rollout", "status", f"deployment/{config.release}-api", "--namespace", config.namespace, "--timeout=180s"])
    return verify_release(config, local_port=18081)


def collect_evidence(config: InstallationConfig, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    commands: dict[str, list[str]] = {
        "cluster": [executable("gcloud"), "container", "clusters", "describe", f"fde-{config.customer}-demo", f"--zone={config.zone}", f"--project={config.project}", "--format=json"],
        "workloads": [executable("kubectl"), "get", "deployments,statefulsets,jobs,pods,pvc", "--namespace", config.namespace, "-o", "json"],
        "helm": [executable("helm"), "status", config.release, "--namespace", config.namespace, "--output", "json"],
        "compute_instances": [executable("gcloud"), "compute", "instances", "list", f"--project={config.project}", "--format=json"],
        "compute_disks": [executable("gcloud"), "compute", "disks", "list", f"--project={config.project}", "--format=json"],
        "compute_addresses": [executable("gcloud"), "compute", "addresses", "list", f"--project={config.project}", "--format=json"],
        "artifact_repositories": [executable("gcloud"), "artifacts", "repositories", "list", f"--project={config.project}", "--location=all", "--format=json"],
        "storage_buckets": [executable("gcloud"), "storage", "buckets", "list", f"--project={config.project}", "--format=json"],
        "expiry_workflows": [executable("gcloud"), "workflows", "list", f"--project={config.project}", f"--location={config.region}", "--format=json"],
        "expiry_schedules": [executable("gcloud"), "scheduler", "jobs", "list", f"--project={config.project}", f"--location={config.region}", "--format=json"],
    }
    evidence: dict[str, object] = {"scope": {"customer": config.customer, "environment": config.environment, "project": config.project}, "config_fingerprint": config.fingerprint}
    for name, command in commands.items():
        result = run(command, check=False)
        raw = redact(result.stdout if result.returncode == 0 else result.stderr)
        try:
            evidence[name] = json.loads(raw)
        except json.JSONDecodeError:
            evidence[name] = {"returncode": result.returncode, "output": raw}
    path = output_dir / "deployment-evidence.json"
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    return path


def destroy_demo(
    config: InstallationConfig,
    terraform_dir: Path,
    confirm_customer: str,
    expiry_id: str,
    expiry_terraform_dir: Path,
    manifest_file: Path | None = None,
) -> list[dict[str, object]]:
    if confirm_customer != config.customer:
        raise OperationError("--confirm-customer must exactly match the configured customer")
    terraform = executable("terraform")
    manifest_output = run([terraform, "output", "-json", "compiled_manifest"], cwd=expiry_terraform_dir, check=False)
    if manifest_output.returncode == 0:
        manifest = json.loads(manifest_output.stdout)
    elif manifest_file is not None:
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OperationError(f"cannot read cleanup manifest fallback: {exc}") from exc
    else:
        raise OperationError("expiry state is unavailable and no cleanup manifest fallback was supplied")
    validate_cleanup_manifest(config, expiry_id, manifest)
    run([terraform, "destroy", "-input=false", "-auto-approve", "-lock-timeout=60s", f"-var=project_id={config.project}", f"-var=customer={config.customer}", f"-var=cluster_name=fde-{config.customer}-demo", f"-var=expiry_id={expiry_id}"], cwd=terraform_dir)
    gcloud = executable("gcloud")
    inventory_commands: Iterable[tuple[str, list[str]]] = (
        ("clusters", [gcloud, "container", "clusters", "list", f"--project={config.project}", "--format=json"]),
        ("instances", [gcloud, "compute", "instances", "list", f"--project={config.project}", "--format=json"]),
        ("disks", [gcloud, "compute", "disks", "list", f"--project={config.project}", "--format=json"]),
        ("addresses", [gcloud, "compute", "addresses", "list", f"--project={config.project}", "--format=json"]),
        ("repositories", [gcloud, "artifacts", "repositories", "list", f"--project={config.project}", "--location=all", "--format=json"]),
        ("buckets", [gcloud, "storage", "buckets", "list", f"--project={config.project}", "--format=json"]),
        ("secrets", [gcloud, "secrets", "list", f"--project={config.project}", "--format=json"]),
    )
    inventory = []
    for name, command in inventory_commands:
        result = run(command)
        inventory.append({"kind": name, "resources": json.loads(result.stdout)})
    by_kind = {item["kind"]: item["resources"] for item in inventory}
    expected_names = {
        "clusters": {manifest["cluster_name"]},
        "disks": {item["name"] for item in manifest.get("disk_resources", [])},
        "addresses": {item["name"] for item in manifest.get("address_resources", [])},
        "repositories": {manifest["artifact_repository"]},
        "buckets": set(manifest.get("bucket_names", [])),
        "secrets": {
            f"fde-{config.customer}-{environment}-{name}"
            for environment in ("staging", "production-demo")
            for name in ("database-url", "postgres-password", "redis-password", "redis-url", "secret-key")
        },
    }
    residues: dict[str, list[str]] = {}
    remaining_instances = remaining_instance_names(by_kind.get("instances", []))
    if remaining_instances:
        residues["instances"] = remaining_instances
    for kind, names in expected_names.items():
        present: list[str] = []
        for resource in by_kind.get(kind, []):
            raw_name = str(resource.get("name", ""))
            normalized_name = raw_name.removeprefix("gs://").rstrip("/")
            short_name = normalized_name.rsplit("/", 1)[-1]
            if short_name in names:
                present.append(short_name)
        if present:
            residues[kind] = sorted(present)
    if residues:
        raise OperationError(f"owned billable residues remain after destroy: {json.dumps(residues, sort_keys=True)}")
    return inventory
