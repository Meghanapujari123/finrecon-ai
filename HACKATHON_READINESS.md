# FinRecon AI — Hackathon Readiness

Razorpay AI Buildathon — Track 04: AI Finance Controller

## 1. Product summary

FinRecon AI reconciles payment gateway, bank settlement, and accounting
ledger records for a batch of transactions, deterministically matches what
it can, flags what it can't, investigates the exceptions with an AI agent,
and requires a human to approve anything before it's marked resolved.

## 2. Problem statement

Finance operations teams manually reconcile payments against bank
settlements and internal ledgers. This is slow, error-prone, and produces
no audit trail. Naively pointing an LLM at the whole problem produces
unverifiable numbers and silent hallucination risk on financial data.

## 3. Solution

Split the problem in two: deterministic software does the arithmetic and
primary matching (verifiable, fast, 100% reproducible); AI does the part
that genuinely needs judgment — investigating *why* an exception happened
and what a reasonable next step looks like — and is bounded by schema
validation, a human-approval gate, and graceful degradation if unavailable.

## 4. Architecture

See `backend/ARCHITECTURE.md` for the full data-flow diagram and reasoning.
Short version: Ingestion → Deterministic Reconciliation Engine → Exceptions
→ AI Investigation (LangGraph) → Human Approval → Audit Trail → Evaluation.

## 5. Technical architecture

FastAPI + SQLAlchemy 2.0 + Pydantic v2 backend, React + TypeScript +
Tailwind + Recharts frontend, LangGraph for agent orchestration, Postgres
in Docker / SQLite for zero-setup local dev (identical models either way).

## 6. Key innovation

The evaluation framework scores the system against synthetic
ground-truth labels it generated itself, so "96.6% precision, 100% recall"
isn't a claim — it's a number anyone can reproduce with
`python scripts/run_evaluation.py --create-demo --n 150 --seed 42`
and get the same answer, because the seed is deterministic and the
matching engine has no LLM in it.

## 7. Why deterministic logic is used (for matching)

Amount/date/reference matching is a well-specified lookup problem, not a
judgment problem. Using an LLM for it would make results non-reproducible,
slower, and would make the accuracy metrics meaningless (you can't
benchmark a system against itself if the system's core logic is
stochastic). See `backend/ARCHITECTURE.md` for the full rationale.

## 8. Where AI is used

- Exception investigation (root cause + recommended action), gated by a
  Pydantic schema and a deterministic approval-requirement safety net
- Finance Q&A explanation layer (wraps DB-sourced numbers in plain English)

Both are designed so the system is *strictly more useful* with AI
available and *still fully functional* without it.

## 9. AI agent workflow

LangGraph state machine:
`load_exception_context → retrieve_related_records → analyze_evidence →
classify_root_cause → recommend_resolution →
determine_approval_requirement → validate_output → persist_analysis`

## 10. Evaluation methodology

Every synthetic record with an injected problem carries a
`ground_truth_label`. After reconciliation runs, `app/evaluation/evaluator.py`
compares what was actually flagged (and how it was classified) against
those labels to compute precision, recall, F1, accuracy, false
positive/negative counts, and classification accuracy — see
`backend/ARCHITECTURE.md` and the module's own docstring for the exact
definitions used.

## 11. Actual evaluation results

From a representative run (`n_base=150, seed=42`, 156 total payment
records after duplicate injection):

| Metric | Value |
|---|---|
| Dataset size | 156 |
| Match accuracy | 98.7% |
| Precision | 96.6% |
| Recall | 100.0% |
| F1 | 98.3% |
| False positives | 2 |
| False negatives | 0 |
| Exception classification accuracy | 94.7% |
| Match rate (matched vs. exception) | 62.2% |
| Throughput | ~1,000–1,400 records/sec (in-process, SQLite, this sandbox) |

