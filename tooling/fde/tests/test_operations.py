from datetime import datetime, timezone
from pathlib import Path

import pytest

from fde_cli.config import load_config
from fde_cli.operations import (
    OperationError,
    assert_scope,
    bootstrap_gcp,
    collect_plan_contract,
    deploy_demo,
    destroy_demo,
    validate_expiry_contract,
    validate_demo_cost_drivers,
)
from test_config import VALID, write


def config(tmp_path: Path):
    return load_config(write(tmp_path, VALID))


def test_explicit_scope_must_match_configuration(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    assert_scope(cfg, "acme", "staging", "fdetemplate")
    with pytest.raises(OperationError, match="does not match"):
        assert_scope(cfg, "other", "staging", "fdetemplate")


def test_managed_profile_cannot_deploy_under_demo_authorization(tmp_path: Path) -> None:
    cfg = load_config(write(tmp_path, VALID.replace("profile: demo", "profile: managed").replace("environment: staging", "environment: production")))
    with pytest.raises(OperationError, match="forbidden"):
        deploy_demo(
            cfg,
            gate_path=tmp_path / "gate.json",
            cost_path=tmp_path / "cost.yaml",
            terraform_dir=tmp_path,
            plan_path=tmp_path / "plan",
            chart=tmp_path,
            values=tmp_path / "values.yaml",
            expiry_terraform_dir=tmp_path,
            expiry_evidence_path=tmp_path / "expiry-evidence.json",
        )


def test_destroy_requires_exact_customer_before_running_tools(tmp_path: Path) -> None:
    with pytest.raises(OperationError, match="exactly match"):
        destroy_demo(config(tmp_path), tmp_path, "wrong", "demo-test-run")


def test_bootstrap_requires_exact_project_before_cloud_calls(tmp_path: Path) -> None:
    with pytest.raises(OperationError, match="exactly match"):
        bootstrap_gcp(
            config(tmp_path),
            terraform_dir=tmp_path,
            state_bucket="fdetemplate-state-test",
            github_repository="Abdul-RehmanCU/FDE_Deploy_Template",
            confirm_project="wrong-project",
        )


def expiry_contract() -> dict[str, object]:
    return {
        "project": "fdetemplate",
        "region": "northamerica-northeast1",
        "zone": "northamerica-northeast1-a",
        "gate_expires_at": datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc),
        "gate_sha": "a" * 64,
        "state_sha": "a" * 64,
        "manifest": {
            "project_id": "fdetemplate",
            "expiry_id": "demo-run-001",
            "expires_at": "2026-09-22T10:00:00Z",
            "region": "northamerica-northeast1",
            "zone": "northamerica-northeast1-a",
            "cluster_name": "fde-demo",
            "bucket_names": ["fdetemplate-fde-demo-production-demo", "fdetemplate-fde-demo-staging"],
            "artifact_repository": "fde-demo-images",
            "disk_resources": [{"name": "disk-a"}, {"name": "disk-b"}],
        },
        "sentinel": {"status": "sentinel-ok", "manifest_sha": "a" * 64, "expiry_id": "demo-run-001"},
        "planned_disks": {"disk-a": "demo-run-001", "disk-b": "demo-run-001"},
        "planned_clusters": {"fde-demo": "demo-run-001"},
        "planned_buckets": {
            "fdetemplate-fde-demo-production-demo": "demo-run-001",
            "fdetemplate-fde-demo-staging": "demo-run-001",
        },
        "planned_repositories": {"fde-demo-images": "demo-run-001"},
    }


