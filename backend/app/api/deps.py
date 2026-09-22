from collections.abc import Callable, Generator
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.api.errors import api_error
from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import TokenPayload, User, UserRole

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token", auto_error=False
)


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str | None, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    assert settings.SECRET_KEY
    if not token:
        api_error(401, "invalid_token", "Authentication is required")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        token_data = TokenPayload(**payload)
        user_id = token_data.sub
    except (InvalidTokenError, ValidationError):
        api_error(401, "invalid_token", "Authentication is required")
    if not user_id:
        api_error(401, "invalid_token", "Authentication is required")
    user = session.get(User, user_id)
    if not user or not user.is_active or user.token_version != token_data.ver:
        api_error(401, "invalid_token", "Authentication is required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_password_ready_user(current_user: CurrentUser) -> User:
    if current_user.must_change_password:
        api_error(403, "password_change_required", "Change your temporary password first")
    return current_user


ReadyUser = Annotated[User, Depends(get_password_ready_user)]


def require_roles(*roles: UserRole) -> Callable[[ReadyUser], User]:
    def dependency(current_user: ReadyUser) -> User:
        if current_user.role not in roles:
            api_error(403, "forbidden", "You do not have permission for this action")
        return current_user

    return dependency


AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
OperatorUser = Annotated[
    User, Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR))
]
