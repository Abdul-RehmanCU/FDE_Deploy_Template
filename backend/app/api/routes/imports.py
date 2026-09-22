import base64
import uuid

from fastapi import APIRouter, File, Header, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import tuple_
from sqlmodel import col, select

from app.api.deps import OperatorUser, ReadyUser, SessionDep
from app.api.errors import api_error
from app.api.pagination import decode_cursor, encode_cursor
from app.core.config import settings
from app.models import (
    ImportAction,
    ImportBatch,
    ImportPage,
    ImportPreview,
    ImportPublic,
    ImportStatus,
    Job,
    JobKind,
    JobStatus,
    MappingUpdate,
    RowOutcome,
    ValidationRow,
    ValidationRowPage,
    ValidationRowPublic,
    utc_now,
)
from app.services.audit import record_audit
from app.services.csv_import import (
    CsvValidationError,
    inspect_csv,
    preview_csv,
    validate_mapping,
)
from app.services.jobs import enqueue_job
from app.services.storage import get_storage

router = APIRouter(prefix="/imports", tags=["imports"])


def get_import_or_404(session: SessionDep, import_id: uuid.UUID) -> ImportBatch:
    batch = session.get(ImportBatch, import_id)
    if not batch:
        api_error(404, "import_not_found", "Import not found")
    return batch


async def read_bounded_upload(file: UploadFile) -> bytes:
    content = bytearray()
    while chunk := await file.read(64 * 1024):
        content.extend(chunk)
        if len(content) > settings.UPLOAD_MAX_BYTES:
            api_error(413, "file_too_large", "CSV files may be at most 10 MiB")
    return bytes(content)


@router.post("", response_model=ImportPublic, status_code=201)
async def upload_import(
    *,
    session: SessionDep,
    current_user: OperatorUser,
    file: UploadFile = File(...),
) -> ImportBatch:
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".csv"):
        api_error(400, "unsupported_file_type", "Upload a CSV file")
    content = await read_bounded_upload(file)
    try:
        inspection = inspect_csv(content, settings.UPLOAD_MAX_ROWS)
    except CsvValidationError as exc:
        api_error(400, exc.code, exc.message)
    batch_id = uuid.uuid4()
    object_key = f"uploads/{batch_id}/source.csv"
    storage = get_storage()
    storage.put(object_key, content, "text/csv")
    batch = ImportBatch(
        id=batch_id,
        original_filename=filename[:255],
        upload_object_key=object_key,
        header=inspection.header,
        total_rows=inspection.total_rows,
        created_by_id=current_user.id,
    )
    session.add(batch)
    record_audit(
        session,
        actor_id=current_user.id,
        action="import.uploaded",
        resource_type="import",
        resource_id=batch.id,
        metadata={"total_rows": inspection.total_rows},
    )
    try:
        session.commit()
    except Exception:
        session.rollback()
        storage.delete(object_key)
        raise
    session.refresh(batch)
    return batch