These numbers come from an actual run in this environment
(`backend/evaluation_report.json` when regenerated) — re-run the script
above to reproduce them yourself. Match rate is intentionally in the
60–70% band because the synthetic dataset deliberately injects a high
density of problems (per the brief's target distribution) to stress-test
exception handling, not to make the headline number look good.

## 12. Failure handling

See `backend/FAILURE_RECOVERY.md` for the full table (14 failure modes,
detection method, recovery behavior, user-visible effect, data-safety
notes). Headline guarantee: the deterministic reconciliation engine has
zero dependency on the LLM provider and is verified by automated tests to
keep working, with full exception data intact, when no LLM key is
configured.

## 13. Human approval model

Every `ExceptionRecord` carries `requires_human_approval`. The AI agent's
own recommendation can only push this *more* conservative (via a
deterministic override: financial impact > ₹10,000 or confidence < 0.6
forces approval regardless of what the model said) — never less. Approving,
rejecting, requesting further investigation, or marking unresolved are the
only ways to change an exception's terminal state, each producing an
`AuditLog` entry, and each is idempotent (a resolution cannot be
double-applied — verified by test).

## 14. Security

- No secrets in source; all config via environment variables, `.env.example` provided, `.env` gitignored
- CORS restricted to configured origins
- CSV upload: file-size limit, row-count limit, required-column validation, per-value type validation, whole-file rejection on any bad row (no silent partial load)
- No arbitrary SQL execution anywhere — Finance Q&A is routed through a fixed set of parameterized query functions, never raw/LLM-generated SQL
- Pydantic validation on every request/response boundary

## 15. Known limitations

Stated plainly, in keeping with the product's own "don't hide failures"
principle:

- The frontend has not had a dedicated multi-pass visual-polish cycle —
  it's functional, dense, and fully wired to live data rather than
  pixel-perfect. All 7 required pages exist and work.
- CSV upload accepts one file per source type per request; there's no
  drag-and-drop multi-file batching UI yet, only the API + a basic flow.
- `Base.metadata.create_all` is used for zero-setup schema creation;
  Alembic is included as a dependency for a real migration path but no
  migration has been authored yet — needed before pointing this at a
  persistent production database.
- The AI agent's graceful-degradation path (no LLM key) is fully verified
  by automated tests and a live run in this environment. Its behavior with
  a real Anthropic API key follows the identical code path and JSON-schema
  validation, but was not exercised against a live key in this sandbox
  (no outbound network access to the Anthropic API here).
- Docker Compose has been written and reviewed carefully but not build-
  tested in this environment (no Docker daemon available here) — the
  underlying backend and frontend have both been build/test-verified
  independently.

## 16. Demo flow

1. Load Demo Dataset (150+ records, one click)
2. Run Full Reconciliation (deterministic engine, sub-200ms for 150 records)
3. Overview shows match rate, exceptions, amount affected, throughput
4. Open an exception → Run AI Investigation → see root cause + recommendation
   (or the honest "AI analysis unavailable" message if no key is set)
5. Approve / Reject / Request Investigation → Audit Trail shows the event
6. Evaluation page shows real precision/recall/F1 against ground truth,
   plus an explicit "exceptions we could not confidently resolve" list

## 17. 60-second pitch

Finance teams reconcile payments against bank and ledger records by hand.
FinRecon AI automates the part that's actually mechanical — matching
amounts, dates, and references — with fully deterministic, auditable
logic, and uses AI only where judgment genuinely helps: investigating why
an exception happened and recommending a bounded next step, always subject
to human approval before anything is marked resolved. Every metric on the
dashboard is computed live against ground truth, not hardcoded, and the
system is built to say "I couldn't confidently resolve this" rather than
guess.

## 18. 3-minute pitch

Start with the problem: reconciliation is manual, slow, and produces no
audit trail, and naive "point an LLM at it" approaches make the numbers
unverifiable. FinRecon AI splits the problem: a deterministic five-level
matching engine handles arithmetic and primary matching — exact reference,
invoice+customer+amount, amount+date tolerance, customer+amount proximity,
and a narrowly bounded fuzzy match — producing evidence-backed matches or
one of nine specific exception types. Nothing here touches an LLM, which
is why the accuracy numbers on the Evaluation page are reproducible: run
`scripts/run_evaluation.py` with the same seed and get the same 96%+
precision every time. Exceptions the engine can't resolve go to a
LangGraph-orchestrated investigation agent that only ever sees the
evidence already in the database, is schema-validated on every output, and
is subject to a hard-coded safety net that forces human approval whenever
financial impact or confidence crosses a threshold — the AI can only make
approval *more* conservative, never less. If no LLM key is configured, or
the model fails validation twice, the system degrades gracefully: the
deterministic exception data stays fully intact and usable, and the UI
says so plainly instead of showing a broken panel. Every resolution is
audited and idempotent. The Evaluation page shows real precision, recall,
F1, and — deliberately — an "exceptions we could not confidently resolve"
section, because refusing to guess is a feature, not a gap.

## 19. Judge FAQ

**Is the AI actually doing anything, or is it decoration?**
It investigates exceptions the deterministic engine already found and
can't resolve on its own — classifying root cause and recommending a
bounded action from evidence it's explicitly told not to go beyond. Turn
off the API key and the rest of the product (matching, exceptions,
evaluation, audit) is unaffected; that's the point.

**How do I know the accuracy numbers aren't cherry-picked?**
Re-run `scripts/run_evaluation.py --create-demo --n 150 --seed 42` — same
seed, same synthetic data, same deterministic engine, same numbers. The
dataset generator's scenario distribution is in `app/services/data_generator.py`,
not hidden.

**What happens with bad input data?**
See `backend/FAILURE_RECOVERY.md`. Short answer: reject the whole upload
with a specific error rather than silently loading partial/bad financial
data.

**Can the AI silently change financial records?**
No — the agent writes only to `ExceptionRecord.ai_*` fields. Approving,
rejecting, or marking unresolved is a separate, human-triggered,
audited, idempotent action.

## 20. Future improvements

- Alembic migration authored for the Postgres schema
- Multi-file CSV upload UI with per-file preview before commit
- Configurable approval thresholds per exception type/severity
- Additional LLM provider implementations (OpenAI, local models) behind
  the existing `LLMProvider` abstraction
- Role-based access control on resolution actions (currently free-text `actor`)
- Streaming/paginated exception lists for very large batches
