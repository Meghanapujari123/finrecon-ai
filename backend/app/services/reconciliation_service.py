from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.models import BankTransaction, ExceptionRecord, LedgerEntry, PaymentTransaction, ReconciliationResult
from app.models.base_types import MatchStatus
from app.reconciliation.matcher import ReconciliationEngine
from app.services.audit_service import write_audit_log


def run_reconciliation(db: Session, batch_id: str) -> dict:
    start = time.perf_counter()

    payments = db.query(PaymentTransaction).filter(PaymentTransaction.batch_id == batch_id).all()
    bank_txns = db.query(BankTransaction).filter(BankTransaction.batch_id == batch_id).all()
    ledger_entries = db.query(LedgerEntry).filter(LedgerEntry.batch_id == batch_id).all()

    if not payments:
        return {
            "batch_id": batch_id,
            "total_records": 0,
            "matched": 0,
            "unmatched": 0,
            "exceptions": 0,
            "match_rate": 0.0,
            "processing_time_ms": 0.0,
            "throughput_records_per_second": 0.0,
            "error": "No payment records found for this batch. Load or upload data first.",
        }

    # Clear any previous run for this batch so re-running is idempotent.
    db.query(ReconciliationResult).filter(ReconciliationResult.batch_id == batch_id).delete()
    db.query(ExceptionRecord).filter(ExceptionRecord.batch_id == batch_id).delete()
    db.commit()

    engine = ReconciliationEngine(payments, bank_txns, ledger_entries)
    outcomes, findings = engine.run()

    matched_count = 0
    for outcome in outcomes:
        result = ReconciliationResult(
            batch_id=batch_id,
            payment_id=outcome.payment_id,
            bank_transaction_id=outcome.bank_transaction_id,
            ledger_entry_id=outcome.ledger_entry_id,
            match_status=outcome.match_status,
            match_method=outcome.match_method,
            confidence=outcome.confidence,
            amount_difference=outcome.amount_difference,
            date_difference_days=outcome.date_difference_days,
            reason=outcome.reason,
            evidence=outcome.evidence,
        )
        db.add(result)
        if outcome.match_status == MatchStatus.MATCHED.value:
            matched_count += 1

    for finding in findings:
        db.add(ExceptionRecord(
            batch_id=batch_id,
            exception_type=finding.exception_type,
            severity=finding.severity,
            payment_id=finding.payment_id,
            bank_transaction_id=finding.bank_transaction_id,
            ledger_entry_id=finding.ledger_entry_id,
            amount_affected=finding.amount_affected,
            description=finding.description,
            status="OPEN",
        ))

    db.commit()

    elapsed_ms = (time.perf_counter() - start) * 1000
    total = len(outcomes)
    exceptions_count = len(findings)
    throughput = round(total / (elapsed_ms / 1000), 2) if elapsed_ms > 0 else float(total)

    write_audit_log(
        db, actor="system", action="RUN_RECONCILIATION", entity_type="Batch", entity_id=batch_id,
        new_state={"total": total, "matched": matched_count, "exceptions": exceptions_count},
        reason="Batch reconciliation executed",
    )

    return {
        "batch_id": batch_id,
        "total_records": total,
        "matched": matched_count,
        "unmatched": total - matched_count,
        "exceptions": exceptions_count,
        "match_rate": round(matched_count / total, 4) if total else 0.0,
        "processing_time_ms": round(elapsed_ms, 2),
        "throughput_records_per_second": throughput,
    }
