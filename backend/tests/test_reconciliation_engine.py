from datetime import date

from app.models import BankTransaction, LedgerEntry, PaymentTransaction
from app.reconciliation.matcher import ReconciliationEngine


def _payment(**kw):
    defaults = dict(
        id="p1", batch_id="b1", transaction_id="TXN1", customer_id="C1", invoice_id="INV1",
        amount=1000.0, currency="INR", transaction_date=date(2026, 6, 1), status="SUCCESS",
        payment_method="upi", record_metadata={},
    )
    defaults.update(kw)
    return PaymentTransaction(**defaults)


def _bank(**kw):
    defaults = dict(
        id="b1", batch_id="b1", bank_reference="BANK1", transaction_id="TXN1",
        amount=1000.0, settlement_date=date(2026, 6, 1), status="SETTLED", fees=20.0,
        record_metadata={},
    )
    defaults.update(kw)
    return BankTransaction(**defaults)


def _ledger(**kw):
    defaults = dict(
        id="l1", batch_id="b1", ledger_reference="LDG1", invoice_id="INV1", customer_id="C1",
        expected_amount=1000.0, recorded_amount=1000.0, tax_amount=180.0,
        date=date(2026, 6, 1), status="POSTED", record_metadata={},
    )
    defaults.update(kw)
    return LedgerEntry(**defaults)


def test_exact_match_is_clean():
    engine = ReconciliationEngine([_payment()], [_bank()], [_ledger()])
    outcomes, findings = engine.run()
    assert len(outcomes) == 1
    assert outcomes[0].match_status == "MATCHED"
    assert findings == []


def test_amount_mismatch_detected():
    payment = _payment()
    ledger = _ledger(recorded_amount=900.0)
    engine = ReconciliationEngine([payment], [_bank()], [ledger])
    outcomes, findings = engine.run()
    types = [f.exception_type for f in findings]
    assert "AMOUNT_MISMATCH" in types


def test_missing_bank_settlement_detected():
    payment = _payment()
    engine = ReconciliationEngine([payment], [], [_ledger()])
    outcomes, findings = engine.run()
    types = [f.exception_type for f in findings]
    assert "MISSING_BANK_SETTLEMENT" in types


def test_missing_ledger_entry_detected():
    payment = _payment()
    engine = ReconciliationEngine([payment], [_bank()], [])
    outcomes, findings = engine.run()
    types = [f.exception_type for f in findings]
    assert "MISSING_LEDGER_ENTRY" in types


def test_duplicate_transaction_detected():
    p1 = _payment(id="p1", transaction_id="TXN1")
    p2 = _payment(id="p2", transaction_id="TXN1-DUP")
    engine = ReconciliationEngine([p1, p2], [_bank(id="b1", transaction_id="TXN1")], [_ledger()])
    outcomes, findings = engine.run()
    types = [f.exception_type for f in findings]
    assert "DUPLICATE_TRANSACTION" in types


def test_date_mismatch_detected():
    bank = _bank(settlement_date=date(2026, 6, 10))
    engine = ReconciliationEngine([_payment()], [bank], [_ledger()])
    outcomes, findings = engine.run()
    types = [f.exception_type for f in findings]
    assert "DATE_MISMATCH" in types


def test_fee_mismatch_detected():
    payment = _payment(record_metadata={"expected_fee": 20.0})
    bank = _bank(fees=90.0)
    engine = ReconciliationEngine([payment], [bank], [_ledger()])
    outcomes, findings = engine.run()
    types = [f.exception_type for f in findings]
    assert "FEE_MISMATCH" in types


def test_tax_mismatch_detected():
    payment = _payment(record_metadata={"expected_tax": 180.0})
    ledger = _ledger(tax_amount=400.0)
    engine = ReconciliationEngine([payment], [_bank()], [ledger])
    outcomes, findings = engine.run()
    types = [f.exception_type for f in findings]
    assert "TAX_MISMATCH" in types


def test_partial_settlement_detected():
    bank = _bank(amount=500.0)
    engine = ReconciliationEngine([_payment()], [bank], [_ledger()])
    outcomes, findings = engine.run()
    types = [f.exception_type for f in findings]
    assert "PARTIAL_SETTLEMENT" in types


def test_orphan_bank_transaction_flagged_unresolvable():
    orphan_bank = _bank(id="b2", transaction_id=None, amount=5000.0)
    engine = ReconciliationEngine([], [orphan_bank], [])
    outcomes, findings = engine.run()
    types = [f.exception_type for f in findings]
    assert "UNKNOWN_UNRESOLVABLE" in types


def test_empty_batch_does_not_crash():
    engine = ReconciliationEngine([], [], [])
    outcomes, findings = engine.run()
    assert outcomes == []
    assert findings == []
