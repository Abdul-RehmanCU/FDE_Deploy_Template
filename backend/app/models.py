import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import EmailStr
from sqlalchemy import JSON, Column, DateTime, Index, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class ImportStatus(StrEnum):
    UPLOADED = "uploaded"
    MAPPED = "mapped"
    VALIDATING = "validating"
    VALIDATED = "validated"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RowOutcome(StrEnum):
    ACCEPTED = "accepted"
    INVALID = "invalid"
    FILE_DUPLICATE = "file_duplicate"
    EXISTING_CONTACT = "existing_contact"


class JobKind(StrEnum):
    VALIDATE = "validate"
    CONFIRM = "confirm"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


class UserBase(SQLModel):
    email: EmailStr = Field(index=True, unique=True, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole = Field(
        default=UserRole.VIEWER,
        sa_column=Column(
            SAEnum(
                UserRole,
                values_callable=lambda members: [member.value for member in members],
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
    )
    is_active: bool = True


class UserCreate(SQLModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole = UserRole.VIEWER


class UserUpdate(SQLModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None


class User(UserBase, table=True):
    __tablename__ = "user"
    __table_args__ = (Index("ix_user_role", "role"),)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str = Field(max_length=255)
    # Retained for rollback compatibility with the imported upstream release.
    # API responses use `role` and never expose this legacy projection.
    is_superuser: bool = False
    must_change_password: bool = True
    token_version: int = 0
    created_at: datetime = Field(
        default_factory=utc_now, sa_type=DateTime(timezone=True)
    )  # type: ignore[call-overload]
    updated_at: datetime = Field(
        default_factory=utc_now, sa_type=DateTime(timezone=True)
    )  # type: ignore[call-overload]


class UserPublic(UserBase):
    id: uuid.UUID
    must_change_password: bool
    created_at: datetime
    updated_at: datetime


class UserCreated(UserPublic):
    temporary_password: str


class UserPage(SQLModel):
    data: list[UserPublic]
    next_cursor: str | None = None
    has_more: bool


class PasswordChange(SQLModel):
    current_password: str = Field(min_length=12, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class TemporaryPassword(SQLModel):
    temporary_password: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool = False


class TokenPayload(SQLModel):
    sub: str | None = None
    ver: int = 0


class Message(SQLModel):
    message: str


class ApiErrorDetail(SQLModel):
    code: str
    message: str
    fields: dict[str, str] | None = None


class ApiError(SQLModel):
    detail: ApiErrorDetail


class ImportBatch(SQLModel, table=True):
    __tablename__ = "import_batch"
    __table_args__ = (
        Index("ix_import_batch_status_created", "status", "created_at"),
        Index("ix_import_batch_created_by", "created_by_id"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    original_filename: str = Field(max_length=255)
    upload_object_key: str = Field(max_length=512, unique=True)
    status: ImportStatus = Field(
        default=ImportStatus.UPLOADED,
        sa_column=Column(
            SAEnum(
                ImportStatus,
                values_callable=lambda members: [member.value for member in members],
                native_enum=False,
                length=24,
            ),
            nullable=False,
        ),
    )
    mapping: dict[str, str] | None = Field(default=None, sa_column=Column(JSON))
    header: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    total_rows: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    duplicate_count: int = 0
    existing_contact_count: int = 0
    inserted_count: int = 0
    skipped_count: int = 0
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=500)
    confirm_idempotency_key: str | None = Field(default=None, max_length=128)
    confirmation_started_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )  # type: ignore[call-overload]
    created_by_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    created_at: datetime = Field(
        default_factory=utc_now, sa_type=DateTime(timezone=True)
    )  # type: ignore[call-overload]
    updated_at: datetime = Field(
        default_factory=utc_now, sa_type=DateTime(timezone=True)
    )  # type: ignore[call-overload]


class ValidationRow(SQLModel, table=True):
    __tablename__ = "validation_row"
    __table_args__ = (
        UniqueConstraint(
            "import_id", "row_number", name="uq_validation_row_import_number"
        ),
        Index(
            "ix_validation_row_import_outcome_row", "import_id", "outcome", "row_number"
        ),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    import_id: uuid.UUID = Field(foreign_key="import_batch.id", ondelete="CASCADE")
    row_number: int
    outcome: RowOutcome = Field(
        sa_column=Column(
            SAEnum(
                RowOutcome,
                values_callable=lambda members: [member.value for member in members],
                native_enum=False,
                length=24,
            ),
            nullable=False,
        )
    )
    normalized_email: str | None = Field(default=None, max_length=320)
    clean_data: dict[str, str | None] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    errors: list[dict[str, str]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(
        default_factory=utc_now, sa_type=DateTime(timezone=True)
    )  # type: ignore[call-overload]


class Contact(SQLModel, table=True):
    __tablename__ = "contact"
    __table_args__ = (
        Index("ix_contact_name_id", "last_name", "first_name", "id"),
        Index("ix_contact_created_id", "created_at", "id"),
        Index("ix_contact_import_id", "source_import_id"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(max_length=320)
    normalized_email: str = Field(max_length=320, unique=True, index=True)
    first_name: str = Field(max_length=120)
    last_name: str = Field(max_length=120)
    company: str | None = Field(default=None, max_length=255)
    country_code: str | None = Field(default=None, max_length=2)
    external_id: str | None = Field(default=None, max_length=255)
    source_import_id: uuid.UUID = Field(
        foreign_key="import_batch.id", ondelete="RESTRICT"
    )
    created_at: datetime = Field(
        default_factory=utc_now, sa_type=DateTime(timezone=True)
    )  # type: ignore[call-overload]
    updated_at: datetime = Field(
        default_factory=utc_now, sa_type=DateTime(timezone=True)
    )  # type: ignore[call-overload]


class Job(SQLModel, table=True):
    __tablename__ = "job"
    __table_args__ = (
        Index("ix_job_status_created", "status", "created_at"),
        Index("ix_job_import_id", "import_id"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    import_id: uuid.UUID = Field(foreign_key="import_batch.id", ondelete="CASCADE")
    kind: JobKind = Field(
        sa_column=Column(
            SAEnum(
                JobKind,
                values_callable=lambda members: [member.value for member in members],
                native_enum=False,
                length=16,
            ),
            nullable=False,
        )
    )
    status: JobStatus = Field(
        default=JobStatus.QUEUED,
        sa_column=Column(
            SAEnum(
                JobStatus,
                values_callable=lambda members: [member.value for member in members],
                native_enum=False,
                length=24,
            ),
            nullable=False,
        ),
    )
    attempt_count: int = 0
    max_attempts: int = 3
    traceparent: str | None = Field(default=None, max_length=255)
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=500)
    created_by_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    created_at: datetime = Field(
        default_factory=utc_now, sa_type=DateTime(timezone=True)
    )  # type: ignore[call-overload]
    started_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore[call-overload]
    finished_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore[call-overload]
    heartbeat_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore[call-overload]


class JobAttempt(SQLModel, table=True):
    __tablename__ = "job_attempt"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_job_attempt_number"),
        Index("ix_job_attempt_job_id", "job_id"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: uuid.UUID = Field(foreign_key="job.id", ondelete="CASCADE")
    attempt_number: int
    status: JobStatus = Field(
        sa_column=Column(
            SAEnum(
                JobStatus,
                values_callable=lambda members: [member.value for member in members],
                native_enum=False,
                length=24,
            ),
            nullable=False,
        )
    )
    worker_id: str | None = Field(default=None, max_length=255)
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=500)
    started_at: datetime = Field(
        default_factory=utc_now, sa_type=DateTime(timezone=True)
    )  # type: ignore[call-overload]
    finished_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore[call-overload]


class JobOutbox(SQLModel, table=True):
    __tablename__ = "job_outbox"
    __table_args__ = (
        Index("ix_job_outbox_pending", "published_at", "available_at", "created_at"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: uuid.UUID = Field(foreign_key="job.id", ondelete="CASCADE", unique=True)
    payload: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    available_at: datetime = Field(
        default_factory=utc_now, sa_type=DateTime(timezone=True)
    )  # type: ignore[call-overload]
    published_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore[call-overload]
    publish_attempts: int = 0
    last_error: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(
        default_factory=utc_now, sa_type=DateTime(timezone=True)
    )  # type: ignore[call-overload]


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_created_id", "created_at", "id"),
        Index("ix_audit_event_actor_id", "actor_id"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    actor_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    action: str = Field(max_length=100)
    resource_type: str = Field(max_length=64)
    resource_id: uuid.UUID | None = None
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column("metadata", JSON, nullable=False)
    )
    request_id: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(
        default_factory=utc_now, sa_type=DateTime(timezone=True)
    )  # type: ignore[call-overload]


class ImportPublic(SQLModel):
    id: uuid.UUID
    original_filename: str
    status: ImportStatus
    mapping: dict[str, str] | None
    header: list[str]
    total_rows: int
    accepted_count: int
    rejected_count: int
    duplicate_count: int
    existing_contact_count: int
    inserted_count: int
    skipped_count: int
    error_code: str | None
    error_message: str | None
    created_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MappingUpdate(SQLModel):
    mapping: dict[str, str]


class ImportAction(SQLModel):
    import_batch: ImportPublic
    job_id: uuid.UUID | None = None


class ImportPreview(SQLModel):
    header: list[str]
    rows: list[list[str]]
    truncated: bool


class ImportPage(SQLModel):
    data: list[ImportPublic]
    next_cursor: str | None = None
    has_more: bool


class ValidationRowPublic(SQLModel):
    row_number: int
    outcome: RowOutcome
    clean_data: dict[str, str | None] | None
    errors: list[dict[str, str]]


class ValidationRowPage(SQLModel):
    data: list[ValidationRowPublic]
    next_cursor: str | None = None
    has_more: bool


class ContactPublic(SQLModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    company: str | None
    country_code: str | None
    external_id: str | None
    created_at: datetime


class ContactPage(SQLModel):
    data: list[ContactPublic]
    next_cursor: str | None = None
    has_more: bool


class JobPublic(SQLModel):
    id: uuid.UUID
    import_id: uuid.UUID
    kind: JobKind
    status: JobStatus
    attempt_count: int
    max_attempts: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class JobAttemptPublic(SQLModel):
    attempt_number: int
    status: JobStatus
    error_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


class JobAttemptPage(SQLModel):
    data: list[JobAttemptPublic]
    next_cursor: str | None = None
    has_more: bool


class AuditEventPublic(SQLModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None
    metadata_json: dict[str, Any]
    request_id: str | None
    created_at: datetime


class AuditEventPage(SQLModel):
    data: list[AuditEventPublic]
    next_cursor: str | None = None
    has_more: bool


class DashboardPublic(SQLModel):
    imports_total: int
    contacts_total: int
    accepted_rows_total: int
    rejected_rows_total: int
    duplicate_rows_total: int
    jobs_by_status: dict[str, int]


class HealthPublic(SQLModel):
    status: str


class VersionPublic(SQLModel):
    version: str
    environment: str
