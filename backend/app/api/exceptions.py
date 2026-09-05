from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.investigation_agent import get_investigation_agent
from app.database import get_db
from app.models import ExceptionRecord
from app.schemas.schemas import ExceptionOut, ResolutionRequest
from app.services.resolution_service import AlreadyResolvedError, ExceptionNotFoundError, apply_resolution

router = APIRouter(prefix="/api/exceptions", tags=["exceptions"])


@router.get("", response_model=list[ExceptionOut])
def list_exceptions(
    batch_id: str,
    exception_type: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    requires_human_approval: bool | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(ExceptionRecord).filter(ExceptionRecord.batch_id == batch_id)
    if exception_type:
        q = q.filter(ExceptionRecord.exception_type == exception_type)
    if severity:
        q = q.filter(ExceptionRecord.severity == severity)
    if status:
        q = q.filter(ExceptionRecord.status == status)
    if requires_human_approval is not None:
        q = q.filter(ExceptionRecord.requires_human_approval == requires_human_approval)
    return q.order_by(ExceptionRecord.created_at.desc()).all()


@router.get("/{exception_id}", response_model=ExceptionOut)
def get_exception(exception_id: str, db: Session = Depends(get_db)):
    exc = db.query(ExceptionRecord).filter(ExceptionRecord.id == exception_id).first()
    if not exc:
        raise HTTPException(404, "Exception not found")
    return exc


@router.post("/{exception_id}/investigate", response_model=ExceptionOut)
def investigate(exception_id: str, db: Session = Depends(get_db)):
    exc = db.query(ExceptionRecord).filter(ExceptionRecord.id == exception_id).first()
    if not exc:
        raise HTTPException(404, "Exception not found")
    agent = get_investigation_agent()
    agent.run(db, exception_id)
    db.refresh(exc)
    return exc


@router.post("/{exception_id}/resolve", response_model=ExceptionOut)
def resolve(exception_id: str, body: ResolutionRequest, db: Session = Depends(get_db)):
    try:
        return apply_resolution(db, exception_id, action=body.action, actor=body.actor, reason=body.reason)
    except ExceptionNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except AlreadyResolvedError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
