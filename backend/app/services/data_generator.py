"""
Reproducible synthetic financial dataset generator.

Given a seed, always produces the same dataset. Every "problematic" record
carries a ground_truth_label so the evaluation module can score the
reconciliation engine and AI agent against known-correct answers instead of
guessing.

Target distribution (approx, over N base transactions):
  60-70% clean, exactly reconcilable
  5-10% amount mismatch
  5-10% missing bank settlement
  5-10% missing ledger entry
  3-5%  duplicate payment
  3-5%  date mismatch
  3-5%  fee mismatch
  3-5%  tax mismatch
  remainder: partial settlement / unknown-unresolvable
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

CUSTOMER_IDS = [f"CUST{100+i}" for i in range(40)]
PAYMENT_METHODS = ["upi", "card", "netbanking", "wallet"]


@dataclass
class GeneratedRecord:
    kind: str  # payment | bank | ledger
    data: dict


@dataclass
class GeneratedDataset:
    payments: list[dict] = field(default_factory=list)
    bank_txns: list[dict] = field(default_factory=list)
    ledger_entries: list[dict] = field(default_factory=list)
    scenario_counts: dict[str, int] = field(default_factory=dict)


def generate_dataset(n_base: int = 150, seed: int = 42) -> GeneratedDataset:
    rng = random.Random(seed)
    base_date = date(2026, 6, 1)

    scenarios = (
        ["clean"] * int(n_base * 0.62)
        + ["amount_mismatch"] * int(n_base * 0.08)
        + ["missing_bank"] * int(n_base * 0.07)
        + ["missing_ledger"] * int(n_base * 0.07)
        + ["duplicate"] * int(n_base * 0.04)
        + ["date_mismatch"] * int(n_base * 0.04)
        + ["fee_mismatch"] * int(n_base * 0.04)
        + ["tax_mismatch"] * int(n_base * 0.04)
    )
    while len(scenarios) < n_base:
        scenarios.append("partial_settlement" if len(scenarios) % 2 == 0 else "unknown_unresolvable")
    rng.shuffle(scenarios)
    scenarios = scenarios[:n_base]

    ds = GeneratedDataset()
    scenario_counts: dict[str, int] = {}

    for i, scenario in enumerate(scenarios):
        scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1

        txn_id = f"TXN{1000+i}"
        invoice_id = f"INV{2000+i}"
        customer_id = rng.choice(CUSTOMER_IDS)
        amount = round(rng.uniform(500, 50000), 2)
        tax_amount = round(amount * 0.18, 2)
        txn_date = base_date + timedelta(days=rng.randint(0, 60))
        expected_fee = round(amount * 0.02, 2)
        method = rng.choice(PAYMENT_METHODS)

        payment = {
            "transaction_id": txn_id,
            "customer_id": customer_id,
            "invoice_id": invoice_id,
            "amount": amount,
            "currency": "INR",
            "transaction_date": txn_date,
            "status": "SUCCESS",
            "payment_method": method,
            "record_metadata": {"expected_fee": expected_fee, "expected_tax": tax_amount},
            "ground_truth_label": None,
        }

        bank = {
            "bank_reference": f"BANK{3000+i}",
            "transaction_id": txn_id,
            "amount": amount,
            "settlement_date": txn_date,
            "status": "SETTLED",
            "fees": expected_fee,
            "record_metadata": {},
            "ground_truth_label": None,
        }

        ledger = {
            "ledger_reference": f"LDG{4000+i}",
            "invoice_id": invoice_id,
            "customer_id": customer_id,
            "expected_amount": amount,
            "recorded_amount": amount,
            "tax_amount": tax_amount,
            "date": txn_date,
            "status": "POSTED",
            "record_metadata": {},
            "ground_truth_label": None,
        }

        if scenario == "clean":
            pass

        elif scenario == "amount_mismatch":
            drift = round(amount * rng.uniform(0.03, 0.15), 2)
            ledger["recorded_amount"] = round(amount - drift, 2)
            payment["ground_truth_label"] = "AMOUNT_MISMATCH"
            ledger["ground_truth_label"] = "AMOUNT_MISMATCH"

        elif scenario == "missing_bank":
            bank = None
            payment["ground_truth_label"] = "MISSING_BANK_SETTLEMENT"

        elif scenario == "missing_ledger":
            ledger = None
            payment["ground_truth_label"] = "MISSING_LEDGER_ENTRY"

        elif scenario == "duplicate":
            # emit the clean record, then a duplicate payment (handled after loop)
            payment["ground_truth_label"] = None

        elif scenario == "date_mismatch":
            bank["settlement_date"] = txn_date + timedelta(days=rng.randint(4, 10))
            payment["ground_truth_label"] = "DATE_MISMATCH"
            bank["ground_truth_label"] = "DATE_MISMATCH"

        elif scenario == "fee_mismatch":
            bank["fees"] = round(expected_fee + rng.uniform(20, 100), 2)
            payment["ground_truth_label"] = "FEE_MISMATCH"
            bank["ground_truth_label"] = "FEE_MISMATCH"

        elif scenario == "tax_mismatch":
            ledger["tax_amount"] = round(tax_amount + rng.uniform(50, 300), 2)
            payment["ground_truth_label"] = "TAX_MISMATCH"
            ledger["ground_truth_label"] = "TAX_MISMATCH"

        elif scenario == "partial_settlement":
            bank["amount"] = round(amount * rng.uniform(0.4, 0.7), 2)
            payment["ground_truth_label"] = "PARTIAL_SETTLEMENT"
            bank["ground_truth_label"] = "PARTIAL_SETTLEMENT"

        elif scenario == "unknown_unresolvable":
            # Orphan bank settlement with no plausible payment link, and drop the
            # original payment's bank+ledger side entirely to create genuine
            # ambiguity that no rule can cleanly resolve.
            bank["transaction_id"] = None
            bank["amount"] = round(rng.uniform(500, 50000), 2)
            ledger = None
            payment["ground_truth_label"] = "UNKNOWN_UNRESOLVABLE"
            bank["ground_truth_label"] = "UNKNOWN_UNRESOLVABLE"

        ds.payments.append(payment)
        if bank is not None:
            ds.bank_txns.append(bank)
        if ledger is not None:
            ds.ledger_entries.append(ledger)

        if scenario == "duplicate":
            dup = dict(payment)
            dup["transaction_id"] = f"{txn_id}-DUP"
            dup["ground_truth_label"] = "DUPLICATE_TRANSACTION"
            ds.payments.append(dup)

    ds.scenario_counts = scenario_counts
    return ds