def test_expiry_contract_accepts_exact_live_evidence() -> None:
    validate_expiry_contract(**expiry_contract())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("state_sha", "b" * 64, "SHA"),
        ("planned_disks", {"disk-a": "demo-run-001"}, "disk set"),
        ("planned_disks", {"disk-a": "other", "disk-b": "other"}, "expiry_id"),
        ("sentinel", {}, "SHA"),
        ("gate_expires_at", datetime(2026, 9, 22, 11, 0, tzinfo=timezone.utc), "deadline"),
        ("region", "us-central1", "region/zone"),
        ("zone", "northamerica-northeast1-b", "region/zone"),
        ("planned_clusters", {"other": "demo-run-001"}, "cluster set"),
        ("planned_buckets", {"other": "demo-run-001"}, "bucket set"),
        ("planned_repositories", {"other": "demo-run-001"}, "repository set"),
    ],
)
def test_expiry_contract_rejects_fake_or_drifted_evidence(
    field: str, value: object, message: str
) -> None:
    contract = expiry_contract()
    contract[field] = value
    with pytest.raises(OperationError, match=message):
        validate_expiry_contract(**contract)  # type: ignore[arg-type]


def representative_plan_resources() -> list[dict[str, object]]:
    labels = {"expiry-id": "demo-run-001"}
    resources: list[dict[str, object]] = [
        {"type": "google_container_cluster", "values": {"name": "fde-demo", "location": "northamerica-northeast1-a", "resource_labels": labels}},
        {"type": "google_container_node_pool", "values": {"name": "fixed-demo", "node_count": 1, "autoscaling": [], "node_config": [{"machine_type": "e2-standard-4", "disk_type": "pd-standard", "disk_size_gb": 30}]}},
        {"type": "google_artifact_registry_repository", "values": {"name": None, "repository_id": "fde-demo-images", "labels": labels}},
        {"type": "google_storage_bucket", "values": {"name": "bucket-a", "labels": labels}},
        {"type": "google_storage_bucket", "values": {"name": "bucket-b", "labels": labels}},
    ]
    for index, size in enumerate([5, 5, 8, 8, 8, 10, 10]):
        resources.append({"type": "google_compute_disk", "values": {"name": f"disk-{index}", "size": size, "type": "pd-standard", "labels": labels}})
    return resources


def test_plan_collector_uses_repository_id_when_computed_name_is_null() -> None:
    plan = {"planned_values": {"root_module": {"child_modules": [{"resources": representative_plan_resources()}]}}}
    disks, clusters, buckets, repositories, resources = collect_plan_contract(plan)
    assert repositories == {"fde-demo-images": "demo-run-001"}
    assert len(disks) == 7 and clusters == {"fde-demo": "demo-run-001"}
    assert sorted(buckets) == ["bucket-a", "bucket-b"]
    validate_demo_cost_drivers(resources, zone="northamerica-northeast1-a")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("google_container_node_pool", "node_count", 2), "one fixed node"),
        (("google_container_node_pool", "autoscaling", [{"max_node_count": 2}]), "autoscaling"),
        (("google_container_cluster", "location", "us-central1-a"), "zonal Montréal"),
        (("google_compute_disk", "type", "pd-ssd"), "54 GiB"),
        (("google_compute_disk", "size", 20), "54 GiB"),
    ],
)
def test_cost_driver_gate_rejects_pricing_drift(
    mutation: tuple[str, str, object], message: str
) -> None:
    resource_type, field, value = mutation
    resources = representative_plan_resources()
    target = next(item for item in resources if item["type"] == resource_type)
    target["values"][field] = value  # type: ignore[index]
    with pytest.raises(OperationError, match=message):
        validate_demo_cost_drivers(resources, zone="northamerica-northeast1-a")


def test_cost_driver_gate_rejects_public_load_balancer_or_managed_service() -> None:
    resources = representative_plan_resources()
    resources.append({"type": "google_compute_forwarding_rule", "values": {}})
    with pytest.raises(OperationError, match="public-LB"):
        validate_demo_cost_drivers(resources, zone="northamerica-northeast1-a")


def test_cost_driver_gate_rejects_larger_machine() -> None:
    resources = representative_plan_resources()
    pool = next(item for item in resources if item["type"] == "google_container_node_pool")
    pool["values"]["node_config"][0]["machine_type"] = "e2-standard-8"  # type: ignore[index]
    with pytest.raises(OperationError, match="machine"):
        validate_demo_cost_drivers(resources, zone="northamerica-northeast1-a")
