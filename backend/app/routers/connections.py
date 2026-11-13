"""Connection registry routes: list, create, switch on/off, outbound log. No delete.

Job: HTTP translation only. Rules live in ``app/connections/registry.py``, which is
imported as the single service. Every route is session-protected by the app-level
dependency in ``main.py``.

Invariants upheld: INV-3 (responses use ``public_view``, never a secret value),
INV-7 (rows are created disabled and the outbound log is viewable).
"""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.connections import registry as registry_service
from app.database import get_db
from app.routers.deps import service_errors
from app.schemas.connections import (
    ConnectionCreate,
    ConnectionLogOut,
    ConnectionOut,
    ConnectionPatch,
)

router = APIRouter(prefix="/api/connections", tags=["connections"])


def _out(row) -> ConnectionOut:
    return ConnectionOut.model_validate(registry_service.public_view(row))


@router.get("", response_model=list[ConnectionOut])
def list_connections(db: Session = Depends(get_db)) -> list[ConnectionOut]:
    return [_out(r) for r in registry_service.list_connections(db)]


@router.post("", status_code=201, response_model=ConnectionOut)
def create_connection(body: ConnectionCreate, db: Session = Depends(get_db)) -> ConnectionOut:
    with service_errors(db):
        row = registry_service.create_connection(db, **body.model_dump())
        db.commit()
        return _out(row)


@router.patch("/{connection_id}", response_model=ConnectionOut)
def set_enabled(
    connection_id: int, body: ConnectionPatch, db: Session = Depends(get_db)
) -> ConnectionOut:
    with service_errors(db):
        row = registry_service.set_enabled(db, connection_id=connection_id, enabled=body.enabled)
        db.commit()
        return _out(row)


@router.get("/{connection_id}/log", response_model=list[ConnectionLogOut])
def connection_log(
    connection_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[ConnectionLogOut]:
    with service_errors(db):
        registry_service.get_connection(db, connection_id=connection_id)
        rows = registry_service.recent_log(db, connection_id=connection_id, limit=limit)
        return [
            ConnectionLogOut(
                id=r.id,
                called_at=r.called_at,
                endpoint=r.endpoint,
                tickers_sent=json.loads(r.tickers_sent),
                succeeded=r.succeeded,
            )
            for r in rows
        ]
