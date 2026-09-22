from app.core.config import settings
from app.core.db import set_postgres_statement_timeout


class Cursor:
    def __init__(self) -> None:
        self.statement: str | None = None
        self.params: tuple[str] | None = None
        self.closed = False

    def execute(self, statement: str, params: tuple[str]) -> None:
        self.statement = statement
        self.params = params

    def close(self) -> None:
        self.closed = True


class Connection:
    def __init__(self, cursor: Cursor) -> None:
        self.test_cursor = cursor

    def cursor(self) -> Cursor:
        return self.test_cursor


def test_statement_timeout_uses_parameterized_set_config() -> None:
    cursor = Cursor()
    set_postgres_statement_timeout(Connection(cursor), object())
    assert cursor.statement == "SELECT set_config('statement_timeout', %s, false)"
    assert cursor.params == (str(settings.DB_STATEMENT_TIMEOUT_MS),)
    assert cursor.closed is True
