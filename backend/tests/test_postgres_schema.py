import os

import pytest
from sqlalchemy import text
from sqlmodel import Session

from app.core.db import engine

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
                text("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")
            ).scalars()
        )
    assert {"ck_user_role", "ck_import_batch_status", "ck_job_status"} <= constraints
    assert {
        "ix_contact_name_id",
        "ix_job_status_created",
        "ix_job_outbox_pending",
        "ix_validation_row_import_outcome_row",
    } <= indexes
