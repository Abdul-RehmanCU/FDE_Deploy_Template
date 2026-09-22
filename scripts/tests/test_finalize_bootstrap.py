import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).parents[1] / "finalize_bootstrap.py"
SPEC = importlib.util.spec_from_file_location("finalize_bootstrap", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_state_bucket_deletion_includes_every_object_generation() -> None:
    assert MODULE.all_generation_delete_command("gs://fde-state") == [
        "gcloud",
        "storage",
        "rm",
        "--recursive",
        "--all-versions",
        "gs://fde-state/**",
    ]


def test_generation_inventory_excludes_object_contents(monkeypatch) -> None:
    def fake_run(command: list[str], *, check: bool = True):
        assert command == [
            "gcloud",
            "storage",
            "ls",
            "--all-versions",
            "--json",
            "gs://fde-state/**",
        ]
        assert check is False
        return SimpleNamespace(
            returncode=0,
            stdout='[{"name":"state/default.tfstate","generation":"7","temporaryHold":true,"sensitive":"excluded"}]',
        )

    monkeypatch.setattr(MODULE, "run", fake_run)
    assert MODULE.list_bucket_generations("gs://fde-state") == [
        {
            "name": "state/default.tfstate",
            "generation": "7",
            "temporaryHold": True,
            "eventBasedHold": False,
        }
    ]


def test_generation_inventory_fails_closed_on_list_error(monkeypatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "run",
        lambda command, check=False: SimpleNamespace(
            returncode=1, stdout="", stderr="denied"
        ),
    )
    with pytest.raises(RuntimeError, match="cannot verify"):
        MODULE.list_bucket_generations("gs://fde-state")


def test_positive_soft_delete_retention_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="soft delete must be disabled"):
        MODULE.require_soft_delete_disabled(
            {"softDeletePolicy": {"retentionDurationSeconds": "604800"}}
        )
    MODULE.require_soft_delete_disabled({"softDeletePolicy": {}})
    with pytest.raises(RuntimeError, match="soft delete must be disabled"):
        MODULE.require_soft_delete_disabled(
            {"soft_delete_policy": {"retention_duration_seconds": "604800"}}
        )
    MODULE.require_soft_delete_disabled({"soft_delete_policy": {}})
