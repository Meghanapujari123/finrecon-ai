# FinRecon AI — Architecture

## Design principle

Deterministic software owns arithmetic and primary matching. AI owns
investigation, explanation, and bounded recommendation. The two never swap
roles: the reconciliation engine (`app/reconciliation/matcher.py`) has no
LLM call anywhere in it, and the AI agent (`app/agents/investigation_agent.py`)
never writes to `PaymentTransaction`, `BankTransaction`, `LedgerEntry`, or
`ReconciliationResult` — only to the `ai_*` fields on `ExceptionRecord`.

## Data flow

```
CSV upload / demo generator
        |
        v
   Batch (payments, bank_transactions, ledger_entries)
        |
        v
Deterministic Reconciliation Engine (app/reconciliation/matcher.py)
        |
        +--> ReconciliationResult (matched or exception, with evidence)
        +--> ExceptionRecord (one per detected issue, status=OPEN)
        |
        v
AI Investigation Agent (LangGraph, app/agents/investigation_agent.py)
   [only runs against already-detected exceptions, on request]
        |
        v
ExceptionRecord updated: ai_analysis, ai_confidence, root_cause,
recommended_action, requires_human_approval, status=UNDER_REVIEW
        |
        v
Human-in-the-loop resolution (app/services/resolution_service.py)
   APPROVE / REJECT / REQUEST_INVESTIGATION / MARK_UNRESOLVED
   -> idempotent, writes AuditLog
        |
        v
Evaluation (app/evaluation/evaluator.py) scores everything above
against the dataset's ground-truth labels
```

## Why deterministic logic for matching

Reconciliation is a well-specified arithmetic and lookup problem: does an
amount equal another amount, is a date within tolerance, does a reference
ID match. An LLM adds latency, cost, and non-determinism to a problem that
doesn't need judgment — and makes the accuracy numbers on the Evaluation
page unverifiable ("trust me" instead of "run it again and get the same
answer"). The matching hierarchy is:

1. Exact transaction/reference ID
2. Invoice ID + customer ID + exact amount
3. Invoice ID + amount + date within `DATE_TOLERANCE_DAYS`
4. Customer ID + amount + date proximity
5. Controlled fuzzy match (small amount tolerance, plausible date window) —
   used only when nothing above matched

Every match records its method, confidence, and evidence, so a human can
audit *why* two records were linked.

## Where AI is used, and why

- **Exception investigation** (LangGraph agent): once the deterministic
  engine has already flagged something it can't resolve, the agent explains
  likely root cause and recommends a bounded next step. This is a genuine
  reasoning task — matching evidence across records to a plausible
  narrative — that arithmetic can't do.
- **Finance Q&A**: intent is routed to one of a small set of safe,
  parameterized SQL-backed tools. The LLM only wraps the *already-computed*
  number in a sentence; it never sees write access and never invents a
  figure. If the LLM is unavailable, the raw computed value is still
  returned.
- **Cash forecast**: deliberately *not* AI — an explainable baseline
  (historical daily averages) so every number traces back to "average of
  the last N days," not a black box.

## AI agent graph (LangGraph)

```
load_exception_context -> retrieve_related_records -> analyze_evidence
   -> classify_root_cause -> recommend_resolution
   -> determine_approval_requirement -> validate_output -> persist_analysis
```

`analyze_evidence` is the only node that calls the LLM; the surrounding
nodes are explicit, auditable stage boundaries. `determine_approval_requirement`
is a deterministic safety net: if financial impact exceeds a threshold or
confidence is below 0.6, human approval is forced regardless of what the
model recommended — the AI can only make the approval requirement *more*
conservative, never less. `validate_output` runs the model's JSON through a
Pydantic schema; invalid output is retried once by the LLM provider and, if
still invalid, the exception is marked `UNRESOLVED` rather than silently
accepted.

## Graceful degradation

If `ANTHROPIC_API_KEY` (or the configured provider's key) is absent, empty,
or the call fails twice, `LLMProvider.is_available()` returns `False` and
every AI-backed feature returns a well-formed "unavailable" result instead
of raising. This is enforced by automated tests
(`tests/test_agent.py::test_agent_degrades_gracefully_without_llm_key`) —
the deterministic reconciliation, exception, and evaluation data remain
100% intact and usable in this state.

## Idempotency

- **Reconciliation re-runs**: `run_reconciliation` clears prior
  `ReconciliationResult`/`ExceptionRecord` rows for the batch before
  re-inserting, so re-running never doubles records.
- **Resolutions**: `apply_resolution` raises `AlreadyResolvedError` if the
  exception is already `RESOLVED` or `REJECTED` — a resolution can never be
  applied twice, even under retry.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React, TypeScript, Tailwind CSS, Recharts, React Router |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.0 |
| Database | PostgreSQL (Docker) / SQLite (local dev) — same models, swapped via `DATABASE_URL` |
| AI orchestration | LangGraph |
| LLM provider | Pluggable via `LLM_PROVIDER` env var (Anthropic implemented) |
| Testing | Pytest (27 tests: engine, evaluation, resolution, agent, failure recovery) |
| Infra | Docker Compose (frontend, backend, Postgres) |
