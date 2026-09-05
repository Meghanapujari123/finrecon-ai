"""
Finance Q&A service for FinRecon AI.

Architecture:
- Database is always the source of truth.
- Deterministic database functions calculate all financial values.
- Gemini is ONLY used to explain verified database results.
- Gemini never queries the database.
- Gemini never calculates financial values.
- If Gemini is unavailable, the verified database result is still returned.
"""

from __future__ import annotations

from typing import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.llm_provider import (
    LLMUnavailableError,
    get_llm_provider,
)

from app.models import (
    ExceptionRecord,
    PaymentTransaction,
    ReconciliationResult,
)


# ======================================================================
# SAFE DATABASE QUERY TOOLS
# ======================================================================


def _amount_at_risk(db: Session, batch_id: str) -> dict:
    """
    Calculate total amount currently affected by unresolved exceptions.
    """

    total = (
        db.query(
            func.coalesce(
                func.sum(ExceptionRecord.amount_affected),
                0.0,
            )
        )
        .filter(
            ExceptionRecord.batch_id == batch_id,
            ExceptionRecord.status != "RESOLVED",
        )
        .scalar()
    )

    return {
        "answer_value": round(float(total or 0), 2),
        "unit": "currency",
    }


def _top_exception_types(
    db: Session,
    batch_id: str,
    limit: int = 3,
) -> dict:
    """
    Return the most frequently occurring exception types.
    """

    rows = (
        db.query(
            ExceptionRecord.exception_type,
            func.count(ExceptionRecord.id),
        )
        .filter(
            ExceptionRecord.batch_id == batch_id,
        )
        .group_by(
            ExceptionRecord.exception_type,
        )
        .order_by(
            func.count(ExceptionRecord.id).desc(),
        )
        .limit(limit)
        .all()
    )

    return {
        "answer_value": [
            {
                "type": exception_type,
                "count": int(count),
            }
            for exception_type, count in rows
        ]
    }


def _missing_settlements(
    db: Session,
    batch_id: str,
) -> dict:
    """
    Count missing bank settlements.
    """

    rows = (
        db.query(ExceptionRecord)
        .filter(
            ExceptionRecord.batch_id == batch_id,
            ExceptionRecord.exception_type == "MISSING_BANK_SETTLEMENT",
        )
        .all()
    )

    return {
        "answer_value": len(rows),
        "record_ids": [r.id for r in rows][:20],
    }


def _reconciled_amount(
    db: Session,
    batch_id: str,
) -> dict:
    """
    Calculate total amount of matched/reconciled payments.
    """

    result_rows = (
        db.query(ReconciliationResult.payment_id)
        .filter(
            ReconciliationResult.batch_id == batch_id,
            ReconciliationResult.match_status == "MATCHED",
        )
        .all()
    )

    payment_ids = [
        row[0]
        for row in result_rows
        if row[0]
    ]

    if not payment_ids:
        return {
            "answer_value": 0.0,
            "unit": "currency",
        }

    total = (
        db.query(
            func.coalesce(
                func.sum(PaymentTransaction.amount),
                0.0,
            )
        )
        .filter(
            PaymentTransaction.id.in_(payment_ids),
        )
        .scalar()
    )

    return {
        "answer_value": round(float(total or 0), 2),
        "unit": "currency",
    }


def _human_review_required(
    db: Session,
    batch_id: str,
) -> dict:
    """
    Count exceptions requiring human review/approval.
    """

    count = (
        db.query(
            func.count(ExceptionRecord.id),
        )
        .filter(
            ExceptionRecord.batch_id == batch_id,
            ExceptionRecord.requires_human_approval == True,  # noqa: E712
        )
        .scalar()
    )

    return {
        "answer_value": int(count or 0),
    }


