import importlib.util
from pathlib import Path

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
