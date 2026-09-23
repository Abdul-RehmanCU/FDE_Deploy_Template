import json
from pathlib import Path

import pytest

from fde_cli import operations
from fde_cli.config import load_config
from fde_cli.doctor import REQUIRED_DEMO_SERVICES
from fde_cli.process import Result
from test_config import VALID, write

SERVICE = "cloudresourcemanager.googleapis.com"


@pytest.mark.parametrize("initially_enabled", [False, True])
def test_bootstrap_checks_api_before_storage_and_terraform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, initially_enabled: bool
) -> None:
    commands: list[list[str]] = []
    enabled = initially_enabled
    bucket = "example-fde-project-state-test"

    def fake_run(args, **kwargs):
        nonlocal enabled
        commands.append(list(args))
        stdout = ""
        if args[1:3] == ["services", "list"]:
            stdout = f"{SERVICE}\n" if enabled else ""
        elif args[1:3] == ["services", "enable"]:
            assert args[3:] == [SERVICE, "--project=example-fde-project", "--quiet"]
            enabled = True
        elif args[1:4] == ["storage", "buckets", "describe"]:
            assert enabled
            stdout = json.dumps({
                "location": "EXAMPLE-REGION1",
                "labels": {"application": "fde-template", "purpose": "terraform-state"},
            })
        elif args[1:4] == ["storage", "buckets", "list"]:
            stdout = json.dumps([{"name": bucket}])
        elif args[1:3] == ["state", "list"]:
            stdout = "google_storage_bucket.terraform_state\n"
        if args[0] == "terraform":
            assert enabled
        return Result(tuple(args), 0, stdout, "")

    monkeypatch.setattr(operations, "executable", lambda name: name)
    monkeypatch.setattr(operations, "run", fake_run)
    operations.bootstrap_gcp(
        load_config(write(tmp_path, VALID)),
        terraform_dir=tmp_path,
        state_bucket=bucket,
        github_repository="example/template",
        confirm_project="example-fde-project",
    )
    first_storage = next(i for i, args in enumerate(commands) if args[1] == "storage")
    assert all(args[1] == "services" for args in commands[:first_storage])
    assert commands[0][1:3] == ["services", "list"]
    assert sum(args[1:3] == ["services", "enable"] for args in commands) == (
        0 if initially_enabled else 1
    )
    assert any(args[0] == "terraform" and args[1] == "apply" for args in commands)


@pytest.mark.parametrize("activation_denied", [False, True])
def test_missing_api_stops_bootstrap_before_storage_or_terraform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, activation_denied: bool
) -> None:
    commands: list[list[str]] = []

    def fake_run(args, **kwargs):
        commands.append(list(args))
        assert args[0] == "gcloud" and args[1] == "services"
        if args[2] == "enable" and activation_denied:
            raise RuntimeError("PERMISSION_DENIED")
        return Result(tuple(args), 0, "", "")

    monkeypatch.setattr(operations, "executable", lambda name: name)
    monkeypatch.setattr(operations, "run", fake_run)
    with pytest.raises(operations.OperationError, match="No Terraform work has started"):
        operations.bootstrap_gcp(
            load_config(write(tmp_path, VALID)),
            terraform_dir=tmp_path,
            state_bucket="example-fde-project-state-test",
            github_repository="example/template",
            confirm_project="example-fde-project",
        )
    assert len(commands) == (2 if activation_denied else 3)


def test_readiness_inventory_includes_resource_manager() -> None:
    assert SERVICE in REQUIRED_DEMO_SERVICES
