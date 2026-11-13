"""Security routes: list and create. HTTP only; rules in services/securities.py."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.deps import service_errors
from app.schemas.securities import SecurityCreate, SecurityOut
from app.services import securities as securities_service

router = APIRouter(prefix="/api/securities", tags=["securities"])


def _out(row) -> SecurityOut:
    return SecurityOut.model_validate(row, from_attributes=True)


@router.get("", response_model=list[SecurityOut])
def list_securities(db: Session = Depends(get_db)) -> list[SecurityOut]:
    return [_out(r) for r in securities_service.list_securities(db)]


@router.post("", status_code=201, response_model=SecurityOut)
def create_security(body: SecurityCreate, db: Session = Depends(get_db)) -> SecurityOut:
    with service_errors(db):
        row = securities_service.create_security(db, **body.model_dump())
        db.commit()
        return _out(row)
