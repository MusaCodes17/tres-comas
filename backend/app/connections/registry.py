"""Connection registry service: list, create, enable, and the safe public view.

Job: own the rules for what a registry row may say. Every outbound or inbound
integration is a row Musa created and can switch off.

Invariants upheld:
- INV-1: only the four allowed kinds can be registered; ``broker`` and
  ``aggregator`` are refused here and by the DB CHECK on ``kind``.
- INV-3: only the NAME of an env key is stored; ``public_view`` never returns a value.
- INV-4: a row's params must be a subset of its kind's allowlist.
- INV-7: new rows are always created disabled (D-17).

All functions flush; the caller commits.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connections.errors import ConnectionNotFound
from app.models.models import Connection, OutboundLog

KINDS = ("market_data", "news", "llm", "mcp_client")
FORBIDDEN_KINDS = ("broker", "aggregator")

# Params each kind may ever send (INV-4, spec "Outbound rules by kind").
ALLOWED_PARAMS: dict[str, frozenset[str]] = {
    "market_data": frozenset({"tickers", "series", "start_date", "end_date"}),
    "news": frozenset({"tickers", "company_names"}),
    "llm": frozenset({"tickers", "weights", "amounts"}),
    "mcp_client": frozenset(),
}

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
SECRET_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)+$")
HEADER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9\-]*$")
PARAM_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _direction_for(kind: str) -> str:
    return "inbound" if kind == "mcp_client" else "outbound"


def _validate_scope(kind: str, scope: dict) -> dict:
    """Return a normalised scope dict or raise ValueError."""
    if not isinstance(scope, dict):
        raise ValueError("scope must be an object")
    unknown = set(scope) - {"hosts", "params", "auth"}
    if unknown:
        raise ValueError(f"unknown scope keys: {sorted(unknown)}")

    hosts = scope.get("hosts", [])
    params = scope.get("params", [])
    auth = scope.get("auth")
    if not isinstance(hosts, list) or not all(isinstance(h, str) for h in hosts):
        raise ValueError("scope.hosts must be a list of strings")
    if not isinstance(params, list) or not all(isinstance(p, str) for p in params):
        raise ValueError("scope.params must be a list of strings")

    if kind == "mcp_client":
        if hosts:
            raise ValueError("an mcp_client connection takes no hosts")
    elif not hosts:
        raise ValueError("an outbound connection needs at least one host")
    for host in hosts:
        if host != host.lower() or not HOST_RE.match(host):
            raise ValueError(f"host must be a lowercase DNS name: {host!r}")

    extra = set(params) - ALLOWED_PARAMS[kind]
    if extra:
        raise ValueError(
            f"params {sorted(extra)} are not allowed for kind {kind!r} (INV-4); "
            f"allowed: {sorted(ALLOWED_PARAMS[kind])}"
        )

    if auth is not None:
        if kind == "mcp_client":
            raise ValueError("an mcp_client connection takes no auth block")
        if not isinstance(auth, dict):
            raise ValueError("scope.auth must be null or an object")
        if set(auth) == {"header", "prefix"}:
            if not isinstance(auth["header"], str) or not HEADER_RE.match(auth["header"]):
                raise ValueError("scope.auth.header must be a header name")
            if not isinstance(auth["prefix"], str):
                raise ValueError("scope.auth.prefix must be a string")
        elif set(auth) == {"param"}:
            if not isinstance(auth["param"], str) or not PARAM_NAME_RE.match(auth["param"]):
                raise ValueError("scope.auth.param must be a parameter name")
        else:
            raise ValueError('scope.auth must be {"header", "prefix"} or {"param"}')

    return {"hosts": hosts, "params": params, "auth": auth}


def list_connections(db: Session) -> list[Connection]:
    """All registry rows, oldest first."""
    return list(db.scalars(select(Connection).order_by(Connection.id)))


def get_connection(db: Session, *, connection_id: int) -> Connection:
    """One row by id.

    Raises:
        LookupError: no such connection.
    """
    row = db.get(Connection, connection_id)
    if row is None:
        raise ConnectionNotFound(f"connection {connection_id} not found")
    return row


def create_connection(
    db: Session,
    *,
    name: str,
    kind: str,
    scope: dict,
    secret_env_key: str | None = None,
) -> Connection:
    """Create a registry row, always disabled (INV-7, D-17). Flushes; caller commits.

    Raises:
        ValueError: bad kind (broker/aggregator names INV-1), name, scope,
            secret key name, or a duplicate name.
    """
    if kind in FORBIDDEN_KINDS:
        raise ValueError(f"kind {kind!r} is not allowed: no broker or aggregator connections (INV-1)")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {list(KINDS)}")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ValueError("name must match ^[a-z][a-z0-9_]{1,63}$")
    if secret_env_key is not None and (
        not isinstance(secret_env_key, str) or not SECRET_KEY_RE.match(secret_env_key)
    ):
        raise ValueError("secret_env_key must be an env var NAME like MY_API_KEY, never a value (INV-3)")
    clean_scope = _validate_scope(kind, scope)
    if db.scalar(select(Connection.id).where(Connection.name == name)) is not None:
        raise ValueError(f"a connection named {name!r} already exists")

    row = Connection(
        name=name,
        kind=kind,
        direction=_direction_for(kind),
        scope=json.dumps(clean_scope),
        secret_env_key=secret_env_key,
        enabled=False,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


def set_enabled(db: Session, *, connection_id: int, enabled: bool) -> Connection:
    """Switch a row on or off. Flushes; caller commits.

    Raises:
        LookupError: no such connection.
    """
    row = get_connection(db, connection_id=connection_id)
    row.enabled = bool(enabled)
    db.flush()
    return row


def public_view(row: Connection) -> dict[str, Any]:
    """The row as safe to show: the env key NAME and whether it is set, never a value (INV-3)."""
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "direction": row.direction,
        "scope": json.loads(row.scope),
        "secret_env_key": row.secret_env_key,
        "secret_configured": bool(row.secret_env_key and os.environ.get(row.secret_env_key)),
        "enabled": row.enabled,
        "created_at": row.created_at,
        "last_used_at": row.last_used_at,
    }


def recent_log(db: Session, *, connection_id: int, limit: int = 50) -> list[OutboundLog]:
    """Most recent outbound log rows for a connection, newest first."""
    return list(
        db.scalars(
            select(OutboundLog)
            .where(OutboundLog.connection_id == connection_id)
            .order_by(OutboundLog.id.desc())
            .limit(limit)
        )
    )
