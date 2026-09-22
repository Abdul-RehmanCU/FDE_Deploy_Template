from pathlib import Path

import pytest

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