@router.get("", response_model=ImportPage)
def list_imports(
    session: SessionDep,
    current_user: ReadyUser,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> ImportPage:
    del current_user
    statement = select(ImportBatch).order_by(
        col(ImportBatch.created_at).desc(), col(ImportBatch.id).desc()
    )
    if cursor:
        created_at, import_id = decode_cursor(cursor)
        statement = statement.where(
            tuple_(col(ImportBatch.created_at), col(ImportBatch.id))
            < (created_at, import_id)
        )
    rows = list(session.exec(statement.limit(limit + 1)).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more else None
    return ImportPage(data=[ImportPublic.model_validate(row) for row in rows], next_cursor=next_cursor, has_more=has_more)


@router.get("/{import_id}", response_model=ImportPublic)
def get_import(import_id: uuid.UUID, session: SessionDep, current_user: ReadyUser) -> ImportBatch:
    del current_user
    return get_import_or_404(session, import_id)


@router.get("/{import_id}/preview", response_model=ImportPreview)
def preview_import(
    import_id: uuid.UUID, session: SessionDep, current_user: ReadyUser
) -> ImportPreview:
    del current_user
    batch = get_import_or_404(session, import_id)
    try:
        header, rows, truncated = preview_csv(get_storage().get(batch.upload_object_key))
    except FileNotFoundError:
        api_error(404, "upload_not_found", "The uploaded CSV is no longer available")
    return ImportPreview(header=header, rows=rows, truncated=truncated)


@router.put("/{import_id}/mapping", response_model=ImportPublic)
def set_mapping(
    import_id: uuid.UUID,
    body: MappingUpdate,
    session: SessionDep,
    current_user: OperatorUser,
) -> ImportBatch:
    batch = get_import_or_404(session, import_id)
    if batch.status not in (ImportStatus.UPLOADED, ImportStatus.MAPPED, ImportStatus.FAILED):
        api_error(409, "import_not_mappable", "This import can no longer be remapped")
    try:
        validate_mapping(body.mapping, batch.header)
    except CsvValidationError as exc:
        api_error(400, exc.code, exc.message)
    batch.mapping = body.mapping
    batch.status = ImportStatus.MAPPED
    batch.error_code = None
    batch.error_message = None
    batch.updated_at = utc_now()
    session.add(batch)
    record_audit(
        session,
        actor_id=current_user.id,
        action="import.mapped",
        resource_type="import",
        resource_id=batch.id,
        metadata={"mapped_fields": sorted(body.mapping)},
    )
    session.commit()
    session.refresh(batch)
    return batch


@router.post("/{import_id}/validate", response_model=ImportAction, status_code=202)
def validate_import(
    import_id: uuid.UUID,
    session: SessionDep,
    current_user: OperatorUser,
    traceparent: str | None = Header(default=None),
) -> ImportAction:
    batch = session.exec(
        select(ImportBatch).where(ImportBatch.id == import_id).with_for_update()
    ).one_or_none()
    if not batch:
        api_error(404, "import_not_found", "Import not found")
    if batch.status != ImportStatus.MAPPED:
        api_error(409, "import_not_ready", "Map the CSV columns before validation")
    batch.status = ImportStatus.VALIDATING
    batch.updated_at = utc_now()
    job = enqueue_job(
        session,
        import_batch=batch,
        kind=JobKind.VALIDATE,
        actor=current_user,
        traceparent=traceparent,
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return ImportAction(import_batch=ImportPublic.model_validate(batch), job_id=job.id)


@router.post("/{import_id}/confirm", response_model=ImportAction, status_code=202)
def confirm_import(
    import_id: uuid.UUID,
    session: SessionDep,
    current_user: OperatorUser,
    idempotency_key: str = Header(min_length=8, max_length=128, alias="Idempotency-Key"),
    traceparent: str | None = Header(default=None),
) -> ImportAction:
    batch = session.exec(
        select(ImportBatch).where(ImportBatch.id == import_id).with_for_update()
    ).one_or_none()
    if not batch:
        api_error(404, "import_not_found", "Import not found")
    if batch.confirm_idempotency_key:
        if batch.confirm_idempotency_key != idempotency_key:
            api_error(409, "idempotency_conflict", "This import was confirmed with another key")
        existing = session.exec(
            select(Job)
            .where(Job.import_id == batch.id, Job.kind == JobKind.CONFIRM)
            .order_by(col(Job.created_at).desc())
        ).first()
        return ImportAction(
            import_batch=ImportPublic.model_validate(batch),
            job_id=existing.id if existing else None,
        )
    if batch.status != ImportStatus.VALIDATED:
        api_error(409, "import_not_ready", "Validation must finish before confirmation")
    batch.confirm_idempotency_key = idempotency_key
    job = enqueue_job(
        session,
        import_batch=batch,
        kind=JobKind.CONFIRM,
        actor=current_user,
        traceparent=traceparent,
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return ImportAction(import_batch=ImportPublic.model_validate(batch), job_id=job.id)


@router.post("/{import_id}/cancel", response_model=ImportAction)
def cancel_import(
    import_id: uuid.UUID, session: SessionDep, current_user: OperatorUser
) -> ImportAction:
    batch = get_import_or_404(session, import_id)
    if batch.confirmation_started_at is not None or batch.status in (
        ImportStatus.IMPORTING,
        ImportStatus.COMPLETED,
    ):
        api_error(409, "import_commit_started", "The atomic import has already started")
    job = session.exec(
        select(Job)
        .where(
            Job.import_id == import_id,
            col(Job.status).in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
        .order_by(col(Job.created_at).desc())
        .with_for_update()
    ).first()
    if not job:
        api_error(409, "job_not_cancellable", "There is no cancellable job")
    job.status = JobStatus.CANCEL_REQUESTED
    session.add(job)
    record_audit(
        session,
        actor_id=current_user.id,
        action="job.cancel_requested",
        resource_type="job",
        resource_id=job.id,
    )
    session.commit()
    session.refresh(batch)
    return ImportAction(import_batch=ImportPublic.model_validate(batch), job_id=job.id)


@router.post("/{import_id}/retry", response_model=ImportAction, status_code=202)
def retry_import(
    import_id: uuid.UUID,
    session: SessionDep,
    current_user: OperatorUser,
    traceparent: str | None = Header(default=None),
) -> ImportAction:
    batch = get_import_or_404(session, import_id)
    failed = session.exec(
        select(Job)
        .where(Job.import_id == import_id, Job.status == JobStatus.FAILED)
        .order_by(col(Job.created_at).desc())
        .with_for_update()
    ).first()
    if not failed:
        api_error(409, "job_not_retryable", "There is no failed job to retry")
    if failed.kind == JobKind.CONFIRM:
        batch.status = ImportStatus.VALIDATED
    else:
        batch.status = ImportStatus.MAPPED
    batch.error_code = None
    batch.error_message = None
    job = enqueue_job(
        session,
        import_batch=batch,
        kind=failed.kind,
        actor=current_user,
        traceparent=traceparent,
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return ImportAction(import_batch=ImportPublic.model_validate(batch), job_id=job.id)


def encode_row_cursor(row_number: int) -> str:
    return base64.urlsafe_b64encode(str(row_number).encode()).decode().rstrip("=")


def decode_row_cursor(cursor: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode())
    except (ValueError, UnicodeDecodeError):
        api_error(400, "invalid_cursor", "The pagination cursor is invalid")


@router.get("/{import_id}/rows", response_model=ValidationRowPage)
def list_validation_rows(
    import_id: uuid.UUID,
    session: SessionDep,
    current_user: ReadyUser,
    outcome: RowOutcome | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> ValidationRowPage:
    del current_user
    get_import_or_404(session, import_id)
    statement = select(ValidationRow).where(ValidationRow.import_id == import_id)
    if outcome:
        statement = statement.where(ValidationRow.outcome == outcome)
    if cursor:
        statement = statement.where(ValidationRow.row_number > decode_row_cursor(cursor))
    rows = list(
        session.exec(
            statement.order_by(col(ValidationRow.row_number)).limit(limit + 1)
        ).all()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_row_cursor(rows[-1].row_number) if has_more else None
    return ValidationRowPage(
        data=[ValidationRowPublic.model_validate(row) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{import_id}/reports/{report_name}")
def download_report(
    import_id: uuid.UUID,
    report_name: str,
    session: SessionDep,
    current_user: OperatorUser,
) -> Response:
    del current_user
    batch = get_import_or_404(session, import_id)
    if batch.status not in (ImportStatus.VALIDATED, ImportStatus.COMPLETED):
        api_error(409, "report_not_ready", "Reports are available after validation")
    if report_name not in {"accepted", "errors", "duplicates"}:
        api_error(404, "report_not_found", "Report not found")
    try:
        content = get_storage().get(f"reports/{batch.id}/{report_name}.csv")
    except FileNotFoundError:
        api_error(404, "report_not_found", "Report not found")
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{report_name}.csv"'},
    )
