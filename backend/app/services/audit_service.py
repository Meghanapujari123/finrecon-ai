from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit_log(
    db: Session,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    previous_state: dict | None = None,
    new_state: dict | None = None,
    reason: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        previous_state=previous_state,
        new_state=new_state,
        reason=reason,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
