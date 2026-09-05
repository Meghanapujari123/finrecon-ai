from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    label: str
    source: str
    seed: str | None = None
    created_at: datetime


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    batch_id: str
    transaction_id: str
    customer_id: str
    invoice_id: str | None
    amount: float
    currency: str
    transaction_date: date
    status: str
    payment_method: str | None


class BankTxnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    batch_id: str
    bank_reference: str
    transaction_id: str | None
    amount: float
    settlement_date: date
    status: str
    fees: float


class LedgerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    batch_id: str
    ledger_reference: str
    invoice_id: str | None
    customer_id: str
    expected_amount: float
    recorded_amount: float
    tax_amount: float
    date: date
    status: str


class ReconciliationRunOut(BaseModel):
    batch_id: str
    total_records: int
    matched: int
    unmatched: int
    exceptions: int
    match_rate: float
    processing_time_ms: float
    throughput_records_per_second: float
    error: str | None = None


class ReconciliationResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    batch_id: str
    payment_id: str | None
    bank_transaction_id: str | None
    ledger_entry_id: str | None
    match_status: str
    match_method: str
    confidence: float
    amount_difference: float
    date_difference_days: int
    reason: str


class ExceptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    batch_id: str
    exception_type: str
    severity: str
    payment_id: str | None
    bank_transaction_id: str | None
    ledger_entry_id: str | None
    amount_affected: float
    description: str
    status: str
    ai_analysis: dict | None
    ai_confidence: float | None
    ai_root_cause: str | None
    ai_status: str
    recommended_action: str | None
    risk_level: str | None
    requires_human_approval: bool
    created_at: datetime
    resolved_at: datetime | None


class ResolutionRequest(BaseModel):
    action: str  # APPROVE | REJECT | REQUEST_INVESTIGATION | MARK_UNRESOLVED
    actor: str = "operator"
    reason: str | None = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    actor: str
    action: str
    entity_type: str
    entity_id: str
    previous_state: dict | None
    new_state: dict | None
    reason: str | None
    timestamp: datetime


class QARequest(BaseModel):
    batch_id: str
    question: str


class QAResponse(BaseModel):
    answer: str
    supporting_records: list[str]
    calculated_metrics: dict
    confidence: str | None


class DashboardSummary(BaseModel):
    batch_id: str
    total_records: int
    matched: int
    exceptions: int
    match_rate: float
    accuracy: float | None
    throughput_records_per_second: float | None
    amount_affected: float
    human_review_required: int
