from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import ExceptionRecord
from app.services.audit_service import write_audit_log


class AlreadyResolvedError(Exception):
    pass


class ExceptionNotFoundError(Exception):
    pass


def apply_resolution(
    db: Session,
    exception_id: str,
    action: str,
    actor: str,
    reason: str | None = None,
) -> ExceptionRecord:
    """Idempotent resolution workflow. A resolution can never be applied
    twice: once an exception is RESOLVED, REJECTED, or UNRESOLVED, any
    further resolution attempt raises AlreadyResolvedError rather than
    silently reapplying (or worse, double-applying) a financial decision."""

    exc = db.query(ExceptionRecord).filter(ExceptionRecord.id == exception_id).first()
    if not exc:
        raise ExceptionNotFoundError(f"Exception {exception_id} not found")

    terminal_states = {"RESOLVED", "REJECTED"}
    if exc.status in terminal_states:
        raise AlreadyResolvedError(
            f"Exception {exception_id} is already {exc.status}; resolutions are idempotent and cannot be reapplied."
        )

    previous_state = {"status": exc.status, "resolved_at": str(exc.resolved_at) if exc.resolved_at else None}

    if action == "APPROVE":
        exc.status = "RESOLVED"
        exc.resolved_at = datetime.utcnow()
    elif action == "REJECT":
        exc.status = "REJECTED"
        exc.resolved_at = datetime.utcnow()
    elif action == "REQUEST_INVESTIGATION":
        exc.status = "UNDER_REVIEW"
    elif action == "MARK_UNRESOLVED":
        exc.status = "UNRESOLVED"
        exc.resolved_at = datetime.utcnow()
    else:
        raise ValueError(f"Unknown resolution action: {action}")

    db.add(exc)
    db.commit()
    db.refresh(exc)

    new_state = {"status": exc.status, "resolved_at": str(exc.resolved_at) if exc.resolved_at else None}
    write_audit_log(
        db, actor=actor, action=f"RESOLUTION_{action}", entity_type="ExceptionRecord",
        entity_id=exc.id, previous_state=previous_state, new_state=new_state, reason=reason,
    )
    return exc
