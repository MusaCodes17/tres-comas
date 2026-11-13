"""The outbound choke point: the only function in the app that makes HTTP calls.

Job: every outbound request goes through ``call``, which checks the registry
row, checks the URL and params against the row's scope, applies the secret, and
writes one ``outbound_logs`` row whether the call succeeds or fails.

Invariants upheld:
- INV-3: the secret is read from the environment at call time, applied to the
  request, and never stored, returned, logged, or put in an error message.
- INV-4: market data gets only tickers, series ids and ISO dates. Any other
  param name or value type is refused before anything is sent.
- INV-7: no enabled registry row, no call; every call that is made is logged.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connections.errors import (
    ConnectionDisabled,
    ConnectionNotCallable,
    ConnectionNotConfigured,
    ConnectionNotFound,
    ProviderError,
    ScopeViolation,
)
from app.models.models import Connection, OutboundLog

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10.0
PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._\-]+$")
TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,15}$")
SERIES_RE = re.compile(r"^[A-Z0-9_]{1,32}$")
_LIST_PARAMS = {"tickers": TICKER_RE, "series": SERIES_RE}
_DATE_PARAMS = ("start_date", "end_date")


def _check_url(url: str, hosts: list[str]) -> str:
    """Validate the URL against the scope and return the loggable endpoint (no query)."""
    if not isinstance(url, str):
        raise ScopeViolation("url must be a string")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise ScopeViolation("url is not valid") from exc
    if parts.scheme != "https":
        raise ScopeViolation("url must be https")
    host = (parts.hostname or "").lower()
    if host not in hosts:
        raise ScopeViolation(f"host {host!r} is not in this connection's scope")
    if parts.username or parts.password or port not in (None, 443):
        raise ScopeViolation("url must not carry credentials or a custom port")
    if parts.query or parts.fragment or "?" in url or "#" in url:
        raise ScopeViolation("url must not carry a query string or fragment; pass params instead")
    segments = parts.path.split("/")[1:]
    if segments and segments[-1] == "":
        segments = segments[:-1]
    for segment in segments:
        if not PATH_SEGMENT_RE.match(segment):
            raise ScopeViolation("url path has a segment outside [A-Za-z0-9._-]")
    return f"https://{host}{parts.path}"


def _check_params(params: dict[str, object] | None, allowed: list[str]) -> tuple[dict[str, str], list[str]]:
    """Validate params (INV-4); return (query dict, tickers list)."""
    query: dict[str, str] = {}
    tickers: list[str] = []
    for key, value in (params or {}).items():
        if key not in allowed:
            raise ScopeViolation(f"param {key!r} is not in this connection's scope (INV-4)")
        if key in _LIST_PARAMS:
            if not isinstance(value, (list, tuple)) or not value:
                raise ScopeViolation(f"param {key!r} must be a non-empty list of strings")
            pattern = _LIST_PARAMS[key]
            for item in value:
                if not isinstance(item, str) or not pattern.match(item):
                    raise ScopeViolation(f"param {key!r} has an item that is not a valid identifier (INV-4)")
            query[key] = ",".join(value)
            if key == "tickers":
                tickers = list(value)
        elif key in _DATE_PARAMS:
            if not isinstance(value, date) or isinstance(value, datetime):
                raise ScopeViolation(f"param {key!r} must be a datetime.date (INV-4)")
            query[key] = value.isoformat()
        else:
            raise ScopeViolation(f"param {key!r} is not sendable by market data calls (INV-4)")
    return query, tickers


def call(
    db: Session,
    name: str,
    *,
    url: str,
    params: dict[str, object] | None = None,
    client: httpx.Client | None = None,
) -> httpx.Response:
    """Make one logged GET through the registry row ``name`` (INV-7).

    This function commits its own log row (and ``last_used_at``), so the caller
    must have committed any pending work first.

    Raises:
        ValueError: the session has pending changes.
        ConnectionNotFound (LookupError): no row with that name.
        ConnectionDisabled: row is switched off; no request, no log row.
        ConnectionNotCallable: kind is not market_data in v1; no request, no log row.
        ScopeViolation (ValueError): url or params outside scope; no request, no log row.
        ConnectionNotConfigured: the secret's env var is unset or empty; no request, no log row.
        ProviderError: transport failure or HTTP status >= 400; logged first.
    """
    if db.new or db.dirty or db.deleted:
        raise ValueError("commit pending work before an outbound call")

    row = db.scalar(select(Connection).where(Connection.name == name))
    if row is None:
        raise ConnectionNotFound(f"connection {name!r} not found")
    if not row.enabled:
        raise ConnectionDisabled(f"connection {name!r} is disabled")
    if row.kind != "market_data":
        raise ConnectionNotCallable(
            f"connection {name!r} has kind {row.kind!r}; news/llm calls are not built in v1"
        )

    scope = json.loads(row.scope)
    endpoint = _check_url(url, scope.get("hosts", []))
    query, tickers = _check_params(params, scope.get("params", []))

    headers: dict[str, str] = {}
    if row.secret_env_key:
        auth = scope.get("auth")
        if not auth:
            raise ScopeViolation(f"connection {name!r} has a secret but no auth placement in scope")
        secret = os.environ.get(row.secret_env_key)
        if not secret:
            raise ConnectionNotConfigured(f"connection {name!r} is not configured: secret is not set")
        if "header" in auth:
            headers[auth["header"]] = f"{auth.get('prefix', '')}{secret}"
        else:
            query[auth["param"]] = secret

    own_client = client is None
    http = httpx.Client() if own_client else client
    failure: str | None = None
    cause: Exception | None = None
    response: httpx.Response | None = None
    try:
        response = http.get(url, params=query or None, headers=headers, timeout=TIMEOUT_SECONDS)
        if response.status_code >= 400:
            failure = f"HTTP {response.status_code}"
    except httpx.HTTPError as exc:
        cause = exc
        failure = type(exc).__name__
    finally:
        if own_client:
            http.close()

    db.add(
        OutboundLog(
            connection_id=row.id,
            endpoint=endpoint,
            tickers_sent=json.dumps(tickers),
            succeeded=failure is None,
        )
    )
    row.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    if failure is not None:
        logger.warning("outbound call failed: connection=%s tickers=%d reason=%s", name, len(tickers), failure)
        error = ProviderError(f"connection {name!r} call failed: {failure}")
        if cause is not None:
            raise error from cause
        raise error
    logger.info("outbound call ok: connection=%s tickers=%d", name, len(tickers))
    assert response is not None
    return response
