from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ReconciliationResult
from app.schemas.schemas import ReconciliationResultOut, ReconciliationRunOut
from app.services.reconciliation_service import run_reconciliation

router = APIRouter(prefix="/api/reconciliation", tags=["reconciliation"])


@router.post("/run/{batch_id}", response_model=ReconciliationRunOut)
def run(batch_id: str, db: Session = Depends(get_db)):
    return run_reconciliation(db, batch_id)


@router.get("/results/{batch_id}", response_model=list[ReconciliationResultOut])
def results(batch_id: str, db: Session = Depends(get_db)):
    return (
        db.query(ReconciliationResult)
        .filter(ReconciliationResult.batch_id == batch_id)
        .order_by(ReconciliationResult.created_at)
        .all()
    )