def _largest_discrepancy(
    db: Session,
    batch_id: str,
) -> dict:
    """
    Find the single exception with the largest amount affected.
    """

    row = (
        db.query(ExceptionRecord)
        .filter(
            ExceptionRecord.batch_id == batch_id,
        )
        .order_by(
            ExceptionRecord.amount_affected.desc(),
        )
        .first()
    )

    if not row:
        return {
            "answer_value": None,
        }

    return {
        "answer_value": round(
            float(row.amount_affected or 0),
            2,
        ),
        "record_ids": [row.id],
        "detail": {
            "exception_type": row.exception_type,
            "description": row.description,
        },
    }


def _financial_impact_by_type(
    db: Session,
    batch_id: str,
    limit: int = 3,
) -> dict:
    """
    Calculate total financial impact grouped by exception type.
    """

    rows = (
        db.query(
            ExceptionRecord.exception_type,
            func.coalesce(
                func.sum(ExceptionRecord.amount_affected),
                0.0,
            ),
        )
        .filter(
            ExceptionRecord.batch_id == batch_id,
        )
        .group_by(
            ExceptionRecord.exception_type,
        )
        .order_by(
            func.coalesce(
                func.sum(ExceptionRecord.amount_affected),
                0.0,
            ).desc(),
        )
        .limit(limit)
        .all()
    )

    return {
        "answer_value": [
            {
                "type": exception_type,
                "financial_impact": round(
                    float(financial_impact or 0),
                    2,
                ),
            }
            for exception_type, financial_impact in rows
        ]
    }


def _total_exception_financial_impact(
    db: Session,
    batch_id: str,
) -> dict:
    """
    Calculate total financial impact across all exceptions.
    """

    total = (
        db.query(
            func.coalesce(
                func.sum(ExceptionRecord.amount_affected),
                0.0,
            )
        )
        .filter(
            ExceptionRecord.batch_id == batch_id,
        )
        .scalar()
    )

    return {
        "answer_value": round(
            float(total or 0),
            2,
        ),
        "unit": "currency",
    }


def _exception_count(
    db: Session,
    batch_id: str,
) -> dict:
    """
    Count all exception records.
    """

    count = (
        db.query(
            func.count(ExceptionRecord.id),
        )
        .filter(
            ExceptionRecord.batch_id == batch_id,
        )
        .scalar()
    )

    return {
        "answer_value": int(count or 0),
    }


# ======================================================================
# INTENT DETECTION
# ======================================================================

QueryFunction = Callable[[Session, str], dict]


