# FinRecon AI

AI Finance Controller for Reconciliation, Investigation & Revenue Intelligence.
Built for the Razorpay AI Buildathon — Track 04: AI Finance Controller.

FinRecon AI reconciles payment gateway, bank settlement, and accounting
ledger records deterministically, surfaces exceptions the arithmetic can't
resolve, investigates those exceptions with an AI agent, and requires human
approval before anything gets marked resolved. Every number in the UI is
computed live from the database — nothing is hardcoded, and the system says
"I could not confidently resolve this" instead of hiding failures.

## What's implemented

- Deterministic multi-level reconciliation engine (no LLM in the matching path)
- Synthetic data generator with ground-truth labels (150+ records, reproducible via seed)
- Evaluation framework scoring precision/recall/F1/accuracy against that ground truth
- LangGraph AI investigation agent with graceful degradation when no LLM key is configured
- Human-in-the-loop resolution workflow (idempotent — a resolution can't be applied twice)
- Finance Q&A with safe, parameterized query tools (numbers always come from the DB)
- Explainable cash forecast (historical-average baseline, not a black box)
- Full audit trail for every state change
- CSV upload with validation, plus one-click demo data
- React/TypeScript/Tailwind dashboard covering all of the above

## Project structure

```
backend/    FastAPI + SQLAlchemy + LangGraph backend
frontend/   React + TypeScript + Tailwind + Recharts frontend
docker-compose.yml
```

See `backend/ARCHITECTURE.md` and `backend/FAILURE_RECOVERY.md` for deeper
detail, and `HACKATHON_READINESS.md` for the judge-facing summary.

## Quick start (no Docker required)

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # SQLite by default - works with zero setup
uvicorn app.main:app --reload --port 8000
```

The API is now at `http://localhost:8000`. Interactive OpenAPI docs are at
`http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env            # points at http://localhost:8000 by default
npm run dev
```

Open `http://localhost:5173`, click **Load Demo Dataset** in the top bar,
then **Run Full Reconciliation** on the Overview page.

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env   # add ANTHROPIC_API_KEY if you want live AI analysis
docker compose up --build
```

- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000` (docs at `/docs`)
- Postgres: `localhost:5432` (user/pass/db: `finrecon`)

Docker Compose runs against Postgres; local dev without Docker uses SQLite
by default — both paths use the exact same SQLAlchemy models and code.

## Environment variables

See `backend/.env.example` for the full list. The only one that changes
behavior meaningfully is `ANTHROPIC_API_KEY`: leave it blank and the AI
investigation agent and Q&A explanations degrade gracefully (deterministic
reconciliation and exception data are unaffected either way).

## Loading data

- **Demo dataset**: click "Load Demo Dataset" in the UI, or
  `POST /api/batches/demo?n_base=150&seed=42`, or
  `python backend/scripts/generate_demo_data.py --n 150 --seed 42`
- **Your own data**: CSV upload via `POST /api/batches/upload` (or the
  Reconciliation page once you wire in an upload form) with columns:
  - payments: `transaction_id, customer_id, invoice_id, amount, transaction_date[, currency, status, payment_method]`
  - bank: `bank_reference, transaction_id, amount, settlement_date[, status, fees]`
  - ledger: `ledger_reference, invoice_id, customer_id, expected_amount, recorded_amount[, tax_amount, date, status]`

## Running tests

```bash
cd backend
source venv/bin/activate
pytest -v
```

27 tests cover every exception category the deterministic engine detects,
evaluation scoring, resolution idempotency, AI-agent graceful degradation,
and failure-recovery edge cases (malformed CSV, missing columns, empty
batches, double-resolution attempts, unknown IDs).

## Running evaluation standalone

```bash
cd backend
python scripts/run_evaluation.py --create-demo --n 150 --seed 42
```

Writes `evaluation_report.json` with the same real, ground-truth-scored
metrics the Evaluation page shows.

## Known limitations

Being direct about this, in the same spirit as the product itself:

- The frontend covers all seven required pages and is fully wired to the
  live API, but has not had a dedicated multi-pass visual polish cycle —
  expect it to be functional and information-dense rather than
  pixel-perfect.
- CSV upload currently expects one file per source type in a single
  request; there's no multi-file batching UI yet.
- Alembic is included as a dependency for production migrations, but the
  demo path uses `Base.metadata.create_all` for zero-setup startup — add a
  real migration before using this against a persistent production database.
- The AI investigation agent has been verified end-to-end in its graceful
  degradation path (no LLM key). Its behavior with a live Anthropic key
  follows the same code path and JSON-schema validation, but has not been
  exercised with a real API key in this environment.
