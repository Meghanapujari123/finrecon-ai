from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Batch
from app.schemas.schemas import BatchOut
from app.services.batch_service import create_batch_from_rows, create_demo_batch

router = APIRouter(prefix="/api/batches", tags=["batches"])
settings = get_settings()


@router.get("", response_model=list[BatchOut])
def list_batches(db: Session = Depends(get_db)):
    return db.query(Batch).order_by(Batch.created_at.desc()).all()


@router.post("/demo", response_model=BatchOut)
def load_demo_batch(n_base: int = 150, seed: int = 42, db: Session = Depends(get_db)):
    if n_base < 50:
        raise HTTPException(400, "Hackathon requirement is a 50+ record batch; n_base must be >= 50")
    batch = create_demo_batch(db, n_base=n_base, seed=seed)
    return batch


def _parse_date(value: str):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {value}")


@router.post("/upload", response_model=BatchOut)
async def upload_csvs(
    label: str,
    payments_csv: UploadFile | None = File(None),
    bank_csv: UploadFile | None = File(None),
    ledger_csv: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    """Accepts up to 3 CSV files (payments, bank, ledger). Required columns:
    payments: transaction_id, customer_id, invoice_id, amount, transaction_date
    bank: bank_reference, transaction_id, amount, settlement_date, fees
    ledger: ledger_reference, invoice_id, customer_id, expected_amount, recorded_amount, tax_amount, date
    """
    if not any([payments_csv, bank_csv, ledger_csv]):
        raise HTTPException(400, "At least one of payments_csv, bank_csv, ledger_csv is required")

    async def _read_rows(upload: UploadFile | None, required_cols: list[str]) -> list[dict]:
        if upload is None:
            return []
        raw = await upload.read()
        if len(raw) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise HTTPException(400, f"{upload.filename} exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")
        text = raw.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise HTTPException(400, f"{upload.filename} has no header row")
        missing = [c for c in required_cols if c not in reader.fieldnames]
        if missing:
            raise HTTPException(400, f"{upload.filename} missing required columns: {missing}")
        rows = list(reader)
        if len(rows) > settings.MAX_UPLOAD_ROWS:
            raise HTTPException(400, f"{upload.filename} exceeds {settings.MAX_UPLOAD_ROWS} row limit")
        return rows

    try:
        payment_rows = await _read_rows(
            payments_csv, ["transaction_id", "customer_id", "amount", "transaction_date"]
        )
        bank_rows = await _read_rows(bank_csv, ["bank_reference", "amount", "settlement_date"])
        ledger_rows = await _read_rows(
            ledger_csv, ["ledger_reference", "customer_id", "expected_amount", "recorded_amount"]
        )

        payments = []
        for r in payment_rows:
            payments.append({
                "transaction_id": r["transaction_id"].strip(),
                "customer_id": r["customer_id"].strip(),
                "invoice_id": (r.get("invoice_id") or "").strip() or None,
                "amount": float(r["amount"]),
                "currency": r.get("currency", "INR"),
                "transaction_date": _parse_date(r["transaction_date"]),
                "status": r.get("status", "SUCCESS"),
                "payment_method": r.get("payment_method") or None,
                "record_metadata": {},
            })

        bank_txns = []
        for r in bank_rows:
            bank_txns.append({
                "bank_reference": r["bank_reference"].strip(),
                "transaction_id": (r.get("transaction_id") or "").strip() or None,
                "amount": float(r["amount"]),
                "settlement_date": _parse_date(r["settlement_date"]),
                "status": r.get("status", "SETTLED"),
                "fees": float(r.get("fees") or 0),
                "record_metadata": {},
            })

        ledger_entries = []
        for r in ledger_rows:
            ledger_entries.append({
                "ledger_reference": r["ledger_reference"].strip(),
                "invoice_id": (r.get("invoice_id") or "").strip() or None,
                "customer_id": r["customer_id"].strip(),
                "expected_amount": float(r["expected_amount"]),
                "recorded_amount": float(r["recorded_amount"]),
                "tax_amount": float(r.get("tax_amount") or 0),
                "date": _parse_date(r.get("date", "")),
                "status": r.get("status", "POSTED"),
                "record_metadata": {},
            })
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, f"CSV validation error: {exc}") from exc

    batch = create_batch_from_rows(db, label=label, payments=payments, bank_txns=bank_txns, ledger_entries=ledger_entries)
    return batch
