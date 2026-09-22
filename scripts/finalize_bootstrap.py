from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def run(
    command: list[str], *, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=check, text=True, capture_output=True)


def resolve_executable(name: str) -> str:
    """Resolve a command once so Windows .cmd shims are passed explicitly."""
    candidates = [name]
    if os.name == "nt" and not name.lower().endswith(".cmd"):
        candidates.insert(0, f"{name}.cmd")
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    if os.name == "nt" and name == "gcloud":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            installed = (
                Path(local_app_data)
                / "Google"
                / "Cloud SDK"
                / "google-cloud-sdk"
                / "bin"
                / "gcloud.cmd"
            )
            if installed.is_file():
                return str(installed)
    raise FileNotFoundError(f"{name} is required")


def all_generation_delete_command(
    bucket_uri: str, gcloud: str = "gcloud"
) -> list[str]:
    return [
        gcloud,
        "storage",
        "rm",
        "--recursive",
        "--all-versions",
        f"{bucket_uri}/**",
    ]


def list_bucket_generations(
    bucket_uri: str, gcloud: str = "gcloud"
) -> list[dict[str, object]]:
    result = run(
        [gcloud, "storage", "ls", "--all-versions", "--json", f"{bucket_uri}/**"],
        check=False,
    )
    if result.returncode != 0:
        if result.returncode == 1 and "matched no objects" in result.stderr.lower():
            return []
        raise RuntimeError("cannot verify all state bucket object generations")
    if not result.stdout.strip():
        return []
    rows = json.loads(result.stdout)
    return [
        {
            "name": row.get("name") or row.get("url"),
            "generation": row.get("generation"),
            "temporaryHold": row.get("temporaryHold", False),
            "eventBasedHold": row.get("eventBasedHold", False),
        }
        for row in rows
    ]


def require_soft_delete_disabled(bucket: dict[str, object]) -> None:
    policy = bucket.get("soft_delete_policy") or bucket.get("softDeletePolicy") or {}
    if not isinstance(policy, dict):
        raise TypeError("state bucket soft-delete policy has an unexpected shape")
    raw = policy.get(
        "retention_duration_seconds",
        policy.get("retentionDurationSeconds", policy.get("retentionDuration", 0)),
    )
    seconds = int(str(raw).removesuffix("s") or "0")
    if seconds > 0:
        raise RuntimeError("state bucket soft delete must be disabled before teardown")


