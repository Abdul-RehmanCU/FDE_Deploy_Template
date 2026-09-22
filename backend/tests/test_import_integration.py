import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
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
    JobKind,
    JobOutbox,
    JobStatus,
    User,
    UserCreate,
    UserRole,
    ValidationRow,
)
from app.services import jobs as jobs_service
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
            run_validation(session, validation_job_id)
            assert len(session.exec(select(ValidationRow)).all()) == 4

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

        idempotency_headers = {
            **operator_headers,
            "Idempotency-Key": "confirm-12345678",
        }
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
        too_late = client.post(
            f"/api/v1/imports/{import_id}/cancel", headers=operator_headers
        )
        assert too_late.status_code == 409
        assert too_late.json()["detail"]["code"] == "import_commit_started"


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


def test_concurrent_confirmation_accepts_exactly_one_idempotency_key() -> None:
    with Session(engine) as session:
        clear_database(session)
        operator = create_ready_user(
            session,
            "concurrent@example.com",
            UserRole.OPERATOR,
            "A-strong-password-concurrent",
        )
        headers = headers_for(operator)
    content = (
        b"Email,First,Last,Company,Country,External\n"
        b"concurrent-contact@example.com,Con,Current,,CA,C-1\n"
    )
    with TestClient(app) as client:
        import_id = upload_and_map(client, headers, content)
        queued = client.post(f"/api/v1/imports/{import_id}/validate", headers=headers)
    with Session(engine) as session:
        run_validation(session, uuid.UUID(queued.json()["job_id"]))

    def confirm(key: str) -> tuple[int, dict[str, object]]:
        with TestClient(app) as threaded_client:
            response = threaded_client.post(
                f"/api/v1/imports/{import_id}/confirm",
                headers={**headers, "Idempotency-Key": key},
            )
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(confirm, ["concurrent-key-one", "concurrent-key-two"])
        )
    assert sorted(status for status, _ in responses) == [202, 409]
    conflict = next(body for status, body in responses if status == 409)
    assert conflict["detail"]["code"] == "idempotency_conflict"  # type: ignore[index]
    with Session(engine) as session:
        confirmation_jobs = session.exec(
            select(Job).where(
                Job.import_id == uuid.UUID(import_id), Job.kind == JobKind.CONFIRM
            )
        ).all()
        assert len(confirmation_jobs) == 1


def test_running_validation_cancels_cleanly_and_ignores_concurrent_redelivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(engine) as session:
        clear_database(session)
        operator = create_ready_user(
            session,
            "running-cancel@example.com",
            UserRole.OPERATOR,
            "A-strong-password-running-cancel",
        )
        headers = headers_for(operator)
    content = (
        b"Email,First,Last,Company,Country,External\n"
        b"running@example.com,Running,Cancel,,CA,C-1\n"
    )
    with TestClient(app) as client:
        import_id = upload_and_map(client, headers, content)
        queued = client.post(f"/api/v1/imports/{import_id}/validate", headers=headers)
        job_id = uuid.UUID(queued.json()["job_id"])

        entered_validation = threading.Event()
        release_validation = threading.Event()
        original_validate = jobs_service.validate_rows
        call_count = 0

        def blocked_validate(*args: object, **kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                entered_validation.set()
                assert release_validation.wait(timeout=5)
            return original_validate(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(jobs_service, "validate_rows", blocked_validate)

        def execute_job() -> None:
            with Session(engine) as worker_session:
                run_validation(worker_session, job_id)

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_delivery = pool.submit(execute_job)
            assert entered_validation.wait(timeout=5)
            replay_delivery = pool.submit(execute_job)
            replay_delivery.result(timeout=5)
            cancelled = client.post(
                f"/api/v1/imports/{import_id}/cancel", headers=headers
            )
            assert cancelled.status_code == 200
            release_validation.set()
            first_delivery.result(timeout=5)

    with Session(engine) as session:
        attempts = session.exec(
            select(JobAttempt).where(JobAttempt.job_id == job_id)
        ).all()
        assert len(attempts) == 1
        assert attempts[0].status == JobStatus.CANCELLED
        assert session.exec(select(ValidationRow)).all() == []
        job = session.get(Job, job_id)
        assert job and job.status == JobStatus.CANCELLED


def test_idempotency_key_is_scoped_to_the_import_resource() -> None:
    with Session(engine) as session:
        clear_database(session)
        operator = create_ready_user(
            session,
            "idempotency-scope@example.com",
            UserRole.OPERATOR,
            "A-strong-password-idempotency",
        )
        headers = headers_for(operator)
    content = (
        b"Email,First,Last,Company,Country,External\n"
        b"scope@example.com,Scope,One,,CA,S-1\n"
    )
    confirmation_jobs: list[str] = []
    with TestClient(app) as client:
        for _ in range(2):
            import_id = upload_and_map(client, headers, content)
            queued = client.post(
                f"/api/v1/imports/{import_id}/validate", headers=headers
            )
            with Session(engine) as session:
                run_validation(session, uuid.UUID(queued.json()["job_id"]))
            confirmed = client.post(
                f"/api/v1/imports/{import_id}/confirm",
                headers={**headers, "Idempotency-Key": "same-client-key"},
            )
            assert confirmed.status_code == 202, confirmed.text
            confirmation_jobs.append(confirmed.json()["job_id"])
    assert len(set(confirmation_jobs)) == 2


def test_cancellation_wins_before_confirmation_transaction_begins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(engine) as session:
        clear_database(session)
        operator = create_ready_user(
            session,
            "confirm-cancel@example.com",
            UserRole.OPERATOR,
            "A-strong-password-confirm-cancel",
        )
        headers = headers_for(operator)
    content = (
        b"Email,First,Last,Company,Country,External\n"
        b"never-insert@example.com,Never,Insert,,CA,C-1\n"
    )
    with TestClient(app) as client:
        import_id = upload_and_map(client, headers, content)
        validation = client.post(
            f"/api/v1/imports/{import_id}/validate", headers=headers
        )
        with Session(engine) as session:
            run_validation(session, uuid.UUID(validation.json()["job_id"]))
        confirmation = client.post(
            f"/api/v1/imports/{import_id}/confirm",
            headers={**headers, "Idempotency-Key": "cancel-before-commit"},
        )
        confirmation_job_id = uuid.UUID(confirmation.json()["job_id"])

        reached_final_check = threading.Event()
        release_final_check = threading.Event()
        original_check = jobs_service._cancel_if_requested

        def blocked_check(*args: object, **kwargs: object) -> bool:
            reached_final_check.set()
            assert release_final_check.wait(timeout=5)
            return original_check(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(jobs_service, "_cancel_if_requested", blocked_check)

        def execute_confirmation() -> None:
            with Session(engine) as worker_session:
                run_confirmation(worker_session, confirmation_job_id)

        with ThreadPoolExecutor(max_workers=1) as pool:
            worker = pool.submit(execute_confirmation)
            assert reached_final_check.wait(timeout=5)
            cancelled = client.post(
                f"/api/v1/imports/{import_id}/cancel", headers=headers
            )
            assert cancelled.status_code == 200, cancelled.text
            release_final_check.set()
            worker.result(timeout=5)

    with Session(engine) as session:
        assert session.exec(select(Contact)).all() == []
        job = session.get(Job, confirmation_job_id)
        batch = session.get(ImportBatch, uuid.UUID(import_id))
        assert job and job.status == JobStatus.CANCELLED
        assert batch and batch.status.value == "cancelled"
        assert batch.confirmation_started_at is None
