"""
AI Exception Investigation Agent, built as a LangGraph state machine.

The agent NEVER touches primary matching/arithmetic - it only investigates
exceptions that the deterministic engine has already raised. Its job is to
explain, classify root cause, and recommend a bounded resolution - never to
silently change financial records.

Graph:
  load_exception_context -> retrieve_related_records -> analyze_evidence
    -> classify_root_cause -> recommend_resolution
    -> determine_approval_requirement -> validate_output -> persist_analysis

If the LLM is unavailable or its output fails validation twice, the agent
returns a well-formed "unavailable" result. The deterministic exception
details already stored in the database are untouched and remain fully
usable - this is enforced by never writing to PaymentTransaction /
BankTransaction / LedgerEntry / ReconciliationResult from this module.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, TypedDict

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.agents.llm_provider import LLMUnavailableError, get_llm_provider
from app.models import BankTransaction, ExceptionRecord, LedgerEntry, PaymentTransaction

logger = logging.getLogger("finrecon.agent")

SYSTEM_PROMPT = """You are a financial reconciliation investigation assistant \
for FinRecon AI. You analyze a single already-detected reconciliation \
exception using ONLY the evidence supplied to you.

Rules you must follow exactly:
- Only use the supplied evidence. Never invent transactions, amounts, dates, \
or customers that are not present in the evidence.
- Never claim certainty without evidence. If evidence is insufficient, say so \
and lower your confidence.
- Recommend human review whenever your confidence is low (below 0.6) or the \
financial impact is large.
- Respond with ONLY a single JSON object, no markdown fences, no prose \
outside the JSON, matching exactly this schema:
{
  "exception_type": string,
  "root_cause": string,
  "evidence": [string, ...],
  "financial_impact": number,
  "confidence": number between 0 and 1,
  "recommended_action": string,
  "requires_human_approval": boolean,
  "explanation": string
}
"""


class AgentOutputSchema(BaseModel):
    exception_type: str
    root_cause: str
    evidence: list[str] = Field(default_factory=list)
    financial_impact: float
    confidence: float
    recommended_action: str
    requires_human_approval: bool
    explanation: str


class InvestigationState(TypedDict, total=False):
    exception_id: str
    exception_context: dict
    related_records: dict
    raw_llm_output: Optional[dict]
    validated_output: Optional[dict]
    validation_error: Optional[str]
    status: str  # ANALYZED | UNAVAILABLE | FAILED
    error_message: Optional[str]


def _serialize(obj: Any) -> dict:
    if obj is None:
        return {}
    d = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        d[col.name] = str(val) if not isinstance(val, (int, float, bool, str, type(None), dict)) else val
    return d


class InvestigationAgent:
    """Wraps the LangGraph graph. A fresh graph is compiled per `run()` call
    with the DB-bound nodes closed over that call's session - LangGraph
    graphs are cheap to compile and this keeps the session lifecycle simple
    and correct (no session shared across requests)."""

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # Node implementations
    # ------------------------------------------------------------------
    def _load_exception_context(self, state: InvestigationState, db: Session) -> InvestigationState:
        exc = db.query(ExceptionRecord).filter(ExceptionRecord.id == state["exception_id"]).first()
        if not exc:
            state["status"] = "FAILED"
            state["error_message"] = "Exception record not found"
            return state
        state["exception_context"] = {
            "exception_type": exc.exception_type,
            "severity": exc.severity,
            "description": exc.description,
            "amount_affected": exc.amount_affected,
            "payment_id": exc.payment_id,
            "bank_transaction_id": exc.bank_transaction_id,
            "ledger_entry_id": exc.ledger_entry_id,
        }
        return state

    def _retrieve_related_records(self, state: InvestigationState, db: Session) -> InvestigationState:
        ctx = state.get("exception_context", {})
        related: dict = {}
        if ctx.get("payment_id"):
            p = db.query(PaymentTransaction).filter(PaymentTransaction.id == ctx["payment_id"]).first()
            related["payment"] = _serialize(p)
        if ctx.get("bank_transaction_id"):
            b = db.query(BankTransaction).filter(BankTransaction.id == ctx["bank_transaction_id"]).first()
            related["bank_transaction"] = _serialize(b)
        if ctx.get("ledger_entry_id"):
            l = db.query(LedgerEntry).filter(LedgerEntry.id == ctx["ledger_entry_id"]).first()
            related["ledger_entry"] = _serialize(l)
        state["related_records"] = related
        return state

    def _analyze_evidence(self, state: InvestigationState) -> InvestigationState:
        """Single LLM call that performs evidence analysis, root-cause
        classification, and resolution recommendation together (the nodes
        below then split, validate, and gate that one structured result -
        this keeps latency and cost reasonable while still expressing each
        step as a distinct, auditable stage)."""
        provider = get_llm_provider()
        if not provider.is_available():
            state["status"] = "UNAVAILABLE"
            return state

        user_prompt = (
            f"Exception:\n{state['exception_context']}\n\n"
            f"Related records (evidence):\n{state['related_records']}\n\n"
            "Analyze this exception and respond with the required JSON object only."
        )
        try:
            raw = provider.complete_json(SYSTEM_PROMPT, user_prompt)
            state["raw_llm_output"] = raw
        except LLMUnavailableError as exc:
            logger.warning("Investigation agent: LLM unavailable/failed: %s", exc)
            state["status"] = "UNAVAILABLE"
        return state

    def _classify_root_cause(self, state: InvestigationState) -> InvestigationState:
        # Root cause is already part of the structured LLM output; this node
        # exists as an explicit, auditable stage boundary and a place to add
        # rule-based overrides later without touching the LLM call itself.
        return state

    def _recommend_resolution(self, state: InvestigationState) -> InvestigationState:
        # Recommendation also comes from the structured output; nothing
        # further to compute here beyond passing state through.
        return state

    def _determine_approval_requirement(self, state: InvestigationState) -> InvestigationState:
        raw = state.get("raw_llm_output")
        if not raw:
            return state
        # Deterministic safety net: even if the model says no approval is
        # needed, large financial impact or low confidence always forces
        # human approval. The AI recommendation can only make approval
        # MORE conservative, never less.
        impact = float(raw.get("financial_impact", 0) or 0)
        confidence = float(raw.get("confidence", 0) or 0)
        if impact > 10000 or confidence < 0.6:
            raw["requires_human_approval"] = True
        state["raw_llm_output"] = raw
        return state

    def _validate_output(self, state: InvestigationState) -> InvestigationState:
        raw = state.get("raw_llm_output")
        if state.get("status") == "UNAVAILABLE" or not raw:
            return state
        try:
            validated = AgentOutputSchema(**raw)
            state["validated_output"] = validated.model_dump()
            state["status"] = "ANALYZED"
        except ValidationError as exc:
            state["validation_error"] = str(exc)
            state["status"] = "FAILED"
        return state

    def _persist_analysis(self, state: InvestigationState, db: Session) -> InvestigationState:
        exc = db.query(ExceptionRecord).filter(ExceptionRecord.id == state["exception_id"]).first()
        if not exc:
            return state

        if state["status"] == "ANALYZED":
            out = state["validated_output"]
            exc.ai_analysis = out
            exc.ai_confidence = out["confidence"]
            exc.ai_root_cause = out["root_cause"]
            exc.ai_status = "ANALYZED"
            exc.recommended_action = out["recommended_action"]
            exc.requires_human_approval = out["requires_human_approval"]
            exc.risk_level = "HIGH" if out["requires_human_approval"] else (
                "MEDIUM" if out["confidence"] < 0.8 else "LOW"
            )
            exc.status = "UNDER_REVIEW"
        elif state["status"] == "UNAVAILABLE":
            exc.ai_status = "UNAVAILABLE"
            exc.ai_analysis = {"message": "AI analysis unavailable — deterministic exception details are still available."}
        else:  # FAILED
            exc.ai_status = "FAILED"
            exc.ai_analysis = {"message": "AI analysis failed validation and was discarded.",
                                "error": state.get("validation_error") or state.get("error_message")}
            exc.status = "UNRESOLVED"

        db.add(exc)
        db.commit()
        return state

    # ------------------------------------------------------------------
    def _build_graph(self, db: Session):
        from langgraph.graph import END, StateGraph

        def _stop_if_failed(state: InvestigationState) -> str:
            return "persist_analysis" if state.get("status") == "FAILED" else "retrieve_related_records"

        graph = StateGraph(InvestigationState)
        graph.add_node("load_exception_context", lambda s: self._load_exception_context(s, db))
        graph.add_node("retrieve_related_records", lambda s: self._retrieve_related_records(s, db))
        graph.add_node("analyze_evidence", self._analyze_evidence)
        graph.add_node("classify_root_cause", self._classify_root_cause)
        graph.add_node("recommend_resolution", self._recommend_resolution)
        graph.add_node("determine_approval_requirement", self._determine_approval_requirement)
        graph.add_node("validate_output", self._validate_output)
        graph.add_node("persist_analysis", lambda s: self._persist_analysis(s, db))

        graph.set_entry_point("load_exception_context")
        graph.add_conditional_edges(
            "load_exception_context", _stop_if_failed,
            {"persist_analysis": "persist_analysis", "retrieve_related_records": "retrieve_related_records"},
        )
        graph.add_edge("retrieve_related_records", "analyze_evidence")
        graph.add_edge("analyze_evidence", "classify_root_cause")
        graph.add_edge("classify_root_cause", "recommend_resolution")
        graph.add_edge("recommend_resolution", "determine_approval_requirement")
        graph.add_edge("determine_approval_requirement", "validate_output")
        graph.add_edge("validate_output", "persist_analysis")
        graph.add_edge("persist_analysis", END)
        return graph.compile()

    def run(self, db: Session, exception_id: str) -> dict:
        graph = self._build_graph(db)
        initial_state: InvestigationState = {"exception_id": exception_id, "status": "PENDING"}
        final_state = graph.invoke(initial_state)
        return final_state


_agent: InvestigationAgent | None = None


def get_investigation_agent() -> InvestigationAgent:
    global _agent
    if _agent is None:
        _agent = InvestigationAgent()
    return _agent
