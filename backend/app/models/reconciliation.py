import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    payment_id: Mapped[str | None] = mapped_column(ForeignKey("payment_transactions.id"), nullable=True)
    bank_transaction_id: Mapped[str | None] = mapped_column(ForeignKey("bank_transactions.id"), nullable=True)
    ledger_entry_id: Mapped[str | None] = mapped_column(ForeignKey("ledger_entries.id"), nullable=True)
    match_status: Mapped[str] = mapped_column(String(20))  # MatchStatus
    match_method: Mapped[str] = mapped_column(String(50))  # MatchMethod
    confidence: Mapped[float] = mapped_column(Float)
    amount_difference: Mapped[float] = mapped_column(Float, default=0.0)
    date_difference_days: Mapped[int] = mapped_column(default=0)
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExceptionRecord(Base):
    __tablename__ = "exception_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    reconciliation_result_id: Mapped[str | None] = mapped_column(
        ForeignKey("reconciliation_results.id"), nullable=True
    )
    exception_type: Mapped[str] = mapped_column(String(50))  # ExceptionType
    severity: Mapped[str] = mapped_column(String(10))  # Severity
    payment_id: Mapped[str | None] = mapped_column(ForeignKey("payment_transactions.id"), nullable=True)
    bank_transaction_id: Mapped[str | None] = mapped_column(ForeignKey("bank_transactions.id"), nullable=True)
    ledger_entry_id: Mapped[str | None] = mapped_column(ForeignKey("ledger_entries.id"), nullable=True)
    amount_affected: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")  # ExceptionStatus

    # AI investigation output (populated by the agent; null until analyzed)
    ai_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_root_cause: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_status: Mapped[str] = mapped_column(String(30), default="NOT_ANALYZED")
    # NOT_ANALYZED | ANALYZED | UNAVAILABLE | FAILED

    recommended_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(10), nullable=True)  # RiskLevel
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=True)

    ground_truth_label: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
