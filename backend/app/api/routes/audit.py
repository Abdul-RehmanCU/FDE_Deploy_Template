from fastapi import APIRouter, Query
from sqlalchemy import tuple_
from sqlmodel import col, select

from app.api.deps import AdminUser, SessionDep
from app.api.pagination import decode_cursor, encode_cursor
from app.models import AuditEvent, AuditEventPage, AuditEventPublic

router = APIRouter(prefix="/audit-events", tags=["audit"])


@router.get("", response_model=AuditEventPage)
def list_audit_events(
    session: SessionDep,
    current_admin: AdminUser,
    action: str | None = Query(default=None, max_length=100),
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> AuditEventPage:
    del current_admin
    statement = select(AuditEvent).order_by(
        col(AuditEvent.created_at).desc(), col(AuditEvent.id).desc()
    )
    if action:
        statement = statement.where(AuditEvent.action == action)
    if cursor:
        created_at, event_id = decode_cursor(cursor)
        statement = statement.where(
            tuple_(col(AuditEvent.created_at), col(AuditEvent.id))
            < (created_at, event_id)
        )
    rows = list(session.exec(statement.limit(limit + 1)).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more else None
    return AuditEventPage(
        data=[AuditEventPublic.model_validate(row) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )
