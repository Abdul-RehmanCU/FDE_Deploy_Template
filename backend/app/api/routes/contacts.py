from fastapi import APIRouter, Query
from sqlalchemy import or_, tuple_
from sqlmodel import col, select

from app.api.deps import ReadyUser, SessionDep
from app.api.pagination import decode_cursor, encode_cursor
from app.models import Contact, ContactPage, ContactPublic

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=ContactPage)
def list_contacts(
    session: SessionDep,
    current_user: ReadyUser,
    q: str | None = Query(default=None, max_length=200),
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> ContactPage:
    del current_user
    statement = select(Contact).order_by(
        col(Contact.created_at).desc(), col(Contact.id).desc()
    )
    if q and (term := q.strip()):
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        statement = statement.where(
            or_(
                col(Contact.email).ilike(pattern, escape="\\"),
                col(Contact.first_name).ilike(pattern, escape="\\"),
                col(Contact.last_name).ilike(pattern, escape="\\"),
                col(Contact.company).ilike(pattern, escape="\\"),
            )
        )
    if cursor:
        created_at, contact_id = decode_cursor(cursor)
        statement = statement.where(
            tuple_(col(Contact.created_at), col(Contact.id)) < (created_at, contact_id)
        )
    rows = list(session.exec(statement.limit(limit + 1)).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more else None
    return ContactPage(
        data=[ContactPublic.model_validate(row) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )
