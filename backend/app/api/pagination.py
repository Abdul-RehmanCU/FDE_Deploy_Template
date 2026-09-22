import base64
import json
import uuid
from datetime import datetime

from app.api.errors import api_error


def encode_cursor(created_at: datetime, object_id: uuid.UUID) -> str:
    raw = json.dumps([created_at.isoformat(), str(object_id)], separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = value + "=" * (-len(value) % 4)
        created_at, object_id = json.loads(base64.urlsafe_b64decode(padded).decode())
        return datetime.fromisoformat(created_at), uuid.UUID(object_id)
    except ValueError, TypeError, json.JSONDecodeError:
        api_error(400, "invalid_cursor", "The pagination cursor is invalid")
