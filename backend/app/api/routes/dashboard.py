from fastapi import APIRouter
from sqlalchemy import func
from sqlmodel import select

from app.api.deps import ReadyUser, SessionDep
from app.models import Contact, DashboardPublic, ImportBatch, Job

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardPublic)
def dashboard(session: SessionDep, current_user: ReadyUser) -> DashboardPublic:
    del current_user
    imports_total = session.exec(select(func.count()).select_from(ImportBatch)).one()
    contacts_total = session.exec(select(func.count()).select_from(Contact)).one()
    totals = session.exec(
        select(
            func.coalesce(func.sum(ImportBatch.accepted_count), 0),
            func.coalesce(func.sum(ImportBatch.rejected_count), 0),
            func.coalesce(func.sum(ImportBatch.duplicate_count), 0),
        )
    ).one()
    job_rows = session.exec(select(Job.status, func.count()).group_by(Job.status)).all()
    return DashboardPublic(
        imports_total=imports_total,
        contacts_total=contacts_total,
        accepted_rows_total=totals[0],
        rejected_rows_total=totals[1],
        duplicate_rows_total=totals[2],
        jobs_by_status={str(status): count for status, count in job_rows},
    )
