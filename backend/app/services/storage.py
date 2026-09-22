from pathlib import Path, PurePosixPath
from typing import Protocol

from google.cloud import storage as gcs  # type: ignore[import-untyped]

from app.core.config import settings


class ObjectStorage(Protocol):
    def put(self, key: str, content: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


def _safe_key(key: str) -> PurePosixPath:
    path = PurePosixPath(key)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Invalid object key")
    return path


class LocalObjectStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        safe = _safe_key(key)
        path = self.root.joinpath(*safe.parts).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid object key")
        return path

    def put(self, key: str, content: bytes, content_type: str) -> None:
        del content_type
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class GCSObjectStorage:
    def __init__(self, bucket_name: str) -> None:
        self.bucket = gcs.Client().bucket(bucket_name)

    def put(self, key: str, content: bytes, content_type: str) -> None:
        self.bucket.blob(str(_safe_key(key))).upload_from_string(
            content, content_type=content_type
        )

    def get(self, key: str) -> bytes:
        return self.bucket.blob(str(_safe_key(key))).download_as_bytes()

    def delete(self, key: str) -> None:
        self.bucket.blob(str(_safe_key(key))).delete(if_generation_match=None)


def get_storage() -> ObjectStorage:
    if settings.STORAGE_BACKEND == "gcs":
        assert settings.GCS_BUCKET
        return GCSObjectStorage(settings.GCS_BUCKET)
    return LocalObjectStorage(settings.STORAGE_LOCAL_ROOT)
