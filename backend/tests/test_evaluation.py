from app.services.batch_service import create_demo_batch
from app.services.reconciliation_service import run_reconciliation
from app.evaluation.evaluator import run_evaluation


def test_evaluation_scores_are_reasonable_on_demo_data(db_session):
    batch = create_demo_batch(db_session, n_base=150, seed=42)
    run_reconciliation(db_session, batch.id)
    result = run_evaluation(db_session, batch.id)

    assert result["dataset_size"] >= 150
    # These are sanity bounds, not hardcoded outputs - the engine must
    # genuinely perform well on the synthetic ground truth, not just return
    # a fixed number.
    assert 0.0 <= result["precision"] <= 1.0
    assert 0.0 <= result["recall"] <= 1.0
    assert 0.0 <= result["f1"] <= 1.0
    assert result["recall"] > 0.9  # engine must catch the vast majority of true exceptions
    assert result["false_negative_count"] >= 0


def test_evaluation_without_reconciliation_run_errors(db_session):
    batch = create_demo_batch(db_session, n_base=60, seed=7)
    result = run_evaluation(db_session, batch.id)
    assert "error" in result


def test_reconciliation_run_is_idempotent_on_rerun(db_session):
    batch = create_demo_batch(db_session, n_base=60, seed=1)
    first = run_reconciliation(db_session, batch.id)
    second = run_reconciliation(db_session, batch.id)
    # Re-running must not double the records - old results are cleared first.
    assert first["total_records"] == second["total_records"]
