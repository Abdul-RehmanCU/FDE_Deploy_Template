import os
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlmodel import Session, select

from app import crud
from app.core.db import engine
from app.core.security import create_access_token
from app.main import app
from app.models import (
    AuditEvent,
    Contact,
    ImportBatch,
    Job,
    JobAttempt,
    JobOutbox,
    User,
    UserCreate,
    UserRole,
    ValidationRow,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Requires migrated PostgreSQL and Redis CI services",
)


def auth(user: User) -> dict[str, str]:
    token = create_access_token(
        user.id, timedelta(minutes=5), token_version=user.token_version
    )
    return {"Authorization": f"Bearer {token}"}


def seed_user(session: Session, email: str, role: UserRole) -> User:
    user, _ = crud.create_user(
        session=session,
        user_create=UserCreate(email=email, role=role),
        temporary_password="Strong-temporary-password-123",
    )
    user.must_change_password = False
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_admin_user_lifecycle_and_role_matrix() -> None:
    with Session(engine) as session:
        for model in (
            AuditEvent,
            JobOutbox,
            JobAttempt,
            Job,
            Contact,
            ValidationRow,
            ImportBatch,
            User,
        ):
            session.execute(delete(model))
        session.commit()
        admin = seed_user(session, "admin@example.com", UserRole.ADMIN)
        operator = seed_user(session, "operator-role@example.com", UserRole.OPERATOR)
        viewer = seed_user(session, "viewer-role@example.com", UserRole.VIEWER)
        admin_headers = auth(admin)
        operator_headers = auth(operator)
        viewer_headers = auth(viewer)

    with TestClient(app) as client:
        assert client.get("/api/v1/users", headers=operator_headers).status_code == 403
        assert client.get("/api/v1/users", headers=viewer_headers).status_code == 403
        created = client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "email": "managed@example.com",
                "full_name": "Managed User",
                "role": "operator",
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["temporary_password"]
        assert body["must_change_password"] is True
        managed_id = body["id"]

        reset = client.post(
            f"/api/v1/users/{managed_id}/temporary-password", headers=admin_headers
        )
        assert reset.status_code == 200
        assert set(reset.json()) == {"temporary_password"}

        with Session(engine) as session:
            managed = session.get(User, managed_id)
            assert managed
            blocked_headers = auth(managed)
        blocked = client.get("/api/v1/imports", headers=blocked_headers)
        assert blocked.status_code == 403
        assert blocked.json()["detail"]["code"] == "password_change_required"

        changed = client.patch(
            f"/api/v1/users/{operator.id}",
            headers=admin_headers,
            json={"role": "viewer"},
        )
        assert changed.status_code == 200
        invalidated = client.get("/api/v1/contacts", headers=operator_headers)
        assert invalidated.status_code == 401
        assert invalidated.json()["detail"]["code"] == "invalid_token"

        self_disable = client.patch(
            f"/api/v1/users/{admin.id}",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert self_disable.status_code == 409
        assert self_disable.json()["detail"]["code"] == "self_disable_forbidden"

    with Session(engine) as session:
        actions = {event.action for event in session.exec(select(AuditEvent)).all()}
        assert {
            "user.created",
            "user.temporary_password_issued",
            "user.updated",
        } <= actions
