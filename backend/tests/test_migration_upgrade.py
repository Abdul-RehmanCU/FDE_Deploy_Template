import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import settings

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Requires PostgreSQL with disposable-database privileges",
)

BACKEND_DIR = Path(__file__).parents[1]


def database_url(name: str) -> str:
    return (
        make_url(settings.sqlalchemy_database_url)
        .set(database=name)
        .render_as_string(hide_password=False)
    )


def run_migration(target_url: str, revision: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = target_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=BACKEND_DIR,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_upgrade_preserves_existing_users_items_and_legacy_reads() -> None:
    target_name = f"fde_migration_{uuid.uuid4().hex}"
    assert target_name.startswith("fde_migration_")
    admin_url = database_url("postgres")
    target_url = database_url(target_name)
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_name)))
    try:
        run_migration(target_url, "fe56fa70289e")
        user_id = uuid.uuid4()
        item_id = uuid.uuid4()
        with psycopg.connect(target_url) as connection:
            connection.execute(
                'INSERT INTO "user" '
                "(id, email, hashed_password, is_active, is_superuser, full_name) "
                "VALUES (%s, %s, %s, true, true, %s)",
                (user_id, "legacy-admin@example.com", "legacy-hash", "Legacy Admin"),
            )
            connection.execute(
                "INSERT INTO item (id, title, description, owner_id) "
                "VALUES (%s, %s, %s, %s)",
                (item_id, "Legacy item", "Must survive additive upgrade", user_id),
            )
            connection.commit()

        run_migration(target_url, "head")
        with psycopg.connect(target_url) as connection:
            user = connection.execute(
                'SELECT email, is_superuser, role FROM "user" WHERE id = %s',
                (user_id,),
            ).fetchone()
            item = connection.execute(
                "SELECT title, owner_id FROM item WHERE id = %s", (item_id,)
            ).fetchone()
            assert user == ("legacy-admin@example.com", True, "admin")
            assert item == ("Legacy item", user_id)
            assert connection.execute(
                "SELECT to_regclass('public.import_batch') IS NOT NULL"
            ).fetchone() == (True,)
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (target_name,),
            )
            admin.execute(
                sql.SQL("DROP DATABASE {}").format(sql.Identifier(target_name))
            )
