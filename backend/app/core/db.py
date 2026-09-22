from typing import Any

from sqlalchemy import event, false, func, select, union_all
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, create_engine

from app import models as _models
from app.core.config import settings

engine = create_engine(
    settings.sqlalchemy_database_url,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
    connect_args=settings.database_connect_args,
)


@event.listens_for(engine, "connect")
def set_postgres_statement_timeout(
    dbapi_connection: Any, connection_record: object
) -> None:
    del connection_record
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(
            "SELECT set_config('statement_timeout', %s, false)",
            (str(settings.DB_STATEMENT_TIMEOUT_MS),),
        )
    finally:
        cursor.close()


def init_db(session: Session) -> None:
    """Verify connectivity; schema creation is exclusively managed by Alembic."""
    session.connection()


REQUIRED_APPLICATION_TABLES = tuple(
    _models.SQLModel.metadata.tables[name]
    for name in (
        "user",
        "import_batch",
        "validation_row",
        "contact",
        "job",
        "job_attempt",
        "job_outbox",
        "audit_event",
    )
)


def database_schema_is_compatible(session: Session) -> bool:
    """Return whether PostgreSQL can resolve every table and column this image uses.

    The zero-row statement checks the running application's schema contract without
    reading customer rows. Deliberately avoid comparing Alembic revision strings:
    a newer additive migration remains compatible with an older application during
    a rolling deployment.
    """
    checks = [
        select(func.jsonb_build_array(*table.c)).select_from(table).where(false())
        for table in REQUIRED_APPLICATION_TABLES
    ]
    try:
        session.execute(union_all(*checks)).all()
    except SQLAlchemyError:
        session.rollback()
        return False
    return True