def _detect_intent(question: str) -> QueryFunction | None:
    """
    Deterministically map natural-language questions to safe
    database query functions.

    The LLM is NOT used to choose database queries.
    """

    q = " ".join(
        question.lower().strip().split()
    )

    # ------------------------------------------------------------------
    # 1. AMOUNT AT RISK
    # ------------------------------------------------------------------

    risk_phrases = [
        "amount at risk",
        "money at risk",
        "money is at risk",
        "money currently at risk",
        "money is currently at risk",
        "financial risk",
        "total risk",
        "affected amount",
        "affected money",
        "affected funds",
        "money exposed",
        "financial exposure",
        "current financial exposure",
        "how much money is at risk",
        "how much money is currently at risk",
        "how much is at risk",
        "how much is currently at risk",
        "total amount at risk",
        "current amount at risk",
        "currently at risk",
        "what is at risk",
        "what's at risk",
        "how much is exposed",
        "how much money is exposed",
        "total exposed amount",
    ]

    if any(
        phrase in q
        for phrase in risk_phrases
    ):
        return _amount_at_risk

    # ------------------------------------------------------------------
    # 2. FINANCIAL IMPACT / MOST EXPENSIVE ISSUE
    # ------------------------------------------------------------------

    financial_impact_phrases = [
        "financial impact",
        "highest financial impact",
        "largest financial impact",
        "biggest financial impact",
        "most financial impact",
        "highest impact",
        "largest impact",
        "biggest impact",
        "highest cost",
        "largest cost",
        "biggest cost",
        "highest loss",
        "largest loss",
        "biggest loss",
        "financial loss",
        "financially significant",
        "costs us the most",
        "cost us the most",
        "costing us the most",
        "costs the most",
        "which issue costs the most",
        "which issue costs us the most",
        "which exception costs the most",
        "what issue costs the most",
        "what exception costs the most",
        "which problem costs the most",
        "what problem costs the most",
        "which problem is most expensive",
        "which issue is most expensive",
        "which exception is most expensive",
        "most expensive issue",
        "most expensive exception",
        "most expensive problem",
        "most costly issue",
        "most costly exception",
        "most costly problem",
        "biggest financial loss",
        "largest financial loss",
        "highest financial loss",
        "what costs us the most",
        "what costs the most",
        "which one costs the most",
        "which one has the highest impact",
        "which one has the biggest impact",
    ]

    if any(
        phrase in q
        for phrase in financial_impact_phrases
    ):
        return _financial_impact_by_type

    # ------------------------------------------------------------------
    # 3. LARGEST SINGLE DISCREPANCY
    # ------------------------------------------------------------------

    discrepancy_phrases = [
        "biggest discrepancy",
        "largest discrepancy",
        "highest discrepancy",
        "maximum discrepancy",
        "biggest difference",
        "largest difference",
        "highest difference",
        "largest mismatch",
        "biggest mismatch",
        "maximum mismatch",
        "largest exception",
        "biggest exception",
        "largest single discrepancy",
        "biggest single discrepancy",
        "largest individual discrepancy",
        "biggest individual discrepancy",
        "what is the biggest discrepancy",
        "what's the biggest discrepancy",
        "what is the largest discrepancy",
        "what's the largest discrepancy",
    ]

    if any(
        phrase in q
        for phrase in discrepancy_phrases
    ):
        return _largest_discrepancy

    # ------------------------------------------------------------------
    # 4. HUMAN REVIEW / APPROVAL
    # ------------------------------------------------------------------

    human_review_phrases = [
        "human review",
        "human-review",
        "human approval",
        "human-approval",
        "requires human review",
        "require human review",
        "requires human approval",
        "require human approval",
        "need human review",
        "needs human review",
        "need human approval",
        "needs human approval",
        "need review",
        "needs review",
        "need approval",
        "needs approval",
        "manual review",
        "manual approval",
        "review required",
        "approval required",
        "transactions require review",
        "transactions need review",
        "transactions requiring review",
        "transactions requiring approval",
        "how many require review",
        "how many require human review",
        "how many need human review",
        "how many need review",
        "how many need approval",
        "how many require approval",
        "human review count",
        "review count",
    ]

    if any(
        phrase in q
        for phrase in human_review_phrases
    ):
        return _human_review_required

    # ------------------------------------------------------------------
    # 5. MISSING SETTLEMENTS
    # ------------------------------------------------------------------

    missing_settlement_phrases = [
        "missing settlement",
        "missing settlements",
        "missing bank settlement",
        "missing bank settlements",
        "bank settlement",
        "bank settlements",
        "settlement missing",
        "settlements missing",
        "how many settlements are missing",
        "how many bank settlements are missing",
        "how many settlements are there",
        "number of missing settlements",
    ]

    if any(
        phrase in q
        for phrase in missing_settlement_phrases
    ):
        return _missing_settlements

    # ------------------------------------------------------------------
    # 6. RECONCILED / MATCHED AMOUNT
    # ------------------------------------------------------------------

    reconciled_phrases = [
        "reconciled amount",
        "reconciled money",
        "reconciled value",
        "matched amount",
        "matched money",
        "matched value",
        "how much was reconciled",
        "how much is reconciled",
        "how much was matched",
        "how much is matched",
        "total reconciled",
        "total matched",
        "reconciliation amount",
        "amount reconciled",
        "amount matched",
        "money reconciled",
        "money matched",
    ]

    if any(
        phrase in q
        for phrase in reconciled_phrases
    ):
        return _reconciled_amount

    # ------------------------------------------------------------------
    # 7. MOST FREQUENT EXCEPTION TYPES / MAIN CAUSES
    # ------------------------------------------------------------------

    frequency_phrases = [
        "most frequent exception",
        "most frequent exceptions",
        "frequent exception",
        "frequent exceptions",
        "most common exception",
        "most common exceptions",
        "common exception types",
        "top exception types",
        "top exceptions",
        "which exception occurs most",
        "which exception occurs most often",
        "which exceptions occur most",
        "which exception types occur most",
        "what exception occurs most",
        "what exceptions occur most",
        "main exception types",
        "main causes",
        "main cause",
        "main causes of reconciliation failures",
        "causes of reconciliation failures",
        "reconciliation failures",
        "why are reconciliations failing",
        "why are transactions failing",
        "most common reconciliation failures",
        "most frequent reconciliation failures",
        "common reconciliation problems",
        "most common reconciliation problems",
        "main reconciliation problems",
        "biggest reconciliation problems",
        "top reconciliation problems",
        "which problems happen most",
        "which issues happen most",
        "which exceptions happen most",
        "which exception types are most common",
    ]

    if any(
        phrase in q
        for phrase in frequency_phrases
    ):
        return _top_exception_types

    # ------------------------------------------------------------------
    # 8. TOTAL NUMBER OF EXCEPTIONS
    # ------------------------------------------------------------------

    exception_count_phrases = [
        "how many exceptions",
        "number of exceptions",
        "total exceptions",
        "exception count",
        "how many issues",
        "number of issues",
        "total issues",
        "how many reconciliation issues",
        "how many reconciliation exceptions",
        "total reconciliation exceptions",
        "total reconciliation issues",
    ]

    if any(
        phrase in q
        for phrase in exception_count_phrases
    ):
        return _exception_count

    return None


