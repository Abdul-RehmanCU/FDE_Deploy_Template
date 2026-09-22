import os
from datetime import timedelta
from pathlib import Path

import pytest

from app.cleanup_storage import cleanup_expired_intermediates
from app.models import utc_now
from app.services.storage import LocalObjectStorage


def test_local_storage_round_trip_and_delete(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path)
    storage.put("uploads/123/source.csv", b"hello", "text/csv")
    assert storage.get("uploads/123/source.csv") == b"hello"
    storage.delete("uploads/123/source.csv")
    with pytest.raises(FileNotFoundError):
        storage.get("uploads/123/source.csv")


@pytest.mark.parametrize("key", ["../secret", "/absolute", "a/../../secret"])
def test_local_storage_rejects_path_traversal(tmp_path: Path, key: str) -> None:
    with pytest.raises(ValueError, match="Invalid object key"):
        LocalObjectStorage(tmp_path).put(key, b"x", "text/plain")


def test_cleanup_removes_only_expired_intermediate_objects(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path)
    storage.put("uploads/old/source.csv", b"old", "text/csv")
    storage.put("reports/old/errors.csv", b"old", "text/csv")
    storage.put("uploads/new/source.csv", b"new", "text/csv")
    old_timestamp = (utc_now() - timedelta(days=8)).timestamp()
    os.utime(tmp_path / "uploads" / "old" / "source.csv", (old_timestamp, old_timestamp))
    os.utime(tmp_path / "reports" / "old" / "errors.csv", (old_timestamp, old_timestamp))
    assert cleanup_expired_intermediates(storage) == 2
    assert storage.get("uploads/new/source.csv") == b"new"
    with pytest.raises(FileNotFoundError):
        storage.get("uploads/old/source.csv")
