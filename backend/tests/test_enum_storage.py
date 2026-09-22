from enum import Enum

from sqlalchemy.dialects import postgresql

from app.models import (
    ImportBatch,
    ImportStatus,
    Job,
    JobAttempt,
    JobKind,
    JobStatus,
    RowOutcome,
    User,
    UserRole,
    ValidationRow,
)


def stored_value(model: type[object], column_name: str, value: Enum) -> str:
    column = model.__table__.columns[column_name]  # type: ignore[attr-defined]
    processor = column.type.bind_processor(postgresql.dialect())
    assert processor is not None
    return processor(value)


def test_database_enums_use_lowercase_contract_values() -> None:
    assert stored_value(User, "role", UserRole.ADMIN) == "admin"
    assert stored_value(ImportBatch, "status", ImportStatus.VALIDATED) == "validated"
    assert (
        stored_value(ValidationRow, "outcome", RowOutcome.FILE_DUPLICATE)
        == "file_duplicate"
    )
    assert stored_value(Job, "kind", JobKind.CONFIRM) == "confirm"
    assert stored_value(Job, "status", JobStatus.CANCEL_REQUESTED) == "cancel_requested"
    assert stored_value(JobAttempt, "status", JobStatus.SUCCEEDED) == "succeeded"