def normalized_versioning(bucket: dict[str, object]) -> object:
    """Keep the recorded versioning evidence stable across gcloud JSON shapes."""
    metadata = bucket.get("versioning")
    if isinstance(metadata, dict):
        return metadata
    for key in ("versioning_enabled", "versioningEnabled"):
        if key in bucket:
            return {"enabled": bucket[key]}
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Owner-ADC final teardown immediately after runtime and expiry reconciliation"
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--state-bucket", required=True)
    parser.add_argument("--github-repository", required=True)
    parser.add_argument("--region", default="northamerica-northeast1")
    parser.add_argument(
        "--confirm", required=True, help="Must equal FINALIZE-BOOTSTRAP"
    )
    parser.add_argument("--evidence-out", type=Path, required=True)
    args = parser.parse_args()
    if args.confirm != "FINALIZE-BOOTSTRAP":
        raise SystemExit("--confirm must exactly equal FINALIZE-BOOTSTRAP")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.github_repository):
        raise SystemExit("--github-repository must be the exact OWNER/REPOSITORY")
    try:
        gcloud = resolve_executable("gcloud")
        terraform = resolve_executable("terraform")
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc

    root = Path(__file__).resolve().parents[1]
    terraform_dir = root / "infra" / "terraform" / "bootstrap"
    bucket_uri = f"gs://{args.state_bucket}"
    owned_buckets = json.loads(
        run(
            [
                gcloud,
                "storage",
                "buckets",
                "list",
                f"--project={args.project}",
                f"--filter=name={args.state_bucket}",
                "--format=json(name)",
            ]
        ).stdout
    )
    if [row.get("name") for row in owned_buckets] != [args.state_bucket]:
        raise SystemExit("state bucket is not uniquely owned by the confirmed project")
    bucket = json.loads(
        run(
            [gcloud, "storage", "buckets", "describe", bucket_uri, "--format=json"]
        ).stdout
    )
    labels = bucket.get("labels", {})
    if (
        labels.get("application") != "fde-template"
        or labels.get("purpose") != "terraform-state"
    ):
        raise SystemExit(
            "state bucket labels do not identify the FDE Terraform state bucket"
        )
    if str(bucket.get("location", "")).lower() != args.region.lower():
        raise SystemExit("state bucket is not in the confirmed Montréal region")
    require_soft_delete_disabled(bucket)

    run(
        [
            terraform,
            "init",
            "-input=false",
            "-reconfigure",
            f"-backend-config=bucket={args.state_bucket}",
            "-backend-config=prefix=bootstrap",
        ],
        cwd=terraform_dir,
    )
    targets = (
        "google_project_iam_member.automation_roles",
        "google_storage_bucket_iam_member.infra_state",
        "google_service_account_iam_member.github_federation",
        "google_iam_workload_identity_pool_provider.github",
        "google_iam_workload_identity_pool.github",
        "google_service_account.automation",
        "google_project_service.required",
    )
    state_result = run(
        [terraform, "state", "list"], cwd=terraform_dir, check=False
    )
    if state_result.returncode == 0:
        state = [line for line in state_result.stdout.splitlines() if line]
    elif "no state file was found" in state_result.stderr.lower():
        state = []
    else:
        raise RuntimeError(
            "cannot inspect bootstrap Terraform state: "
            + state_result.stderr.strip()
        )
    valid_state_prefixes = (*targets, "google_storage_bucket.terraform_state")
    unexpected_state = [
        entry
        for entry in state
        if not any(
            entry == prefix or entry.startswith(f"{prefix}[")
            for prefix in valid_state_prefixes
        )
    ]
    if unexpected_state:
        raise SystemExit(f"unexpected bootstrap state entries: {unexpected_state}")
    destroy = [
        terraform,
        "destroy",
        "-input=false",
        "-auto-approve",
        "-lock-timeout=60s",
        f"-var=project_id={args.project}",
        f"-var=region={args.region}",
        f"-var=github_repository={args.github_repository}",
        f"-var=state_bucket_name={args.state_bucket}",
        *(f"-target={target}" for target in targets),
    ]
    recorded_target = any(
        entry == target or entry.startswith(f"{target}[")
        for entry in state
        for target in targets
    )
    if recorded_target:
        run(destroy, cwd=terraform_dir)
    state_after_destroy_result = run(
        [terraform, "state", "list"], cwd=terraform_dir, check=False
    )
    if state_after_destroy_result.returncode == 0:
        state_after_destroy = [
            line for line in state_after_destroy_result.stdout.splitlines() if line
        ]
    elif "no state file was found" in state_after_destroy_result.stderr.lower():
        state_after_destroy = []
    else:
        raise RuntimeError(
            "cannot inspect bootstrap Terraform state after destroy: "
            + state_after_destroy_result.stderr.strip()
        )
    if state_after_destroy == ["google_storage_bucket.terraform_state"]:
        run(
            [terraform, "state", "rm", "google_storage_bucket.terraform_state"],
            cwd=terraform_dir,
        )
    elif state_after_destroy:
        raise SystemExit(f"unexpected bootstrap state remains: {state_after_destroy}")

    authorization = f"{bucket_uri}/authorizations/single-paid-demo.json"
    all_versions_before = list_bucket_generations(bucket_uri, gcloud)
    if all_versions_before:
        run(
            [
                gcloud,
                "storage",
                "objects",
                "update",
                authorization,
                "--clear-temporary-hold",
            ],
            check=False,
        )
        run(all_generation_delete_command(bucket_uri, gcloud))
    all_versions_after = list_bucket_generations(bucket_uri, gcloud)
    if all_versions_after:
        raise SystemExit("state object generations remain after all-version deletion")
    run([gcloud, "storage", "buckets", "delete", bucket_uri])

    pools = json.loads(
        run(
            [
                gcloud,
                "iam",
                "workload-identity-pools",
                "list",
                "--location=global",
                f"--project={args.project}",
                "--format=json",
            ]
        ).stdout
    )
    expected_pool = "fde-gh-" + hashlib.sha256(args.state_bucket.encode()).hexdigest()[:12]
    fde_pools = [
        pool for pool in pools
        if str(pool.get("name", "")).rsplit("/", 1)[-1] in {expected_pool, "fde-github"}
    ]
    expected_accounts = {
        f"fde-{name}@{args.project}.iam.gserviceaccount.com"
        for name in ("build", "infra", "deploy", "cleanup")
    }
    service_accounts = json.loads(
        run(
            [
                gcloud,
                "iam",
                "service-accounts",
                "list",
                f"--project={args.project}",
                "--format=json",
            ]
        ).stdout
    )
    fde_accounts = [
        account
        for account in service_accounts
        if account.get("email") in expected_accounts
    ]
    policy = json.loads(
        run(
            [gcloud, "projects", "get-iam-policy", args.project, "--format=json"]
        ).stdout
    )
    fde_bindings = []
    for binding in policy.get("bindings", []):
        members = [
            member
            for member in binding.get("members", [])
            if member.removeprefix("serviceAccount:") in expected_accounts
        ]
        if members:
            fde_bindings.append({"role": binding.get("role"), "members": members})
    evidence = {
        "project": args.project,
        "state_bucket": args.state_bucket,
        "state_bucket_before": {
            "location": bucket.get("location"),
            "labels": labels,
            "versioning": normalized_versioning(bucket),
            "softDeletePolicy": bucket.get("soft_delete_policy")
            or bucket.get("softDeletePolicy"),
        },
        "object_generations_before": all_versions_before,
        "object_generations_after": all_versions_after,
        "bootstrap_state_before_bucket_retirement": state,
        "state_bucket_removed": run(
            [gcloud, "storage", "buckets", "describe", bucket_uri, "--format=json"],
            check=False,
        ).returncode
        != 0,
        "fde_workload_identity_pools": fde_pools,
        "fde_service_accounts": fde_accounts,
        "fde_project_iam_bindings": fde_bindings,
        "required_apis_intentionally_left_enabled": True,
    }
    args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_out.write_text(
        json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
    )
    if (
        not evidence["state_bucket_removed"]
        or evidence["fde_workload_identity_pools"]
        or evidence["fde_service_accounts"]
        or evidence["fde_project_iam_bindings"]
    ):
        raise SystemExit("bootstrap residue remains; inspect the private evidence file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
