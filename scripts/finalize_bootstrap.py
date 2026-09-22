from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def run(
    command: list[str], *, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=check, text=True, capture_output=True)


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
    for executable in ("gcloud", "terraform"):
        if shutil.which(executable) is None:
            raise SystemExit(f"{executable} is required")

    root = Path(__file__).resolve().parents[1]
    terraform_dir = root / "infra" / "terraform" / "bootstrap"
    bucket_uri = f"gs://{args.state_bucket}"
    bucket = json.loads(
        run(
            ["gcloud", "storage", "buckets", "describe", bucket_uri, "--format=json"]
        ).stdout
    )
    project = json.loads(
        run(["gcloud", "projects", "describe", args.project, "--format=json"]).stdout
    )
    labels = bucket.get("labels", {})
    if (
        labels.get("application") != "fde-template"
        or labels.get("purpose") != "terraform-state"
    ):
        raise SystemExit(
            "state bucket labels do not identify the FDE Terraform state bucket"
        )
    if str(bucket.get("projectNumber")) != str(project.get("projectNumber")):
        raise SystemExit("state bucket does not belong to the confirmed project")
    if str(bucket.get("location", "")).lower() != args.region.lower():
        raise SystemExit("state bucket is not in the confirmed Montréal region")

    run(
        [
            "terraform",
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
    destroy = [
        "terraform",
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
    run(destroy, cwd=terraform_dir)
    state = [
        line
        for line in run(
            ["terraform", "state", "list"], cwd=terraform_dir
        ).stdout.splitlines()
        if line
    ]
    if state != ["google_storage_bucket.terraform_state"]:
        raise SystemExit(f"unexpected bootstrap state remains: {state}")
    run(
        ["terraform", "state", "rm", "google_storage_bucket.terraform_state"],
        cwd=terraform_dir,
    )

    authorization = f"{bucket_uri}/authorizations/single-paid-demo.json"
    run(
        [
            "gcloud",
            "storage",
            "objects",
            "update",
            authorization,
            "--clear-temporary-hold",
        ],
        check=False,
    )
    run(["gcloud", "storage", "rm", "--recursive", f"{bucket_uri}/"])
    run(["gcloud", "storage", "buckets", "delete", bucket_uri])

    pools = json.loads(
        run(
            [
                "gcloud",
                "iam",
                "workload-identity-pools",
                "list",
                "--location=global",
                f"--project={args.project}",
                "--format=json",
            ]
        ).stdout
    )
    fde_pools = [
        pool for pool in pools if str(pool.get("name", "")).endswith("/fde-github")
    ]
    expected_accounts = {
        f"fde-{name}@{args.project}.iam.gserviceaccount.com"
        for name in ("build", "infra", "deploy", "cleanup")
    }
    service_accounts = json.loads(
        run(
            [
                "gcloud",
                "iam",
                "service-accounts",
                "list",
                f"--project={args.project}",
                "--format=json",
            ]
        ).stdout
    )
    fde_accounts = [
        account for account in service_accounts if account.get("email") in expected_accounts
    ]
    policy = json.loads(
        run(
            ["gcloud", "projects", "get-iam-policy", args.project, "--format=json"]
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
        "bootstrap_state_before_bucket_retirement": state,
        "state_bucket_removed": run(
            ["gcloud", "storage", "buckets", "describe", bucket_uri, "--format=json"],
            check=False,
        ).returncode
        != 0,
        "fde_workload_identity_pools": fde_pools,
        "fde_service_accounts": fde_accounts,
        "fde_project_iam_bindings": fde_bindings,
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
