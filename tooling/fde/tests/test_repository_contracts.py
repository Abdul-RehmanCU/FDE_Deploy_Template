from pathlib import Path

import yaml

ROOT = Path(__file__).parents[3]


def terraform_block(text: str, header: str) -> str:
    start = text.index(header)
    opening = text.index("{", start)
    depth = 0
    for index in range(opening, len(text)):
        character = text[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unterminated Terraform block: {header}")


def test_bootstrap_enables_cloud_resource_manager_before_project_resources() -> None:
    text = (ROOT / "infra" / "terraform" / "bootstrap" / "main.tf").read_text(
        encoding="utf-8"
    )
    start = text.index("required_services = toset([")
    end = text.index("])\n", start) + 2
    services = text[start:end]
    assert '"cloudresourcemanager.googleapis.com"' in services
    assert 'resource "google_project_service" "required"' in text

    for header in (
        'resource "google_storage_bucket" "terraform_state"',
        'resource "google_service_account" "automation"',
        'resource "google_iam_workload_identity_pool" "github"',
        'resource "google_iam_workload_identity_pool_provider" "github"',
        'resource "google_service_account_iam_member" "github_federation"',
        'resource "google_storage_bucket_iam_member" "infra_state"',
        'resource "google_project_iam_member" "automation_roles"',
    ):
        assert "depends_on = [google_project_service.required]" in terraform_block(
            text, header
        ), header


def test_publisher_recreate_prevents_old_observability_configuration_overlap() -> None:
    text = (ROOT / "infra" / "helm" / "fde" / "templates" / "publisher.yaml").read_text(
        encoding="utf-8"
    )
    assert "  strategy:\n    type: Recreate" in text


def test_called_cleanup_has_explicit_authorization_for_dispatch_callers() -> None:
    caller = yaml.load((ROOT / ".github/workflows/gcp-demo.yml").read_text(), Loader=yaml.BaseLoader)
    cleanup_call = next(job for job in caller["jobs"].values()
                        if job.get("uses") == "./.github/workflows/gcp-cleanup.yml")
    callee = yaml.load((ROOT / ".github/workflows/gcp-cleanup.yml").read_text(), Loader=yaml.BaseLoader)
    assert cleanup_call["with"]["confirm_cleanup"] == "DESTROY-DEMO"
    assert callee["on"]["workflow_call"]["inputs"]["confirm_cleanup"]["required"] == "true"
    # Reusable workflows inherit the caller's event_name, including dispatch.
    assert callee["jobs"]["cleanup"]["if"] == "inputs.confirm_cleanup == 'DESTROY-DEMO'"


def test_expiry_accepts_the_intentionally_empty_address_allowlist() -> None:
    text = (ROOT / "infra" / "terraform" / "modules" / "expiry" / "variables.tf").read_text(
        encoding="utf-8"
    )
    block = terraform_block(text, 'variable "address_resources"')
    assert 'default     = []' in block
    assert 'join(",", [for resource in var.address_resources : resource.name])' in block


def test_expiry_custom_role_uses_supported_artifact_registry_permissions() -> None:
    text = (ROOT / "infra" / "terraform" / "modules" / "expiry" / "main.tf").read_text(
        encoding="utf-8"
    )
    block = terraform_block(text, 'resource "google_project_iam_custom_role" "cleanup"')
    assert '"artifactregistry.repositories.get"' in block
    assert '"artifactregistry.repositories.delete"' in block
    assert 'artifactregistry.operations.get' not in block
