import os
import uuid
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
    JobStatus,
    User,
    UserCreate,
    UserRole,
    ValidationRow,
)
from app.services.jobs import run_confirmation, run_validation

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Requires migrated PostgreSQL and Redis CI services",
)


def headers_for(user: User) -> dict[str, str]:
    token = create_access_token(
        user.id, timedelta(minutes=5), token_version=user.token_version
    )
    return {"Authorization": f"Bearer {token}"}


def clear_database(session: Session) -> None:
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


def create_ready_user(
    session: Session, email: str, role: UserRole, password: str
) -> User:
    user, _ = crud.create_user(
        session=session,
        user_create=UserCreate(email=email, full_name=role.value.title(), role=role),
        temporary_password=password,
    )
    user.must_change_password = False
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def upload_and_map(client: TestClient, headers: dict[str, str], content: bytes) -> str:
    upload = client.post(
        "/api/v1/imports",
        headers=headers,
        files={"file": ("contacts.csv", content, "text/csv")},
    )
    assert upload.status_code == 201, upload.text
    import_id = upload.json()["id"]
    mapped = client.put(
        f"/api/v1/imports/{import_id}/mapping",
        headers=headers,
        json={
            "mapping": {
                "email": "Email",
                "first_name": "First",
                "last_name": "Last",
                "company": "Company",
                "country_code": "Country",
                "external_id": "External",
            }
        },
    )
    assert mapped.status_code == 200, mapped.text
    return import_id


def test_real_import_flow_is_authorized_atomic_and_replay_safe() -> None:
    with Session(engine) as session:
        clear_database(session)
        operator = create_ready_user(
            session, "operator@example.com", UserRole.OPERATOR, "A-strong-password-123"
        )
        viewer = create_ready_user(
            session, "viewer@example.com", UserRole.VIEWER, "A-strong-password-456"
        )
        operator_headers = headers_for(operator)
        viewer_headers = headers_for(viewer)

    content = (
        b"Email,First,Last,Company,Country,External\n"
        b"one@example.com,One,Person,=1+1,ca,+10\n"
        b"bad-email,Bad,Email,,CA,11\n"
        b"one@example.com,Copy,Person,,CA,12\n"
        b"two@example.com,Two,Person,,US,13\n"
    )
    with TestClient(app) as client:
        import_id = upload_and_map(client, operator_headers, content)
        forbidden_upload = client.post(
            "/api/v1/imports",
            headers=viewer_headers,
            files={"file": ("contacts.csv", content, "text/csv")},
        )
        assert forbidden_upload.status_code == 403
        assert forbidden_upload.json()["detail"]["code"] == "forbidden"

        queued = client.post(
            f"/api/v1/imports/{import_id}/validate", headers=operator_headers
        )
        assert queued.status_code == 202, queued.text
        validation_job_id = uuid.UUID(queued.json()["job_id"])
        with Session(engine) as session:
            run_validation(session, validation_job_id)

        result = client.get(f"/api/v1/imports/{import_id}", headers=viewer_headers)
        assert result.status_code == 200
        expected_counts = {
            "accepted_count": 2,
            "rejected_count": 1,
            "duplicate_count": 1,
            "existing_contact_count": 0,
        }
        for field, value in expected_counts.items():
            assert result.json()[field] == value
        viewer_report = client.get(
            f"/api/v1/imports/{import_id}/reports/accepted", headers=viewer_headers
        )
        assert viewer_report.status_code == 403
        report = client.get(
            f"/api/v1/imports/{import_id}/reports/accepted",
            headers=operator_headers,
        )
        assert report.status_code == 200
        assert b"'=1+1" in report.content
        assert b"'+10" in report.content

        idempotency_headers = {**operator_headers, "Idempotency-Key": "confirm-12345678"}
        confirmation = client.post(
            f"/api/v1/imports/{import_id}/confirm", headers=idempotency_headers
        )
        assert confirmation.status_code == 202, confirmation.text
        confirmation_job_id = uuid.UUID(confirmation.json()["job_id"])
        duplicate_click = client.post(
            f"/api/v1/imports/{import_id}/confirm", headers=idempotency_headers
        )
        assert duplicate_click.status_code == 202
        assert duplicate_click.json()["job_id"] == str(confirmation_job_id)
        with Session(engine) as session:
            run_confirmation(session, confirmation_job_id)
            run_confirmation(session, confirmation_job_id)
            assert len(session.exec(select(Contact)).all()) == 2
            job = session.get(Job, confirmation_job_id)
            assert job and job.status == JobStatus.SUCCEEDED

        conflict = client.post(
            f"/api/v1/imports/{import_id}/confirm",
            headers={**operator_headers, "Idempotency-Key": "different-123456"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "idempotency_conflict"


def test_cancelled_queued_validation_is_harmless() -> None:
    with Session(engine) as session:
        clear_database(session)
        operator = create_ready_user(
            session, "cancel@example.com", UserRole.OPERATOR, "A-strong-password-789"
        )
        headers = headers_for(operator)
    content = (
        b"Email,First,Last,Company,Country,External\n"
        b"cancelled@example.com,Cancel,Me,,CA,C-1\n"
    )
    with TestClient(app) as client:
        import_id = upload_and_map(client, headers, content)
        queued = client.post(f"/api/v1/imports/{import_id}/validate", headers=headers)
        job_id = uuid.UUID(queued.json()["job_id"])
        cancelled = client.post(f"/api/v1/imports/{import_id}/cancel", headers=headers)
        assert cancelled.status_code == 200
        with Session(engine) as session:
            run_validation(session, job_id)
            assert session.exec(select(ValidationRow)).all() == []
            job = session.get(Job, job_id)
            assert job and job.status == JobStatus.CANCELLED
