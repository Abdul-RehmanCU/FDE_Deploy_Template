from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

from app import crud
from app.api.deps import SessionDep
from app.api.errors import api_error
from app.core import security
from app.core.config import settings
from app.models import Token
from app.services.login_rate_limit import enforce_login_rate_limit

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
def login_access_token(
    request: Request,
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    client_ip = request.client.host if request.client else "unknown"
    enforce_login_rate_limit(client_ip, form_data.username)
    user = crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user or not user.is_active:
        api_error(400, "invalid_credentials", "Incorrect email or password")
    return Token(
        access_token=security.create_access_token(
            user.id,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            token_version=user.token_version,
        ),
        must_change_password=user.must_change_password,
    )