# ======================================================================
# GEMINI EXPLANATION
# ======================================================================


def _generate_explanation(
    question: str,
    tool_result: dict,
) -> str | None:
    """
    Ask Gemini to explain the verified database result.

    Gemini receives ONLY the database result.
    """

    provider = get_llm_provider()

    if not provider.is_available():
        return None

    system_prompt = """
You are the Finance Q&A explanation assistant for FinRecon AI.

Your job is ONLY to explain a result that has already been calculated
from the database.

STRICT RULES:

1. Never invent numbers.
2. Never modify numbers.
3. Never calculate a different number.
4. Never assume missing data.
5. Use only the supplied database result.
6. Answer the user's exact question.
7. Be concise and professional.
8. Do not mention that you are an AI unless necessary.
9. Do not say "computed result".
10. Do not expose internal Python, database, or tool details.
11. If the result contains a list, identify the most relevant items.
12. If the user asks which issue/type costs the most, clearly state
    the highest-impact exception and its financial impact.
13. If the user asks for the amount at risk, clearly state the amount.
14. If the user asks for a count, clearly state the count.
15. If the result contains a currency value, preserve the exact value.
16. Do not add currency symbols unless one is explicitly present
    in the supplied result.
17. Return ONLY valid JSON.

The JSON must contain exactly:

{
  "explanation": "..."
}
"""

    user_prompt = f"""
USER QUESTION:
{question}

VERIFIED DATABASE RESULT:
{tool_result}

Return ONLY this JSON structure:

{{
  "explanation": "..."
}}
"""

    try:
        result = provider.complete_json(
            system_prompt,
            user_prompt,
        )

        explanation = result.get("explanation")

        if (
            isinstance(explanation, str)
            and explanation.strip()
        ):
            return explanation.strip()

    except LLMUnavailableError:
        return None

    except Exception:
        return None

    return None


# ======================================================================
# FALLBACK RESPONSE FORMATTER
# ======================================================================


