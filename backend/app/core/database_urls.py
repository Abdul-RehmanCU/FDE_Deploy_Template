from sqlalchemy.engine import URL, make_url


def _postgres_url(value: str, *, database: str | None, driver: str) -> URL:
    parsed = make_url(value)
    if parsed.get_backend_name() not in ("postgres", "postgresql"):
        raise ValueError("database URL must use PostgreSQL")
    if database is not None:
        parsed = parsed.set(database=database)
    return parsed.set(drivername=driver)


def sqlalchemy_psycopg_url(value: str, *, database: str | None = None) -> str:
    """Return a SQLAlchemy URL that selects psycopg3 without exposing credentials."""
    return _postgres_url(
        value, database=database, driver="postgresql+psycopg"
    ).render_as_string(hide_password=False)


def libpq_url(value: str, *, database: str | None = None) -> str:
    """Return a libpq/psycopg URL, preserving encoded credentials and query options."""
    return _postgres_url(
        value, database=database, driver="postgresql"
    ).render_as_string(hide_password=False)
