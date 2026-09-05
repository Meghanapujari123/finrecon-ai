import uuid
from datetime import date, datetime

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy import Date as SADate
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    actor: Mapped[str] = mapped_column(String(100))  # "system" | "ai_agent" | user id/name
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(100))
    previous_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(String(36), index=True)
    forecast_date: Mapped[date] = mapped_column(SADate)
    predicted_inflow: Mapped[float] = mapped_column(Float)
    predicted_outflow: Mapped[float] = mapped_column(Float)
    predicted_balance: Mapped[float] = mapped_column(Float)
    confidence: Mapped[str] = mapped_column(String(10))  # LOW | MEDIUM | HIGH
    assumptions: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
