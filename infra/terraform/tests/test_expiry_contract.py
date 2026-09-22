import json
import re
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / "modules" / "expiry" / "workflow.yaml.tftpl"
EXPIRY_MAIN = ROOT / "modules" / "expiry" / "main.tf"
BOOTSTRAP_MAIN = ROOT / "bootstrap" / "main.tf"


def rendered_workflow() -> str:
    manifest = {
        "project_id": "fdetemplate",
        "project_number": "653399508708",
        "region": "northamerica-northeast1",
        "zone": "northamerica-northeast1-a",
        "expiry_id": "demo-20260922",
        "expires_at": "2026-09-22T12:00:00Z",
        "cluster_name": "fde-demo",
        "artifact_repository": "fde-demo-images",
        "bucket_names": ["fdetemplate-fde-demo-staging"],
        "disk_resources": [{"name": "pvc-exact-name", "expiry_id": "demo-20260922"}],
        "address_resources": [],
    }
    return WORKFLOW.read_text(encoding="utf-8").replace("${manifest_json}", json.dumps(manifest)).replace("$${", "${")


def test_rendered_workflow_is_yaml() -> None:
    document = yaml.safe_load(rendered_workflow())
    assert set(document) == {
        "main",
        "delete_gke_cluster",
        "delete_compute_resource",
        "empty_bucket",
        "delete_gcs_object",
        "delete_repository",
    }


def test_probe_guards_precede_all_delete_calls() -> None:
    text = rendered_workflow()
    first_delete = text.index("- delete_cluster:")
    assert text.index("manifest fingerprint mismatch") < first_delete
    assert text.index("compiled project does not match") < first_delete
    assert text.index("compiled project number does not match") < first_delete
    assert text.index("status: \"sentinel-ok\"") < first_delete
    assert text.index("status: \"not-due\"") < first_delete
    assert "status: \"stale-window\"" not in text
    assert 'mode in ["sentinel", "dry-run"]' in text
    assert 'mode in ["cleanup", "recovery"] and sys.now() < time.parse(manifest.expires_at)' in text
    assert '"recovery"' in text
    cluster_function = text[text.index("delete_gke_cluster:") : text.index("delete_compute_resource:")]
    assert cluster_function.index("verify_owner") < cluster_function.index("request_delete")


def test_cleanup_polls_operations_and_retries_http() -> None:
    text = rendered_workflow()
    assert "/operations/" in text
    assert text.count("retry: ${http.default_retry}") >= 10
    assert "GKE deletion exceeded ten minutes" in text
    assert "Compute deletion exceeded ten minutes" in text
    assert "Artifact Registry deletion exceeded ten minutes" in text


def test_bucket_cleanup_covers_versions_replay_and_concurrency() -> None:
    text = rendered_workflow()
    assert "versions: true" in text
    assert "generation: ${generation}" in text
    assert text.count("e.code == 404") >= 5
    assert "e.code == 409" in text
    assert "list_first_page" in text
    assert "pageToken" not in text
    assert text.index("verify_bucket_owner") < text.index("list_first_page")
    assert "verify_repository_owner" in text
    assert "creationTimestamp != creation_timestamp" in text
    assert '"expiry-id") != expected_expiry_id' in text
    assert "cleanup-incomplete" in text


def test_scheduler_has_recovery_run_and_bounded_apply_window() -> None:
    text = EXPIRY_MAIN.read_text(encoding="utf-8")
    assert 'recovery_1 = timeadd(var.expires_at, "10m")' in text
    assert 'recovery_2 = timeadd(var.expires_at, "20m")' in text
    assert 'timeadd(timestamp(), "3h40m")' in text
    assert 'role   = "roles/workflows.invoker"' in text
    assert "resource.name ==" not in text


def test_expiry_timestamp_must_be_exact_utc_minute() -> None:
    text = (ROOT / "modules" / "expiry" / "variables.tf").read_text(encoding="utf-8")
    assert "T[0-9]{2}:[0-9]{2}:00Z" in text


def terraform_console(expression: str) -> str:
    completed = subprocess.run(
        ["terraform", "console"],
        cwd=ROOT / "modules" / "expiry",
        input=expression + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    plain = re.sub(r"\x1b\[[0-9;]*m", "", completed.stdout)
    return plain.strip().splitlines()[-1].strip('"')


def test_real_terraform_trigger_rendering_stays_on_or_after_deadline() -> None:
    primary = terraform_console('formatdate("m h D M *", "2026-09-22T12:00:00Z")')
    recovery_1 = terraform_console('formatdate("m h D M *", timeadd("2026-09-22T12:00:00Z", "10m"))')
    recovery_2 = terraform_console('formatdate("m h D M *", timeadd("2026-09-22T12:00:00Z", "20m"))')
    assert primary == "0 12 22 9 *"
    assert recovery_1 == "10 12 22 9 *"
    assert recovery_2 == "20 12 22 9 *"


def test_workload_identities_have_separate_provider_attributes() -> None:
    text = BOOTSTRAP_MAIN.read_text(encoding="utf-8")
    assert '"attribute.automation"' in text
    assert "/attribute.automation/${each.key}" in text
    for identity in ("build", "infra", "deploy", "cleanup"):
        assert f"{identity}" in text
    assert "demo-infrastructure" in text
    assert "demo-staging" in text
    assert "demo-cleanup" in text
    assert "demo-build" in text
    assert "pull_request" not in text
    assert '"roles/iam.serviceAccountUser"' not in text
    assert "Abdul-RehmanCU" not in text
    assert 'github_owner = split("/", var.github_repository)[0]' in text


def test_wif_owner_derives_from_reusable_repository_variable() -> None:
    repository = "ExampleOrg/template-fork"
    derived_owner = repository.split("/")[0]
    text = BOOTSTRAP_MAIN.read_text(encoding="utf-8")
    assert derived_owner == "ExampleOrg"
    assert "assertion.repository_owner == '${local.github_owner}'" in text
    assert "assertion.repository == '${var.github_repository}'" in text


def test_runtime_secret_and_act_as_bindings_are_resource_scoped() -> None:
    demo = (ROOT / "modules" / "demo" / "main.tf").read_text(encoding="utf-8")
    expiry = (ROOT / "modules" / "expiry" / "main.tf").read_text(encoding="utf-8")
    assert 'resource "google_secret_manager_secret_iam_member" "runtime"' in demo
    assert 'resource "google_project_iam_member" "runtime_secrets"' not in demo
    assert 'resource "google_service_account_iam_member" "infra_can_use_nodes"' in demo
    assert 'resource "google_service_account_iam_member" "infra_can_use_workflow"' in expiry
    assert 'resource "google_service_account_iam_member" "infra_can_use_scheduler"' in expiry
    assert "disk_names" in expiry
    assert "expiry_id = var.expiry_id" in expiry
