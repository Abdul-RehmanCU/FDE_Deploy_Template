import secrets
import uuid

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models import User, UserCreate, UserUpdate, utc_now


def generate_temporary_password() -> str:
    return secrets.token_urlsafe(18)


def create_user(
    *, session: Session, user_create: UserCreate, temporary_password: str | None = None
) -> tuple[User, str]:
    password = temporary_password or generate_temporary_password()
    db_obj = User.model_validate(
        user_create,
        update={"hashed_password": get_password_hash(password), "must_change_password": True},
    )
    session.add(db_obj)
    session.flush()
    session.refresh(db_obj)
    return db_obj, password


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> User:
    changes = user_in.model_dump(exclude_unset=True)
    if changes:
        db_user.sqlmodel_update(changes)
        db_user.updated_at = utc_now()
        if "is_active" in changes or "role" in changes:
            db_user.token_version += 1
        session.add(db_user)
        session.flush()
        session.refresh(db_user)
    return db_user


def set_temporary_password(*, session: Session, db_user: User) -> str:
    password = generate_temporary_password()
    db_user.hashed_password = get_password_hash(password)
    db_user.must_change_password = True
    db_user.token_version += 1
    db_user.updated_at = utc_now()
    session.add(db_user)
    session.flush()
    return password


def get_user_by_email(*, session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == email.strip().lower())).first()


DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_hash:
        db_user.hashed_password = updated_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user


def get_user(*, session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)
