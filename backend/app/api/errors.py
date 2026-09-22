from typing import NoReturn

from fastapi import HTTPException


def api_error(
    status_code: int,
    code: str,
    message: str,
    fields: dict[str, str] | None = None,
) -> NoReturn:
    detail: dict[str, object] = {"code": code, "message": message}
    if fields:
        detail["fields"] = fields
    raise HTTPException(status_code=status_code, detail=detail)
