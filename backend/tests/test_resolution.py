import pytest

from app.services.batch_service import create_demo_batch
from app.services.reconciliation_service import run_reconciliation
from app.services.resolution_service import (
    AlreadyResolvedError,
    ExceptionNotFoundError,
    apply_resolution,
)
from app.models import ExceptionRecord


def _first_exception(db_session, batch_id):
    return db_session.query(ExceptionRecord).filter(ExceptionRecord.batch_id == batch_id).first()


def test_resolution_cannot_be_applied_twice(db_session):
    batch = create_demo_batch(db_session, n_base=60, seed=3)
    run_reconciliation(db_session, batch.id)
    exc = _first_exception(db_session, batch.id)

    apply_resolution(db_session, exc.id, action="APPROVE", actor="tester")
    with pytest.raises(AlreadyResolvedError):
        apply_resolution(db_session, exc.id, action="APPROVE", actor="tester")


def test_resolution_on_unknown_exception_raises(db_session):
    with pytest.raises(ExceptionNotFoundError):
        apply_resolution(db_session, "does-not-exist", action="APPROVE", actor="tester")


def test_resolution_creates_audit_log(db_session):
    from app.models import AuditLog

    batch = create_demo_batch(db_session, n_base=60, seed=5)
    run_reconciliation(db_session, batch.id)
    exc = _first_exception(db_session, batch.id)

    apply_resolution(db_session, exc.id, action="REJECT", actor="tester", reason="not a real issue")
    logs = db_session.query(AuditLog).filter(AuditLog.entity_id == exc.id).all()
    assert len(logs) == 1
    assert logs[0].action == "RESOLUTION_REJECT"
