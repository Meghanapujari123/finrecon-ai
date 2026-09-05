from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BankTransaction, LedgerEntry, PaymentTransaction
from app.schemas.schemas import BankTxnOut, LedgerOut, PaymentOut

payments_router = APIRouter(prefix="/api/payments", tags=["payments"])
bank_router = APIRouter(prefix="/api/bank-transactions", tags=["bank"])
ledger_router = APIRouter(prefix="/api/ledger", tags=["ledger"])


@payments_router.get("", response_model=list[PaymentOut])
def list_payments(batch_id: str, db: Session = Depends(get_db)):
    return db.query(PaymentTransaction).filter(PaymentTransaction.batch_id == batch_id).all()


@bank_router.get("", response_model=list[BankTxnOut])
def list_bank_txns(batch_id: str, db: Session = Depends(get_db)):
    return db.query(BankTransaction).filter(BankTransaction.batch_id == batch_id).all()


@ledger_router.get("", response_model=list[LedgerOut])
def list_ledger(batch_id: str, db: Session = Depends(get_db)):
    return db.query(LedgerEntry).filter(LedgerEntry.batch_id == batch_id).all()
