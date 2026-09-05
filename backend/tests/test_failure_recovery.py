import io

from fastapi.testclient import TestClient

from app.main import app


def test_reconciliation_on_batch_with_no_data_does_not_crash(db_session):
    from app.services.reconciliation_service import run_reconciliation
    from app.models import Batch

    batch = Batch(id="empty-batch", label="empty", source="upload")
    db_session.add(batch)
    db_session.commit()

    result = run_reconciliation(db_session, "empty-batch")
    assert result["total_records"] == 0
    assert "error" in result


def test_csv_upload_rejects_missing_columns():
    with TestClient(app) as client:
        bad_csv = "wrong_col,other\n1,2\n"
        files = {"payments_csv": ("payments.csv", io.BytesIO(bad_csv.encode()), "text/csv")}
        r = client.post("/api/batches/upload", params={"label": "bad upload"}, files=files)
        assert r.status_code == 400
        assert "missing required columns" in r.json()["detail"]


def test_csv_upload_rejects_invalid_amount():
    with TestClient(app) as client:
        csv_text = "transaction_id,customer_id,amount,transaction_date\nT1,C1,not_a_number,2026-06-01\n"
        files = {"payments_csv": ("payments.csv", io.BytesIO(csv_text.encode()), "text/csv")}
        r = client.post("/api/batches/upload", params={"label": "bad amount"}, files=files)
        assert r.status_code == 400


def test_csv_upload_succeeds_with_valid_data():
    with TestClient(app) as client:
        csv_text = "transaction_id,customer_id,amount,transaction_date\nT1,C1,1000,2026-06-01\n"
        files = {"payments_csv": ("payments.csv", io.BytesIO(csv_text.encode()), "text/csv")}
        r = client.post("/api/batches/upload", params={"label": "good upload"}, files=files)
        assert r.status_code == 200
        assert r.json()["source"] == "upload"


def test_demo_batch_rejects_undersized_hackathon_requirement():
    with TestClient(app) as client:
        r = client.post("/api/batches/demo", params={"n_base": 10, "seed": 1})
        assert r.status_code == 400


def test_investigate_unknown_exception_returns_404():
    with TestClient(app) as client:
        r = client.post("/api/exceptions/does-not-exist/investigate")
        assert r.status_code == 404


def test_resolve_unknown_exception_returns_404():
    with TestClient(app) as client:
        r = client.post("/api/exceptions/does-not-exist/resolve", json={"action": "APPROVE", "actor": "t"})
        assert r.status_code == 404


def test_evaluation_without_data_returns_400():
    with TestClient(app) as client:
        r = client.post("/api/evaluation/run", params={"batch_id": "no-such-batch"})
        assert r.status_code == 400
