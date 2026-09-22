import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import delete
from sqlmodel import Session, select

from app.core.db import engine
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
    UserRole,
    ValidationRow,
    utc_now,
)
from app.outbox_publisher import publish_batch
from app.services.jobs import reconcile_stalled_jobs
from app.worker import celery_app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Requires migrated PostgreSQL and Redis CI services",
)


def seed_outbox(count: int) -> list[uuid.UUID]:
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
        user = User(
            email="outbox@example.com",
            role=UserRole.ADMIN,
            hashed_password="unused",
            must_change_password=False,
        )
        session.add(user)
        session.flush()
        batch = ImportBatch(
            original_filename="outbox.csv",
            upload_object_key=f"uploads/{uuid.uuid4()}/source.csv",
            header=["Email"],
            created_by_id=user.id,
        )
        session.add(batch)
        session.flush()
        ids: list[uuid.UUID] = []
        for _ in range(count):
            job = Job(
                import_id=batch.id,
                kind=JobKind.VALIDATE,
                created_by_id=user.id,
            )
            session.add(job)
            session.flush()
            ids.append(job.id)
            session.add(
                JobOutbox(
                    job_id=job.id,
                    payload={"job_id": str(job.id), "kind": JobKind.VALIDATE.value},
                    available_at=utc_now(),
                )
            )
        session.commit()
        return ids


def test_outbox_failure_is_retried_without_duplicate_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = seed_outbox(1)[0]
    attempts = 0

    def flaky_send_task(*args: object, **kwargs: object) -> None:
        nonlocal attempts
        del args, kwargs
        attempts += 1
        if attempts == 1:
            raise OSError("simulated broker interruption")

    monkeypatch.setattr(celery_app, "send_task", flaky_send_task)
    with pytest.raises(OSError, match="simulated broker interruption"):
        publish_batch()
    assert publish_batch() == 1
    with Session(engine) as session:
        row = session.exec(select(JobOutbox).where(JobOutbox.job_id == job_id)).one()
        assert row.published_at is not None
        assert row.publish_attempts == 2
        assert row.last_error is None
    assert attempts == 2


def test_skip_locked_prevents_concurrent_duplicate_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_ids = set(seed_outbox(2))
    published: list[uuid.UUID] = []
    first_call = threading.Event()

    def slow_send_task(*args: object, **kwargs: object) -> None:
        del args
        published.append(uuid.UUID(str(kwargs["task_id"])))
        if not first_call.is_set():
            first_call.set()
            time.sleep(0.25)

    monkeypatch.setattr(celery_app, "send_task", slow_send_task)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(publish_batch)
        assert first_call.wait(timeout=2)
        second = pool.submit(publish_batch)
        results = [first.result(timeout=5), second.result(timeout=5)]
    assert sorted(results) == [0, 2]
    assert set(published) == job_ids
    assert len(published) == 2


def test_reconciliation_recovers_lost_queued_and_running_deliveries() -> None:
    job_ids = seed_outbox(2)
    stale = utc_now() - timedelta(hours=1)
    with Session(engine) as session:
        queued = session.get(Job, job_ids[0])
        running = session.get(Job, job_ids[1])
        assert queued and running
        queued.created_at = stale
        running.status = JobStatus.RUNNING
        running.heartbeat_at = stale
        for job in (queued, running):
            outbox = session.exec(
                select(JobOutbox).where(JobOutbox.job_id == job.id)
            ).one()
            outbox.published_at = stale
            session.add(outbox)
            session.add(job)
        session.commit()
        assert reconcile_stalled_jobs(session) == 2
        for job_id in job_ids:
            job = session.get(Job, job_id)
            outbox = session.exec(
                select(JobOutbox).where(JobOutbox.job_id == job_id)
            ).one()
            assert job and job.status == JobStatus.QUEUED
            assert job.error_code == "delivery_reconciled"
            assert outbox.published_at is None
