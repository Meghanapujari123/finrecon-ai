from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.evaluation.evaluator import run_evaluation
from app.forecasting.forecast_service import generate_forecast
from app.models import AuditLog, ExceptionRecord, ReconciliationResult
from app.qa.qa_service import answer_question
from app.schemas.schemas import AuditLogOut, DashboardSummary, QARequest, QAResponse

health_router = APIRouter(prefix="/api/health", tags=["health"])
dashboard_router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
audit_router = APIRouter(prefix="/api/audit", tags=["audit"])
evaluation_router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])
forecast_router = APIRouter(prefix="/api/forecast", tags=["forecast"])
qa_router = APIRouter(prefix="/api/qa", tags=["qa"])


@health_router.get("")
def health():
    return {"status": "ok"}


@dashboard_router.get("/{batch_id}", response_model=DashboardSummary)
def dashboard_summary(batch_id: str, db: Session = Depends(get_db)):
    results = db.query(ReconciliationResult).filter(ReconciliationResult.batch_id == batch_id).all()
    exceptions = db.query(ExceptionRecord).filter(ExceptionRecord.batch_id == batch_id).all()
    if not results:
        raise HTTPException(404, "No reconciliation run found for this batch yet")

    total = len(results)
    matched = len([r for r in results if r.match_status == "MATCHED"])
    amount_affected = sum(e.amount_affected or 0.0 for e in exceptions)
    human_review = len([e for e in exceptions if e.requires_human_approval])

    ev = run_evaluation(db, batch_id)
    accuracy = ev.get("match_accuracy") if "error" not in ev else None

    # Throughput is a point-in-time measurement of a specific reconciliation
    # run, not a persisted property of a batch - we don't fabricate one here.
    # The Overview page shows the real value from the run that just executed.
    avg_throughput = None
    return DashboardSummary(
        batch_id=batch_id,
        total_records=total,
        matched=matched,
        exceptions=len(exceptions),
        match_rate=round(matched / total, 4) if total else 0.0,
        accuracy=accuracy,
        throughput_records_per_second=avg_throughput,
        amount_affected=round(amount_affected, 2),
        human_review_required=human_review,
    )


@audit_router.get("", response_model=list[AuditLogOut])
def list_audit_logs(entity_id: str | None = None, limit: int = 200, db: Session = Depends(get_db)):
    q = db.query(AuditLog)
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    return q.order_by(AuditLog.timestamp.desc()).limit(limit).all()


@evaluation_router.post("/run")
def run_eval(batch_id: str, db: Session = Depends(get_db)):
    result = run_evaluation(db, batch_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@forecast_router.get("/{batch_id}")
def forecast(batch_id: str, horizon_days: int = 7, db: Session = Depends(get_db)):
    result = generate_forecast(db, batch_id, horizon_days=horizon_days)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@qa_router.post("/ask", response_model=QAResponse)
def ask(body: QARequest, db: Session = Depends(get_db)):
    return answer_question(db, body.batch_id, body.question)
