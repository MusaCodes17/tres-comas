"""Transaction and position routes.

Job: HTTP only. Every write goes through ``services.ledger`` with
``source="manual"`` (INV-2, INV-6); positions are read-only (GET only).
"""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, Security, Transaction
from app.routers.deps import service_errors
from app.schemas.transactions import (
    PositionOut,
    TransactionCreate,
    TransactionOut,
    TransactionReplace,
)
from app.services import ledger, positions

router = APIRouter(prefix="/api", tags=["transactions"])


def _require_account(db: Session, account_id: int) -> None:
    if db.get(Account, account_id) is None:
        raise LookupError(f"account {account_id} not found")


@router.get("/accounts/{account_id}/transactions", response_model=list[TransactionOut])
def list_transactions(account_id: int, db: Session = Depends(get_db)) -> list[TransactionOut]:
    with service_errors(db):
        _require_account(db, account_id)
        rows = db.scalars(
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(Transaction.trade_date.desc(), Transaction.id.desc())
        ).all()
        return [TransactionOut.from_row(r) for r in rows]


@router.post(
    "/accounts/{account_id}/transactions", status_code=201, response_model=TransactionOut
)
def create_transaction(
    account_id: int, body: TransactionCreate, db: Session = Depends(get_db)
) -> TransactionOut:
    with service_errors(db):
        row = ledger.record_transaction(
            db, account_id=account_id, source="manual", **body.model_dump()
        )
        db.commit()
        return TransactionOut.from_row(row)


@router.post("/transactions/{transaction_id}/void", response_model=TransactionOut)
def void_transaction(transaction_id: int, db: Session = Depends(get_db)) -> TransactionOut:
    with service_errors(db):
        row = ledger.void_transaction(db, transaction_id=transaction_id)
        db.commit()
        return TransactionOut.from_row(row)


@router.post(
    "/transactions/{transaction_id}/replace", status_code=201, response_model=TransactionOut
)
def replace_transaction(
    transaction_id: int, body: TransactionReplace, db: Session = Depends(get_db)
) -> TransactionOut:
    with service_errors(db):
        row = ledger.void_and_replace(
            db, transaction_id=transaction_id, source="manual", **body.model_dump()
        )
        db.commit()
        return TransactionOut.from_row(row)


@router.get("/accounts/{account_id}/positions", response_model=list[PositionOut])
def list_positions(
    account_id: int,
    as_of: date | None = None,
    include_closed: bool = False,
    db: Session = Depends(get_db),
) -> list[PositionOut]:
    with service_errors(db):
        _require_account(db, account_id)
        result = positions.get_positions(
            db, account_id=account_id, as_of=as_of, include_closed=include_closed
        )
        out = []
        for pos in result:
            sec = db.get(Security, pos.security_id)
            out.append(PositionOut.from_position(pos, ticker=sec.ticker, exchange=sec.exchange))
        return out
