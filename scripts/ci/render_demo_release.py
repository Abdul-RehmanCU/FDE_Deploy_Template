from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from fde_cli.config import load_config
from fde_cli.operations import validate_helm_values


def terraform_value(outputs: dict[str, Any], name: str) -> Any:
    try:
        return outputs[name]["value"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Terraform output {name!r} is missing") from exc


def render(
    *,
    base_values: dict[str, Any],
    base_observability_values: dict[str, Any],
    manifest: dict[str, Any],
    terraform_outputs: dict[str, Any],
    project: str,
    customer: str,
    environment: str,
    brand_name: str,
    revision: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if environment not in {"staging", "production-demo"}:
        raise ValueError("demo environment must be staging or production-demo")
    if manifest.get("commit") != revision:
        raise ValueError("image manifest commit does not match the selected revision")

    repository = str(manifest.get("repository", "")).rstrip("/")
    images = manifest.get("images")
    if not repository or not isinstance(images, dict):
        raise ValueError("image manifest repository or images are missing")
    backend_digest = str(images.get("backend", {}).get("digest", ""))
    frontend_digest = str(images.get("frontend", {}).get("digest", ""))

    buckets = terraform_value(terraform_outputs, "application_buckets")
    accounts = terraform_value(terraform_outputs, "runtime_service_accounts")
    volumes = terraform_value(terraform_outputs, "persistent_disk_volume_handles")
    bucket = str(buckets[environment])
    service_account = str(accounts[environment])
    prefix = f"fde-{customer}-{environment}"

    config = {
        "customer": customer,
        "environment": environment,
        "project": project,
        "region": "northamerica-northeast1",
        "zone": "northamerica-northeast1-a",
        "profile": "demo",
        "namespace": environment,
        "image_repository": f"{repository}/backend",
        "image_digest": backend_digest,
        "frontend_image_repository": f"{repository}/frontend",
        "frontend_image_digest": frontend_digest,
        "app_version": revision,
        "branding": {"name": brand_name},
        "sizing": {
            "api_replicas": 2,
            "worker_replicas": 1,
            "api_cpu": "250m",
            "api_memory": "384Mi",
            "worker_cpu": "250m",
            "worker_memory": "384Mi",
        },
    }

    values = deepcopy(base_values)
    values.update(
        {
            "profile": "demo",
            "customer": customer,
            "environment": environment,
            "appVersion": revision,
            "branding": {"name": brand_name},
        }
    )
    values["images"]["backend"].update(
        {"repository": f"{repository}/backend", "digest": backend_digest}
    )
    values["images"]["frontend"].update(
        {"repository": f"{repository}/frontend", "digest": frontend_digest}
    )
    values["serviceAccount"].update({"gcpServiceAccount": service_account})
    values["storage"].update({"backend": "gcs", "gcsBucket": bucket})
    values["secretProvider"].update(
        {
            "enabled": True,
            "projectId": project,
            "secretNames": {
                "databaseUrl": f"{prefix}-database-url",
                "redisUrl": f"{prefix}-redis-url",
                "appSecretKey": f"{prefix}-secret-key",
                "postgresPassword": f"{prefix}-postgres-password",
                "redisPassword": f"{prefix}-redis-password",
                "redisCa": f"{prefix}-redis-ca",
                "databaseSslRootCert": f"{prefix}-database-ssl-root-cert",
                "databaseSslCert": f"{prefix}-database-ssl-cert",
                "databaseSslKey": f"{prefix}-database-ssl-key",
            },
        }
    )
    values["demoDependencies"]["enabled"] = True
    values["demoDependencies"]["postgres"]["volumeHandle"] = volumes[
        f"{prefix}-postgres"
    ]
    values["demoDependencies"]["redis"]["volumeHandle"] = volumes[f"{prefix}-redis"]

    observability = deepcopy(base_observability_values)
    observability["storage"]["predeclared"] = True
    for component in ("prometheus", "loki", "tempo"):
        observability["storage"]["volumeHandles"][component] = volumes[
            f"fde-{customer}-observability-{component}"
        ]
    return config, values, observability


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--terraform-outputs", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--customer", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--brand-name", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--config-out", type=Path, required=True)
    parser.add_argument("--values-out", type=Path, required=True)
    parser.add_argument("--observability-values-out", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    terraform_outputs = json.loads(args.terraform_outputs.read_text(encoding="utf-8"))
    base_values = yaml.safe_load(
        Path("infra/helm/fde/values.yaml").read_text(encoding="utf-8")
    )
    base_observability_values = yaml.safe_load(
        Path("observability/helm/values.yaml").read_text(encoding="utf-8")
    )
    config, values, observability = render(
        base_values=base_values,
        base_observability_values=base_observability_values,
        manifest=manifest,
        terraform_outputs=terraform_outputs,
        project=args.project,
        customer=args.customer,
        environment=args.environment,
        brand_name=args.brand_name,
        revision=args.revision,
    )
    args.config_out.write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    args.values_out.write_text(
        yaml.safe_dump(values, sort_keys=False), encoding="utf-8"
    )
    validate_helm_values(load_config(args.config_out), args.values_out)
    if args.observability_values_out:
        args.observability_values_out.write_text(
            yaml.safe_dump(observability, sort_keys=False), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
