import asyncio
import io

import pytest
from starlette.datastructures import UploadFile

from app.api.routes import imports
from app.models import User, UserRole


class FailingSession:
    def add(self, value: object) -> None:
        del value

    def commit(self) -> None:
        raise RuntimeError("simulated database failure")

    def rollback(self) -> None:
        return None


class RecordingStorage:
    def __init__(self) -> None:
        self.put_key: str | None = None
        self.deleted_key: str | None = None

    def put(self, key: str, content: bytes, content_type: str) -> None:
        del content, content_type
        self.put_key = key

    def delete(self, key: str) -> None:
        self.deleted_key = key


def test_upload_object_is_compensated_when_database_commit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = RecordingStorage()
    monkeypatch.setattr(imports, "get_storage", lambda: storage)
    upload = UploadFile(
        filename="contacts.csv",
        file=io.BytesIO(b"Email,First,Last\none@example.com,One,Person\n"),
    )
    user = User(
        email="operator@example.com",
        role=UserRole.OPERATOR,
        hashed_password="unused",
        must_change_password=False,
    )
    with pytest.raises(RuntimeError, match="simulated database failure"):
        asyncio.run(
            imports.upload_import(
                session=FailingSession(),  # type: ignore[arg-type]
                current_user=user,
                file=upload,
            )
        )
    assert storage.put_key is not None
    assert storage.deleted_key == storage.put_key
