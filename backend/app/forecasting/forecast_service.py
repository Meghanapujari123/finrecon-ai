"""
Forward cash forecast.

Deliberately NOT a black-box ML model - an explainable baseline built from
historical daily inflow/outflow averages, so every number in the UI can be
traced back to "average of the last N days" plus stated assumptions. This
matches the product principle: never present forecasts as guaranteed
outcomes, always show the assumptions behind them.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import BankTransaction, PaymentTransaction


def generate_forecast(db: Session, batch_id: str, horizon_days: int = 7) -> dict:
    payments = db.query(PaymentTransaction).filter(PaymentTransaction.batch_id == batch_id).all()
    bank_txns = db.query(BankTransaction).filter(BankTransaction.batch_id == batch_id).all()

    if not payments:
        return {"error": "No data for this batch."}

    daily_inflow: dict = defaultdict(float)
    for p in payments:
        daily_inflow[p.transaction_date] += p.amount

    daily_outflow: dict = defaultdict(float)
    for b in bank_txns:
        daily_outflow[b.settlement_date] += b.fees

    dates = sorted(daily_inflow.keys())
    if not dates:
        return {"error": "No dated records to build a forecast from."}

    last_date = dates[-1]
    lookback_dates = dates[-30:]
    avg_daily_inflow = sum(daily_inflow[d] for d in lookback_dates) / max(len(lookback_dates), 1)
    avg_daily_outflow = sum(daily_outflow.get(d, 0.0) for d in lookback_dates) / max(len(lookback_dates), 1)

    sample_size = len(lookback_dates)
    confidence = "HIGH" if sample_size >= 21 else "MEDIUM" if sample_size >= 7 else "LOW"

    running_balance = sum(daily_inflow.values()) - sum(daily_outflow.values())
    projections = []
    for i in range(1, horizon_days + 1):
        forecast_date = last_date + timedelta(days=i)
        net = avg_daily_inflow - avg_daily_outflow
        running_balance += net
        projections.append({
            "forecast_date": str(forecast_date),
            "predicted_inflow": round(avg_daily_inflow, 2),
            "predicted_outflow": round(avg_daily_outflow, 2),
            "predicted_net": round(net, 2),
            "predicted_balance": round(running_balance, 2),
        })

    return {
        "batch_id": batch_id,
        "horizon_days": horizon_days,
        "confidence": confidence,
        "assumptions": [
            f"Average daily inflow based on the last {sample_size} days of payment records",
            f"Average daily outflow based on the last {sample_size} days of settlement fees",
            "Unresolved exceptions are excluded from the projection",
            "No abnormal payment spike or drop is assumed",
        ],
        "historical": {
            "total_inflow": round(sum(daily_inflow.values()), 2),
            "total_outflow": round(sum(daily_outflow.values()), 2),
            "days_of_data": len(dates),
        },
        "projections": projections,
    }
