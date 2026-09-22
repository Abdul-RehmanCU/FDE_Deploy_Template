from typing import Any

from sqlalchemy import event
from sqlmodel import Session, create_engine

from app.core.config import settings

engine = create_engine(
    settings.sqlalchemy_database_url,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
)


@event.listens_for(engine, "connect")
def set_postgres_statement_timeout(dbapi_connection: Any, connection_record: object) -> None:
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
