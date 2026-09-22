import uuid
from datetime import timedelta
from time import monotonic

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.observability import IMPORT_ROWS, JOB_DURATION, JOB_RUNS
from app.models import (
    Contact,
    ImportBatch,
    ImportStatus,
    Job,
    JobAttempt,
    JobKind,
    JobOutbox,
    JobStatus,
    RowOutcome,
    User,
    ValidationRow,
    utc_now,
)
from app.services.audit import record_audit
from app.services.csv_import import build_report, validate_rows
from app.services.storage import get_storage


def enqueue_job(
    session: Session,
    *,
    import_batch: ImportBatch,
    kind: JobKind,
    actor: User,
    traceparent: str | None = None,
) -> Job:
    job = Job(
        import_id=import_batch.id,
        kind=kind,
        created_by_id=actor.id,
        max_attempts=settings.CELERY_TASK_MAX_RETRIES + 1,
        traceparent=traceparent,
    )
    session.add(job)
    session.flush()
    session.add(
        JobOutbox(
            job_id=job.id,
            payload={
                "job_id": str(job.id),
                "kind": kind.value,
                **({"traceparent": traceparent} if traceparent else {}),
            },
        )
    )
    record_audit(
        session,
        actor_id=actor.id,
        action=f"job.{kind.value}.queued",
        resource_type="job",
        resource_id=job.id,
        metadata={"import_id": str(import_batch.id)},
    )
    return job


def _start_attempt(session: Session, job_id: uuid.UUID) -> tuple[Job, JobAttempt] | None:
    job = session.exec(select(Job).where(Job.id == job_id).with_for_update()).one_or_none()
    if not job or job.status in (JobStatus.SUCCEEDED, JobStatus.CANCELLED):
        return None
    if job.status == JobStatus.CANCEL_REQUESTED:
        job.status = JobStatus.CANCELLED
        job.finished_at = utc_now()
        session.add(job)
        batch = session.get(ImportBatch, job.import_id)
        if batch and batch.confirmation_started_at is None:
            batch.status = ImportStatus.CANCELLED
            batch.updated_at = utc_now()
            session.add(batch)
        session.commit()
        return None
    job.attempt_count += 1
    job.status = JobStatus.RUNNING
    job.started_at = job.started_at or utc_now()
    job.heartbeat_at = utc_now()
    attempt = JobAttempt(
        job_id=job.id,
        attempt_number=job.attempt_count,
        status=JobStatus.RUNNING,
    )
    session.add(job)
    session.add(attempt)
    session.commit()
    session.refresh(job)
    session.refresh(attempt)
    return job, attempt


def _fail_attempt(
    session: Session, job_id: uuid.UUID, attempt_id: uuid.UUID, *, code: str, message: str
) -> None:
    job = session.get(Job, job_id)
    attempt = session.get(JobAttempt, attempt_id)
    if job:
        job.status = JobStatus.FAILED
        job.error_code = code
        job.error_message = message
        job.finished_at = utc_now()
        session.add(job)
        batch = session.get(ImportBatch, job.import_id)
        if batch:
            batch.status = ImportStatus.FAILED
            batch.error_code = code
            batch.error_message = message
            batch.updated_at = utc_now()
            session.add(batch)
    if attempt:
        attempt.status = JobStatus.FAILED
        attempt.error_code = code
        attempt.error_message = message
        attempt.finished_at = utc_now()
        session.add(attempt)
    session.commit()


def _report_key(import_id: uuid.UUID, report: str) -> str:
    return f"reports/{import_id}/{report}.csv"


def run_validation(session: Session, job_id: uuid.UUID) -> None:
    started_at = monotonic()
    started = _start_attempt(session, job_id)
    if not started:
        return
    job, attempt = started
    try:
        batch = session.get(ImportBatch, job.import_id)
        if not batch or not batch.mapping:
            raise RuntimeError("Import mapping is missing")
        batch.status = ImportStatus.VALIDATING
        batch.updated_at = utc_now()
        session.add(batch)
        session.commit()

        content = get_storage().get(batch.upload_object_key)
        existing_emails = set(session.exec(select(Contact.normalized_email)).all())
        results = validate_rows(
            content,
            header=batch.header,
            mapping=batch.mapping,
            existing_emails=existing_emails,
        )

        session.exec(delete(ValidationRow).where(col(ValidationRow.import_id) == batch.id))
        session.add_all(
            [
                ValidationRow(
                    import_id=batch.id,
                    row_number=row.row_number,
                    outcome=row.outcome,
                    normalized_email=row.normalized_email,
                    clean_data=row.clean_data,
                    errors=row.errors,
                )
                for row in results
            ]
        )
        counts = dict.fromkeys(RowOutcome, 0)
        for row in results:
            counts[row.outcome] += 1
        batch.accepted_count = counts[RowOutcome.ACCEPTED]
        batch.rejected_count = counts[RowOutcome.INVALID]
        batch.duplicate_count = counts[RowOutcome.FILE_DUPLICATE]
        batch.existing_contact_count = counts[RowOutcome.EXISTING_CONTACT]
        batch.status = ImportStatus.VALIDATED
        batch.error_code = None
        batch.error_message = None
        batch.updated_at = utc_now()
        job.status = JobStatus.SUCCEEDED
        job.finished_at = utc_now()
        attempt.status = JobStatus.SUCCEEDED
        attempt.finished_at = utc_now()
        session.add_all([batch, job, attempt])

        storage = get_storage()
        storage.put(
            _report_key(batch.id, "accepted"),
            build_report([row for row in results if row.outcome == RowOutcome.ACCEPTED]),
            "text/csv; charset=utf-8",
        )
        storage.put(
            _report_key(batch.id, "errors"),
            build_report([row for row in results if row.outcome == RowOutcome.INVALID]),
            "text/csv; charset=utf-8",
        )
        storage.put(
            _report_key(batch.id, "duplicates"),
            build_report(
                [
                    row
                    for row in results
                    if row.outcome
                    in (RowOutcome.FILE_DUPLICATE, RowOutcome.EXISTING_CONTACT)
                ]
            ),
            "text/csv; charset=utf-8",
        )
        session.commit()
        for outcome, count in counts.items():
            IMPORT_ROWS.labels(outcome=outcome.value).inc(count)
        JOB_RUNS.labels(kind=JobKind.VALIDATE.value, outcome="succeeded").inc()
    except Exception:
        session.rollback()
        _fail_attempt(
            session,
            job.id,
            attempt.id,
            code="validation_failed",
            message="Validation could not be completed",
        )
        JOB_RUNS.labels(kind=JobKind.VALIDATE.value, outcome="failed").inc()
        raise
    finally:
        JOB_DURATION.labels(kind=JobKind.VALIDATE.value).observe(
            monotonic() - started_at
        )