def _format_fallback_answer(
    question: str,
    tool_result: dict,
) -> str:
    """
    Produce a useful answer without Gemini.
    """

    answer_value = tool_result.get(
        "answer_value"
    )

    question_lower = question.lower()

    # --------------------------------------------------------------
    # Amount at risk
    # --------------------------------------------------------------

    if (
        "risk" in question_lower
        or "exposed" in question_lower
        or "exposure" in question_lower
    ):
        if isinstance(answer_value, (int, float)):
            return (
                f"The total amount currently at risk is "
                f"{answer_value:,.2f}."
            )

    # --------------------------------------------------------------
    # Financial impact
    # --------------------------------------------------------------

    if isinstance(answer_value, list):

        if not answer_value:
            return "No matching records were found."

        first = answer_value[0]

        if (
            isinstance(first, dict)
            and "financial_impact" in first
        ):
            top = first

            return (
                f"The exception with the highest financial impact is "
                f"{top.get('type')} at "
                f"{float(top.get('financial_impact', 0)):,.2f}."
            )

        if (
            isinstance(first, dict)
            and "count" in first
        ):
            parts = []

            for item in answer_value[:3]:
                parts.append(
                    f"{item.get('type')} "
                    f"({item.get('count')})"
                )

            return (
                "The most frequent exception types are "
                + ", ".join(parts)
                + "."
            )

    # --------------------------------------------------------------
    # Largest discrepancy
    # --------------------------------------------------------------

    if (
        "detail" in tool_result
        and answer_value is not None
    ):
        detail = tool_result.get(
            "detail",
            {},
        )

        exception_type = detail.get(
            "exception_type",
            "the exception",
        )

        return (
            f"The biggest discrepancy is "
            f"{float(answer_value):,.2f}, "
            f"identified as {exception_type}."
        )

    # --------------------------------------------------------------
    # Currency
    # --------------------------------------------------------------

    if tool_result.get("unit") == "currency":
        return (
            f"The amount is "
            f"{float(answer_value or 0):,.2f}."
        )

    # --------------------------------------------------------------
    # Generic numeric result
    # --------------------------------------------------------------

    if answer_value is None:
        return "No matching record was found."

    return (
        f"The result is {answer_value}."
    )


# ======================================================================
# MAIN QA FUNCTION
# ======================================================================


def answer_question(
    db: Session,
    batch_id: str,
    question: str,
) -> dict:
    """
    Main entry point for Finance Q&A.
    """

    # --------------------------------------------------------------
    # Validate question
    # --------------------------------------------------------------

    if not question or not question.strip():
        return {
            "answer": "Please enter a finance question.",
            "supporting_records": [],
            "calculated_metrics": {},
            "confidence": None,
        }

    # --------------------------------------------------------------
    # Detect intent
    # --------------------------------------------------------------

    fn = _detect_intent(question)

    # --------------------------------------------------------------
    # Unsupported question
    # --------------------------------------------------------------

    if fn is None:
        return {
            "answer": (
                "I couldn't map this question to a supported finance "
                "query. Try asking about amount at risk, financial "
                "impact, most frequent exception types, missing "
                "settlements, reconciled amount, human review, "
                "largest discrepancy, or total exceptions."
            ),
            "supporting_records": [],
            "calculated_metrics": {},
            "confidence": None,
        }

    # --------------------------------------------------------------
    # Execute SAFE DATABASE QUERY
    # --------------------------------------------------------------

    tool_result = fn(
        db,
        batch_id,
    )

    # --------------------------------------------------------------
    # Ask Gemini ONLY for explanation
    # --------------------------------------------------------------

    explanation = _generate_explanation(
        question,
        tool_result,
    )

    # --------------------------------------------------------------
    # Fallback if Gemini is unavailable
    # --------------------------------------------------------------

    used_llm = explanation is not None

    if explanation is None:
        explanation = _format_fallback_answer(
            question,
            tool_result,
        )

    # --------------------------------------------------------------
    # Supporting records
    # --------------------------------------------------------------

    supporting_records = tool_result.get(
        "record_ids",
        [],
    )

    # --------------------------------------------------------------
    # Calculated metrics
    # --------------------------------------------------------------

    calculated_metrics = {
        key: value
        for key, value in tool_result.items()
        if key != "record_ids"
    }

    # --------------------------------------------------------------
    # Final response
    # --------------------------------------------------------------

    return {
        "answer": explanation,
        "supporting_records": supporting_records,
        "calculated_metrics": calculated_metrics,
        "confidence": "high" if used_llm else "medium",
    }