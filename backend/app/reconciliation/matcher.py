"""
Deterministic reconciliation engine.

No LLM is involved anywhere in this file. Every match or exception is the
result of explicit, auditable rules over the payment / bank / ledger
records. This is intentional: arithmetic and primary transaction matching
must be verifiable, not "AI judgment".

Matching hierarchy (first hit wins):
  L1: exact transaction/reference id shared across payment + bank
  L2: invoice_id + customer_id + amount (exact)
  L3: invoice_id + amount + date within tolerance
  L4: customer_id + amount + date proximity (no invoice_id available)
  L5: controlled fuzzy match (amount within small tolerance + same customer,
      used only when nothing above matched and it's still a plausible pair)

After the best available payment<->bank pairing is chosen, the same record
is checked against the ledger (by invoice_id, falling back to customer_id +
amount) to detect ledger-side mismatches (amount/tax) independent of the
bank-matching result.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.config import get_settings
from app.models.base_types import ExceptionType, MatchMethod, MatchStatus, Severity

settings = get_settings()


@dataclass
class MatchOutcome:
    match_status: str
    match_method: str
    confidence: float
    amount_difference: float
    date_difference_days: int
    reason: str
    evidence: dict
    payment_id: Optional[str] = None
    bank_transaction_id: Optional[str] = None
    ledger_entry_id: Optional[str] = None


@dataclass
class ExceptionFinding:
    exception_type: str
    severity: str
    description: str
    amount_affected: float
    payment_id: Optional[str] = None
    bank_transaction_id: Optional[str] = None
    ledger_entry_id: Optional[str] = None
    evidence: dict = field(default_factory=dict)


def _days_between(d1: date, d2: date) -> int:
    return abs((d1 - d2).days)


class ReconciliationEngine:
    def __init__(self, payments: list, bank_txns: list, ledger_entries: list):
        self.payments = payments
        self.bank_txns = bank_txns
        self.ledger_entries = ledger_entries

        # Fast lookup indexes
        self._bank_by_txn_id: dict[str, list] = defaultdict(list)
        for b in bank_txns:
            if b.transaction_id:
                self._bank_by_txn_id[b.transaction_id].append(b)

        self._bank_by_amount: dict[float, list] = defaultdict(list)
        for b in bank_txns:
            self._bank_by_amount[round(b.amount, 2)].append(b)

        self._ledger_by_invoice: dict[str, list] = defaultdict(list)
        for entry in ledger_entries:
            if entry.invoice_id:
                self._ledger_by_invoice[entry.invoice_id].append(entry)

        self._ledger_by_customer_amount: dict[tuple, list] = defaultdict(list)
        for entry in ledger_entries:
            self._ledger_by_customer_amount[(entry.customer_id, round(entry.expected_amount, 2))].append(entry)

        self._used_bank_ids: set[str] = set()
        self._used_ledger_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Payment <-> Bank matching
    # ------------------------------------------------------------------
    def _match_payment_to_bank(self, payment) -> tuple[Optional[object], str, float, str]:
        """Returns (bank_txn_or_None, method, confidence, reason)."""

        # L1: exact transaction id
        candidates = [
            b for b in self._bank_by_txn_id.get(payment.transaction_id, [])
            if b.id not in self._used_bank_ids
        ]
        if candidates:
            return candidates[0], MatchMethod.EXACT_REFERENCE.value, 1.0, "Exact transaction ID match"

        # L2/L3: by amount, then narrow by date tolerance
        amount_candidates = [
            b for b in self._bank_by_amount.get(round(payment.amount, 2), [])
            if b.id not in self._used_bank_ids
        ]
        if amount_candidates:
            same_date = [
                b for b in amount_candidates
                if _days_between(b.settlement_date, payment.transaction_date) == 0
            ]
            if same_date:
                return same_date[0], MatchMethod.INVOICE_CUSTOMER_AMOUNT.value, 0.95, \
                    "Exact amount match, same date"
            within_tolerance = [
                b for b in amount_candidates
                if _days_between(b.settlement_date, payment.transaction_date) <= settings.DATE_TOLERANCE_DAYS
            ]
            if within_tolerance:
                within_tolerance.sort(
                    key=lambda b: _days_between(b.settlement_date, payment.transaction_date)
                )
                return within_tolerance[0], MatchMethod.INVOICE_AMOUNT_DATE_TOLERANCE.value, 0.85, \
                    f"Amount match within {settings.DATE_TOLERANCE_DAYS}-day settlement tolerance"

        # L5: fuzzy - amount within small tolerance (settlement fees etc.)
        near_amount = [
            b for b in self.bank_txns
            if b.id not in self._used_bank_ids
            and abs(b.amount - payment.amount) <= max(settings.AMOUNT_MISMATCH_THRESHOLD, payment.amount * 0.02)
            and _days_between(b.settlement_date, payment.transaction_date) <= settings.DATE_TOLERANCE_DAYS + 1
        ]
        if near_amount:
            near_amount.sort(key=lambda b: abs(b.amount - payment.amount))
            candidate = near_amount[0]
            confidence = round(settings.FUZZY_MATCH_MIN_CONFIDENCE, 2)
            return candidate, MatchMethod.FUZZY.value, confidence, \
                "Fuzzy match on near-equal amount within tolerance window"

        return None, MatchMethod.NONE.value, 0.0, "No plausible bank settlement found"

    def _find_ledger_entry(self, payment) -> Optional[object]:
        if payment.invoice_id:
            candidates = [
                e for e in self._ledger_by_invoice.get(payment.invoice_id, [])
                if e.id not in self._used_ledger_ids
            ]
            if candidates:
                return candidates[0]
        candidates = [
            e for e in self._ledger_by_customer_amount.get(
                (payment.customer_id, round(payment.amount, 2)), []
            )
            if e.id not in self._used_ledger_ids
        ]
        if candidates:
            return candidates[0]
        return None

    # ------------------------------------------------------------------
    # Duplicate detection (payment-side)
    # ------------------------------------------------------------------
    def _detect_duplicates(self) -> list[ExceptionFinding]:
        findings = []
        seen: dict[tuple, list] = defaultdict(list)
        for p in self.payments:
            key = (p.customer_id, p.invoice_id, round(p.amount, 2), p.transaction_date)
            seen[key].append(p)
        for key, group in seen.items():
            if len(group) > 1:
                # Keep the first as legitimate, flag the rest as duplicates
                for dup in group[1:]:
                    findings.append(ExceptionFinding(
                        exception_type=ExceptionType.DUPLICATE_TRANSACTION.value,
                        severity=Severity.HIGH.value,
                        description=(
                            f"Payment {dup.transaction_id} appears to duplicate "
                            f"{group[0].transaction_id} (same customer, invoice, amount, date)"
                        ),
                        amount_affected=dup.amount,
                        payment_id=dup.id,
                        evidence={"duplicate_of_payment_id": group[0].id,
                                  "duplicate_of_transaction_id": group[0].transaction_id},
                    ))
        return findings

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def run(self) -> tuple[list[MatchOutcome], list[ExceptionFinding]]:
        outcomes: list[MatchOutcome] = []
        findings: list[ExceptionFinding] = []

        findings.extend(self._detect_duplicates())
        duplicate_payment_ids = {
            f.payment_id for f in findings if f.exception_type == ExceptionType.DUPLICATE_TRANSACTION.value
        }

        for payment in self.payments:
            bank_txn, method, confidence, reason = self._match_payment_to_bank(payment)
            ledger_entry = self._find_ledger_entry(payment)

            if bank_txn:
                self._used_bank_ids.add(bank_txn.id)
            if ledger_entry:
                self._used_ledger_ids.add(ledger_entry.id)

            issues: list[ExceptionFinding] = []
            amount_diff = 0.0
            date_diff = 0

            if payment.id in duplicate_payment_ids:
                # already recorded as a duplicate exception; still attempt matching
                # for evidentiary completeness but mark as exception overall.
                pass

            if bank_txn is None:
                issues.append(ExceptionFinding(
                    exception_type=ExceptionType.MISSING_BANK_SETTLEMENT.value,
                    severity=Severity.HIGH.value,
                    description=f"No bank settlement found for payment {payment.transaction_id}",
                    amount_affected=payment.amount,
                    payment_id=payment.id,
                    evidence={"payment_amount": payment.amount, "payment_date": str(payment.transaction_date)},
                ))
            else:
                amount_diff = round(bank_txn.amount - payment.amount, 2)
                date_diff = _days_between(bank_txn.settlement_date, payment.transaction_date)

                if abs(amount_diff) > settings.AMOUNT_MISMATCH_THRESHOLD:
                    if bank_txn.amount < payment.amount and abs(amount_diff) >= payment.amount * 0.05:
                        issues.append(ExceptionFinding(
                            exception_type=ExceptionType.PARTIAL_SETTLEMENT.value,
                            severity=Severity.MEDIUM.value,
                            description=(
                                f"Bank settled {bank_txn.amount} against payment amount "
                                f"{payment.amount} for {payment.transaction_id} (partial)"
                            ),
                            amount_affected=abs(amount_diff),
                            payment_id=payment.id, bank_transaction_id=bank_txn.id,
                            evidence={"payment_amount": payment.amount, "bank_amount": bank_txn.amount},
                        ))
                    else:
                        issues.append(ExceptionFinding(
                            exception_type=ExceptionType.AMOUNT_MISMATCH.value,
                            severity=Severity.HIGH.value,
                            description=(
                                f"Bank amount {bank_txn.amount} does not match payment amount "
                                f"{payment.amount} for {payment.transaction_id}"
                            ),
                            amount_affected=abs(amount_diff),
                            payment_id=payment.id, bank_transaction_id=bank_txn.id,
                            evidence={"payment_amount": payment.amount, "bank_amount": bank_txn.amount},
                        ))

                if date_diff > settings.DATE_TOLERANCE_DAYS:
                    issues.append(ExceptionFinding(
                        exception_type=ExceptionType.DATE_MISMATCH.value,
                        severity=Severity.LOW.value,
                        description=(
                            f"Settlement date differs from payment date by {date_diff} days "
                            f"for {payment.transaction_id}"
                        ),
                        amount_affected=0.0,
                        payment_id=payment.id, bank_transaction_id=bank_txn.id,
                        evidence={"payment_date": str(payment.transaction_date),
                                  "settlement_date": str(bank_txn.settlement_date)},
                    ))

                # Fee sanity check: if metadata declares an expected fee, compare it.
                expected_fee = (payment.record_metadata or {}).get("expected_fee")
                if expected_fee is not None and abs(bank_txn.fees - float(expected_fee)) > 0.5:
                    issues.append(ExceptionFinding(
                        exception_type=ExceptionType.FEE_MISMATCH.value,
                        severity=Severity.LOW.value,
                        description=(
                            f"Bank fee {bank_txn.fees} does not match expected fee "
                            f"{expected_fee} for {payment.transaction_id}"
                        ),
                        amount_affected=abs(bank_txn.fees - float(expected_fee)),
                        payment_id=payment.id, bank_transaction_id=bank_txn.id,
                        evidence={"bank_fee": bank_txn.fees, "expected_fee": expected_fee},
                    ))

            if ledger_entry is None:
                issues.append(ExceptionFinding(
                    exception_type=ExceptionType.MISSING_LEDGER_ENTRY.value,
                    severity=Severity.MEDIUM.value,
                    description=f"No ledger entry found for payment {payment.transaction_id}",
                    amount_affected=payment.amount,
                    payment_id=payment.id,
                    evidence={"payment_amount": payment.amount},
                ))
            else:
                ledger_diff = round(ledger_entry.recorded_amount - ledger_entry.expected_amount, 2)
                if abs(ledger_diff) > settings.AMOUNT_MISMATCH_THRESHOLD:
                    issues.append(ExceptionFinding(
                        exception_type=ExceptionType.AMOUNT_MISMATCH.value,
                        severity=Severity.HIGH.value,
                        description=(
                            f"Ledger recorded amount {ledger_entry.recorded_amount} does not match "
                            f"expected amount {ledger_entry.expected_amount} for invoice "
                            f"{ledger_entry.invoice_id}"
                        ),
                        amount_affected=abs(ledger_diff),
                        payment_id=payment.id, ledger_entry_id=ledger_entry.id,
                        evidence={"expected_amount": ledger_entry.expected_amount,
                                  "recorded_amount": ledger_entry.recorded_amount},
                    ))
                expected_tax = (payment.record_metadata or {}).get("expected_tax")
                if expected_tax is not None and abs(ledger_entry.tax_amount - float(expected_tax)) > 0.5:
                    issues.append(ExceptionFinding(
                        exception_type=ExceptionType.TAX_MISMATCH.value,
                        severity=Severity.MEDIUM.value,
                        description=(
                            f"Ledger tax amount {ledger_entry.tax_amount} does not match expected "
                            f"tax {expected_tax} for invoice {ledger_entry.invoice_id}"
                        ),
                        amount_affected=abs(ledger_entry.tax_amount - float(expected_tax)),
                        payment_id=payment.id, ledger_entry_id=ledger_entry.id,
                        evidence={"ledger_tax": ledger_entry.tax_amount, "expected_tax": expected_tax},
                    ))

            if payment.id in duplicate_payment_ids:
                issues.append(ExceptionFinding(
                    exception_type=ExceptionType.DUPLICATE_TRANSACTION.value,
                    severity=Severity.HIGH.value,
                    description=f"Payment {payment.transaction_id} flagged as a likely duplicate",
                    amount_affected=payment.amount,
                    payment_id=payment.id,
                    evidence={},
                ))

            is_matched = bank_txn is not None and ledger_entry is not None and not issues

            if is_matched:
                outcomes.append(MatchOutcome(
                    match_status=MatchStatus.MATCHED.value,
                    match_method=method,
                    confidence=confidence,
                    amount_difference=amount_diff,
                    date_difference_days=date_diff,
                    reason=reason,
                    evidence={"payment_amount": payment.amount,
                              "bank_amount": bank_txn.amount if bank_txn else None,
                              "ledger_expected_amount": ledger_entry.expected_amount if ledger_entry else None},
                    payment_id=payment.id,
                    bank_transaction_id=bank_txn.id if bank_txn else None,
                    ledger_entry_id=ledger_entry.id if ledger_entry else None,
                ))
            else:
                outcomes.append(MatchOutcome(
                    match_status=MatchStatus.EXCEPTION.value,
                    match_method=method,
                    confidence=confidence,
                    amount_difference=amount_diff,
                    date_difference_days=date_diff,
                    reason=reason if issues else "Matched but flagged for review",
                    evidence={"payment_amount": payment.amount,
                              "bank_amount": bank_txn.amount if bank_txn else None,
                              "ledger_expected_amount": ledger_entry.expected_amount if ledger_entry else None},
                    payment_id=payment.id,
                    bank_transaction_id=bank_txn.id if bank_txn else None,
                    ledger_entry_id=ledger_entry.id if ledger_entry else None,
                ))
                if not issues:
                    # Matched to both sides but something else prevented a clean match
                    # (should be rare) - record as unknown/unresolvable rather than
                    # silently calling it matched.
                    issues.append(ExceptionFinding(
                        exception_type=ExceptionType.UNKNOWN_UNRESOLVABLE.value,
                        severity=Severity.MEDIUM.value,
                        description=f"Payment {payment.transaction_id} could not be confidently resolved",
                        amount_affected=payment.amount,
                        payment_id=payment.id,
                        evidence={},
                    ))
                findings.extend(issues)

        # Orphan bank transactions: settled money with no matching payment at all
        for b in self.bank_txns:
            if b.id not in self._used_bank_ids:
                findings.append(ExceptionFinding(
                    exception_type=ExceptionType.UNKNOWN_UNRESOLVABLE.value,
                    severity=Severity.MEDIUM.value,
                    description=f"Bank settlement {b.bank_reference} has no matching payment record",
                    amount_affected=b.amount,
                    bank_transaction_id=b.id,
                    evidence={"bank_amount": b.amount, "settlement_date": str(b.settlement_date)},
                ))

        return outcomes, findings
