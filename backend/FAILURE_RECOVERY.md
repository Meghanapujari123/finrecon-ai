# FinRecon AI — Failure Recovery

Each row: what can go wrong, how the system detects it, what it does about
it, what the user sees, and any data-safety notes.

| Failure | Detection | Recovery | User-visible behavior | Data safety |
|---|---|---|---|---|
| Malformed CSV (bad encoding, no header) | `csv.DictReader` + explicit header check in `app/api/batches.py` | Request rejected before any row is parsed | `400` with the filename and reason | No partial batch is created |
| Missing required CSV columns | Column-name check against a required list per file type | Request rejected with the exact missing columns listed | `400: "<file> missing required columns: [...]"` | No partial batch is created |
| Invalid amount/date values in a CSV row | `float()`/date-parsing wrapped in try/except during row conversion | Whole upload rejected (not silently skipped) — a partially-valid financial batch is worse than no batch | `400: CSV validation error: <detail>` | No partial batch is created |
| Duplicate rows in upload | Not deduplicated at upload time; the reconciliation engine's `_detect_duplicates` catches duplicate payments post-load | Flagged as `DUPLICATE_TRANSACTION` exceptions, not silently merged or dropped | Shows up in Exceptions page, requires human resolution | Original rows preserved; nothing auto-deleted |
| Empty dataset / batch with zero payments | `run_reconciliation` checks `if not payments` before doing any work | Returns a structured result with `error` set instead of dividing by zero or crashing | `total_records: 0`, explicit error message | No exceptions or results are fabricated |
| Database unavailable at startup | SQLAlchemy engine connection attempted on first query; Docker Compose `depends_on: condition: service_healthy` on Postgres | Backend container won't start serving traffic until Postgres passes its healthcheck | Compose reports the backend as unhealthy/restarting rather than serving broken responses | N/A |
| LLM unavailable (no key configured) | `LLMProvider.is_available()` checked before every call | Investigation agent returns `status=UNAVAILABLE` and stores `"AI analysis unavailable — deterministic exception details are still available."`; Q&A falls back to the raw computed number | UI shows the deterministic exception details in full, with an explicit "AI analysis unavailable" note instead of a blank/broken panel | Exception's deterministic fields are never touched |
| LLM timeout | `LLM_REQUEST_TIMEOUT_SECONDS` on the Anthropic client | Caught as part of the retry-once-then-fail path in `LLMProvider._call_anthropic` | Same as "LLM unavailable" above | Same |
| Invalid LLM JSON output | `json.loads` wrapped; on failure, one retry is attempted | If still invalid after retry, `LLMUnavailableError` is raised and the agent records `ai_status=FAILED` with the validation error, and sets the exception to `UNRESOLVED` | Exception shown as `UNRESOLVED` with the failure reason visible, not silently marked analyzed | No fabricated analysis is ever persisted |
| Duplicate resolution request (double-click, retry) | `apply_resolution` checks current status against `{"RESOLVED", "REJECTED"}` before applying | Raises `AlreadyResolvedError`; API returns `409` | UI shows "already resolved" message, exception state unchanged | Guarantees a resolution is applied at most once |
| Partial processing failure mid-reconciliation | Reconciliation results/exceptions for a batch are cleared and rewritten inside a single service call; SQLAlchemy session commit is the atomic boundary | An exception during `run()` propagates before `db.commit()`, so no partial batch of results is committed | `500` (surfaced by FastAPI's default handler) rather than a half-written dashboard | Prior run's results remain intact until the new run successfully commits |
| Empty dataset passed to forecast/evaluation | Explicit `if not payments` / `if not results` checks in `forecast_service.py` and `evaluator.py` | Returns `{"error": "..."}" instead of crashing | `400` with a clear "run reconciliation first" / "no data for this batch" message | N/A |
| Extremely large amount (data entry error) | No hard cap is enforced on amount today — flagged here as a known gap | Would currently pass through as a very large `AMOUNT_MISMATCH`/`UNKNOWN_UNRESOLVABLE` exception rather than crashing anything, since all amount math is `float` arithmetic with no overflow risk at realistic scales | Shows up as an unusually large exception in the UI, sorted to the top when ordering by amount | No silent truncation |
| Unknown/unrecognized exception type | The engine's exception vocabulary is a closed enum (`ExceptionType`); anything it can't classify into one of the 8 specific categories is emitted as `UNKNOWN_UNRESOLVABLE` rather than omitted | N/A — this is the designed fallback | Explicitly visible as "unknown/unresolvable" rather than disappearing | The record and its evidence are always persisted |
| Unknown exception/batch ID in an API call | Explicit DB lookups return `None`, checked before use | `404` with a clear message | N/A | N/A |
| Re-running reconciliation on the same batch | `run_reconciliation` deletes prior `ReconciliationResult`/`ExceptionRecord` rows for that `batch_id` before inserting new ones | Re-running never doubles counts | Dashboard reflects only the latest run | Previous AI investigations and resolutions on regenerated exceptions are naturally reset — documented here as expected behavior, not a bug |

## What is explicitly NOT auto-recovered

- A CSV upload with any invalid row is rejected wholesale rather than
  "recovering" by silently dropping bad rows — for financial data, a
  partially-loaded batch is more dangerous than a rejected one.
- The AI agent never retries by itself beyond the single retry described
  above; further retries are a deliberate human action (re-running
  "Investigate" from the Exceptions page).
- A resolution, once applied, is never automatically reversed by the
  system — reversal (if ever needed) would be a separate, explicitly
  human-triggered and audited action, not built into this version.

## Core guarantee

The deterministic reconciliation engine has zero dependency on the LLM
provider, the AI agent module, or network access to any external API. It
is exercised directly by `tests/test_reconciliation_engine.py` with no
mocking of an LLM required, and `tests/test_agent.py` explicitly verifies
that with no LLM key configured, reconciliation and exception data remain
fully populated and queryable.