def run_confirmation(session: Session, job_id: uuid.UUID) -> None:
    started_at = monotonic()
    started = _start_attempt(session, job_id)
    if not started:
        return
    job, attempt = started
    try:
        batch = session.exec(
            select(ImportBatch)
            .where(ImportBatch.id == job.import_id)
            .with_for_update()
        ).one()
        if batch.status == ImportStatus.COMPLETED:
            job.status = JobStatus.SUCCEEDED
            job.finished_at = utc_now()
            attempt.status = JobStatus.SUCCEEDED
            attempt.finished_at = utc_now()
            session.add_all([job, attempt])
            session.commit()
            return
        if batch.status != ImportStatus.VALIDATED:
            raise RuntimeError("Import is not ready for confirmation")
        batch.status = ImportStatus.IMPORTING
        batch.confirmation_started_at = utc_now()

        rows = session.exec(
            select(ValidationRow).where(
                ValidationRow.import_id == batch.id,
                ValidationRow.outcome == RowOutcome.ACCEPTED,
            )
        ).all()
        values = [
            {
                "id": uuid.uuid4(),
                "email": row.clean_data["email"],
                "normalized_email": row.normalized_email,
                "first_name": row.clean_data["first_name"],
                "last_name": row.clean_data["last_name"],
                "company": row.clean_data.get("company"),
                "country_code": row.clean_data.get("country_code"),
                "external_id": row.clean_data.get("external_id"),
                "source_import_id": batch.id,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            }
            for row in rows
            if row.clean_data and row.normalized_email
        ]
        inserted = 0
        if values:
            result = session.execute(
                pg_insert(Contact)
                .values(values)
                .on_conflict_do_nothing(index_elements=["normalized_email"])
                .returning(col(Contact.id))
            )
            inserted = len(result.scalars().all())
        batch.inserted_count = inserted
        batch.skipped_count = len(values) - inserted
        batch.status = ImportStatus.COMPLETED
        batch.updated_at = utc_now()
        job.status = JobStatus.SUCCEEDED
        job.finished_at = utc_now()
        attempt.status = JobStatus.SUCCEEDED
        attempt.finished_at = utc_now()
        session.add_all([batch, job, attempt])
        record_audit(
            session,
            actor_id=job.created_by_id,
            action="import.confirmed",
            resource_type="import",
            resource_id=batch.id,
            metadata={"inserted_count": inserted, "skipped_count": batch.skipped_count},
        )
        session.commit()
        JOB_RUNS.labels(kind=JobKind.CONFIRM.value, outcome="succeeded").inc()
    except Exception:
        session.rollback()
        _fail_attempt(
            session,
            job.id,
            attempt.id,
            code="import_failed",
            message="The import transaction could not be completed",
        )
        JOB_RUNS.labels(kind=JobKind.CONFIRM.value, outcome="failed").inc()
        raise
    finally:
        JOB_DURATION.labels(kind=JobKind.CONFIRM.value).observe(
            monotonic() - started_at
        )


def reconcile_stalled_jobs(session: Session) -> int:
    cutoff = utc_now() - timedelta(seconds=settings.JOB_STALE_SECONDS)
    jobs = session.exec(
        select(Job).where(
            Job.status == JobStatus.RUNNING,
            col(Job.heartbeat_at).is_not(None),
            col(Job.heartbeat_at) < cutoff,
        )
    ).all()
    for job in jobs:
        job.status = JobStatus.QUEUED
        job.error_code = "worker_stalled"
        job.error_message = "The worker stopped; the job was queued again"
        session.add(job)
        existing = session.exec(select(JobOutbox).where(JobOutbox.job_id == job.id)).first()
        if existing:
            existing.published_at = None
            existing.available_at = utc_now()
            session.add(existing)
        else:
            session.add(
                JobOutbox(
                    job_id=job.id,
                    payload={
                        "job_id": str(job.id),
                        "kind": job.kind.value,
                        **({"traceparent": job.traceparent} if job.traceparent else {}),
                    },
                )
            )
    session.commit()
    return len(jobs)
