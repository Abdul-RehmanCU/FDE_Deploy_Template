import json
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
        "disk_names": ["pvc-exact-name"],
        "address_names": [],
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


def test_scheduler_has_recovery_run_and_bounded_apply_window() -> None:
    text = EXPIRY_MAIN.read_text(encoding="utf-8")
    assert 'recovery = timeadd(var.expires_at, "10m")' in text
    assert 'timeadd(timestamp(), "3h50m")' in text
    assert "resource.name ==" in text


def test_workload_identities_have_separate_provider_attributes() -> None:
    text = BOOTSTRAP_MAIN.read_text(encoding="utf-8")
    assert '"attribute.automation"' in text
    assert "/attribute.automation/${each.key}" in text
    for identity in ("build", "infra", "deploy", "cleanup"):
        assert f"{identity}" in text
    assert "demo-infrastructure" in text
    assert "demo-staging" in text
    assert "demo-cleanup" in text
