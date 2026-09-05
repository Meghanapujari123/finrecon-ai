import uuid
from datetime import date, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy import Date as SADate
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    transaction_id: Mapped[str] = mapped_column(String(100), index=True)
    customer_id: Mapped[str] = mapped_column(String(100), index=True)
    invoice_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    transaction_date: Mapped[date] = mapped_column(SADate)
    status: Mapped[str] = mapped_column(String(30), default="SUCCESS")
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    record_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    ground_truth_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    bank_reference: Mapped[str] = mapped_column(String(100), index=True)
    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float)
    settlement_date: Mapped[date] = mapped_column(SADate)
    status: Mapped[str] = mapped_column(String(30), default="SETTLED")
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    record_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    ground_truth_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    ledger_reference: Mapped[str] = mapped_column(String(100), index=True)
    invoice_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(100), index=True)
    expected_amount: Mapped[float] = mapped_column(Float)
    recorded_amount: Mapped[float] = mapped_column(Float)
    tax_amount: Mapped[float] = mapped_column(Float, default=0.0)
    date: Mapped[date] = mapped_column(SADate)
    status: Mapped[str] = mapped_column(String(30), default="POSTED")
    record_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    ground_truth_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
