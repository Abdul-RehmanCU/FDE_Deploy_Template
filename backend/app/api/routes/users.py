import uuid

from fastapi import APIRouter, Query
from sqlalchemy import tuple_
from sqlmodel import col, select

from app import crud
from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.api.errors import api_error
from app.api.pagination import decode_cursor, encode_cursor
from app.core.security import get_password_hash, verify_password
from app.models import (
    Message,
    PasswordChange,
    TemporaryPassword,
    User,
    UserCreate,
    UserCreated,
    UserPage,
    UserPublic,
    UserUpdate,
    utc_now,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserPage)
def list_users(
    session: SessionDep,
    current_admin: AdminUser,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> UserPage:
    del current_admin
    statement = select(User).order_by(col(User.created_at).desc(), col(User.id).desc())
    if cursor:
        created_at, user_id = decode_cursor(cursor)
        statement = statement.where(
            tuple_(col(User.created_at), col(User.id)) < (created_at, user_id)
        )
    rows = list(session.exec(statement.limit(limit + 1)).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more else None
    return UserPage(data=[UserPublic.model_validate(row) for row in rows], next_cursor=next_cursor, has_more=has_more)


@router.post("", response_model=UserCreated, status_code=201)
def create_user(
    *, session: SessionDep, current_admin: AdminUser, user_in: UserCreate
) -> UserCreated:
    if crud.get_user_by_email(session=session, email=user_in.email):
        api_error(409, "email_conflict", "A user with this email already exists")
    normalized = user_in.model_copy(update={"email": str(user_in.email).strip().lower()})
    user, password = crud.create_user(session=session, user_create=normalized)
    record_audit(
        session,
        actor_id=current_admin.id,
        action="user.created",
        resource_type="user",
        resource_id=user.id,
        metadata={"role": user.role.value},
    )
    session.commit()
    return UserCreated(
        **UserPublic.model_validate(user).model_dump(), temporary_password=password
    )


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> User:
    return current_user


@router.post("/me/password", response_model=Message)
def change_password(
    *, session: SessionDep, body: PasswordChange, current_user: CurrentUser
) -> Message:
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        api_error(400, "incorrect_password", "The current password is incorrect")
    if body.current_password == body.new_password:
        api_error(400, "password_reused", "Choose a different password")
    current_user.hashed_password = get_password_hash(body.new_password)
    current_user.must_change_password = False
    current_user.token_version += 1
    current_user.updated_at = utc_now()
    session.add(current_user)
    record_audit(
        session,
        actor_id=current_user.id,
        action="user.password_changed",
        resource_type="user",
        resource_id=current_user.id,
    )
    session.commit()
    return Message(message="Password updated; sign in again")


@router.get("/{user_id}", response_model=UserPublic)
def read_user(user_id: uuid.UUID, session: SessionDep, current_admin: AdminUser) -> User:
    del current_admin
    user = crud.get_user(session=session, user_id=user_id)
    if not user:
        api_error(404, "user_not_found", "User not found")
    return user


@router.patch("/{user_id}", response_model=UserPublic)
def update_user(
    *,
    session: SessionDep,
    current_admin: AdminUser,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> User:
    user = crud.get_user(session=session, user_id=user_id)
    if not user:
        api_error(404, "user_not_found", "User not found")
    if user_in.email:
        existing = crud.get_user_by_email(session=session, email=user_in.email)
        if existing and existing.id != user_id:
            api_error(409, "email_conflict", "A user with this email already exists")
        user_in = user_in.model_copy(
            update={"email": str(user_in.email).strip().lower()}
        )
    if user.id == current_admin.id and user_in.is_active is False:
        api_error(409, "self_disable_forbidden", "Administrators cannot disable themselves")
    user = crud.update_user(session=session, db_user=user, user_in=user_in)
    record_audit(
        session,
        actor_id=current_admin.id,
        action="user.updated",
        resource_type="user",
        resource_id=user.id,
        metadata={"role": user.role.value, "is_active": user.is_active},
    )
    session.commit()
    return user


@router.post("/{user_id}/temporary-password", response_model=TemporaryPassword)
def issue_temporary_password(
    user_id: uuid.UUID, session: SessionDep, current_admin: AdminUser
) -> TemporaryPassword:
    user = crud.get_user(session=session, user_id=user_id)
    if not user:
        api_error(404, "user_not_found", "User not found")
    password = crud.set_temporary_password(session=session, db_user=user)
    record_audit(
        session,
        actor_id=current_admin.id,
        action="user.temporary_password_issued",
        resource_type="user",
        resource_id=user.id,
    )
    session.commit()
    return TemporaryPassword(temporary_password=password)
