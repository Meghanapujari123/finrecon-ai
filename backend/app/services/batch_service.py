from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import BankTransaction, Batch, LedgerEntry, PaymentTransaction
from app.services.data_generator import generate_dataset


def create_demo_batch(db: Session, n_base: int = 150, seed: int = 42) -> Batch:
    ds = generate_dataset(n_base=n_base, seed=seed)

    batch = Batch(
        label=f"Demo dataset (seed={seed}, n={n_base})",
        source="demo",
        seed=str(seed),
        notes=str(ds.scenario_counts),
    )
    db.add(batch)
    db.flush()

    for p in ds.payments:
        db.add(PaymentTransaction(batch_id=batch.id, **p))
    for b in ds.bank_txns:
        db.add(BankTransaction(batch_id=batch.id, **b))
    for entry in ds.ledger_entries:
        db.add(LedgerEntry(batch_id=batch.id, **entry))

    db.commit()
    db.refresh(batch)
    return batch


def create_batch_from_rows(
    db: Session,
    label: str,
    payments: list[dict],
    bank_txns: list[dict],
    ledger_entries: list[dict],
) -> Batch:
    batch = Batch(label=label, source="upload")
    db.add(batch)
    db.flush()

    for p in payments:
        db.add(PaymentTransaction(batch_id=batch.id, **p))
    for b in bank_txns:
        db.add(BankTransaction(batch_id=batch.id, **b))
    for entry in ledger_entries:
        db.add(LedgerEntry(batch_id=batch.id, **entry))

    db.commit()
    db.refresh(batch)
    return batch
