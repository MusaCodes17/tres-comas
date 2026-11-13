"""Account routes: list, create, edit. No delete. HTTP only; rules in services/accounts.py."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.deps import service_errors
from app.schemas.accounts import AccountCreate, AccountOut, AccountUpdate
from app.services import accounts as accounts_service

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _out(row) -> AccountOut:
    return AccountOut.model_validate(row, from_attributes=True)


@router.get("", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)) -> list[AccountOut]:
    return [_out(r) for r in accounts_service.list_accounts(db)]


@router.post("", status_code=201, response_model=AccountOut)
def create_account(body: AccountCreate, db: Session = Depends(get_db)) -> AccountOut:
    with service_errors(db):
        row = accounts_service.create_account(db, **body.model_dump())
        db.commit()
        return _out(row)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int, body: AccountUpdate, db: Session = Depends(get_db)
) -> AccountOut:
    with service_errors(db):
        row = accounts_service.update_account(
            db, account_id=account_id, **body.model_dump(exclude_unset=True)
        )
        db.commit()
        return _out(row)
