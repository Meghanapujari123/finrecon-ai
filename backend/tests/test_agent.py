from app.agents.investigation_agent import get_investigation_agent
from app.models import ExceptionRecord
from app.services.batch_service import create_demo_batch
from app.services.reconciliation_service import run_reconciliation


def test_agent_degrades_gracefully_without_llm_key(db_session, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()

    batch = create_demo_batch(db_session, n_base=60, seed=11)
    run_reconciliation(db_session, batch.id)
    exc = db_session.query(ExceptionRecord).filter(ExceptionRecord.batch_id == batch.id).first()

    agent = get_investigation_agent()
    result = agent.run(db_session, exc.id)

    assert result["status"] == "UNAVAILABLE"
    db_session.refresh(exc)
    assert exc.ai_status == "UNAVAILABLE"
    # Deterministic exception data must remain intact and usable.
    assert exc.description
    assert exc.exception_type


def test_agent_handles_missing_exception_id(db_session):
    agent = get_investigation_agent()
    result = agent.run(db_session, "does-not-exist")
    assert result["status"] == "FAILED"
