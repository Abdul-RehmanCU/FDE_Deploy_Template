import os

import pytest
from sqlalchemy import text
from sqlmodel import Session

from app.core.db import engine
from app.worker_metrics import DurableJobCollector

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Set RUN_POSTGRES_TESTS=1 after alembic upgrade head against PostgreSQL",
)


def test_postgres_constraints_and_indexes_exist() -> None:
    with Session(engine) as session:
        constraints = set(
            session.execute(
                text("SELECT conname FROM pg_constraint WHERE conname LIKE 'ck_%'")
            ).scalars()
        )
        indexes = set(
            session.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()"
                )
            ).scalars()
        )
    assert {"ck_user_role", "ck_import_batch_status", "ck_job_status"} <= constraints
    assert {
        "ix_contact_name_id",
        "ix_job_status_created",
        "ix_job_outbox_pending",
        "ix_validation_row_import_outcome_row",
    } <= indexes


def test_worker_metrics_are_collected_from_durable_postgres_state() -> None:
    families = list(DurableJobCollector().collect())
    names = {family.name for family in families}
    assert {
        "fde_worker_up",
        "fde_database_connections",
        "fde_jobs",
        "fde_oldest_queued_job_seconds",
        "fde_job_attempts",
        "fde_job_duration_seconds",
        "fde_import_rows",
        "fde_worker_metrics_collection_success",
    } <= names
    health = next(
        family
        for family in families
        if family.name == "fde_worker_metrics_collection_success"
    )
    assert health.samples[0].value == 1
    connections = next(
        family for family in families if family.name == "fde_database_connections"
    )
    assert all(sample.value >= 0 for sample in connections.samples)
    overflow = next(
        sample
        for sample in connections.samples
        if sample.labels.get("state") == "overflow"
    )
    assert overflow.value == 0
