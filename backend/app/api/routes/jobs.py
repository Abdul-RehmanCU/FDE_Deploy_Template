import base64
import uuid

from fastapi import APIRouter, Query
from sqlmodel import col, select

from app.api.deps import ReadyUser, SessionDep
from app.api.errors import api_error
from app.models import Job, JobAttempt, JobAttemptPage, JobAttemptPublic, JobPublic

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _encode_attempt_cursor(number: int) -> str:
    return base64.urlsafe_b64encode(str(number).encode()).decode().rstrip("=")


def _decode_attempt_cursor(value: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode())
    except (ValueError, UnicodeDecodeError):
        api_error(400, "invalid_cursor", "The pagination cursor is invalid")


@router.get("/{job_id}", response_model=JobPublic)
def get_job(job_id: uuid.UUID, session: SessionDep, current_user: ReadyUser) -> Job:
    del current_user
    job = session.get(Job, job_id)
    if not job:
        api_error(404, "job_not_found", "Job not found")
    return job


@router.get("/{job_id}/attempts", response_model=JobAttemptPage)
def list_attempts(
    job_id: uuid.UUID,
    session: SessionDep,
    current_user: ReadyUser,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> JobAttemptPage:
    del current_user
    if not session.get(Job, job_id):
        api_error(404, "job_not_found", "Job not found")
    statement = select(JobAttempt).where(JobAttempt.job_id == job_id)
    if cursor:
        statement = statement.where(
            JobAttempt.attempt_number > _decode_attempt_cursor(cursor)
        )
    rows = list(
        session.exec(statement.order_by(col(JobAttempt.attempt_number)).limit(limit + 1)).all()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    return JobAttemptPage(
        data=[JobAttemptPublic.model_validate(row) for row in rows],
        next_cursor=_encode_attempt_cursor(rows[-1].attempt_number) if has_more else None,
        has_more=has_more,
    )
