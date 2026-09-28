from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record_audit(
    db: Session,
    *,
    action: str,
    entity: str,
    entity_id: str | None = None,
    user_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    details: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        audit_metadata=metadata,
        details=details,
    )
    db.add(entry)
    db.flush()
    return entry
