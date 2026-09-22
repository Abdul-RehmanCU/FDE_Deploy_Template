import uuid
from typing import Any

from sqlmodel import Session

from app.models import AuditEvent


def record_audit(
    session: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=metadata or {},
        request_id=request_id,
    )
    session.add(event)
    return event
