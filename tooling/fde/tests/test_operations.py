from pathlib import Path

import pytest

from fde_cli.config import load_config
from fde_cli.operations import OperationError, assert_scope, deploy_demo, destroy_demo
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
        )


def test_destroy_requires_exact_customer_before_running_tools(tmp_path: Path) -> None:
    with pytest.raises(OperationError, match="exactly match"):
        destroy_demo(config(tmp_path), tmp_path, "wrong")
