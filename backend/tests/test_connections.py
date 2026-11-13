"""Connection registry and outbound client: INV-1, INV-3, INV-4, INV-7.

No test touches the network: calls go through httpx.MockTransport.
"""
import json
from datetime import date, datetime
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from app import connections
from app.connections import registry
from app.connections.errors import (
    ConnectionDisabled,
    ConnectionNotCallable,
    ConnectionNotConfigured,
    ConnectionNotFound,
    ProviderError,
    ScopeViolation,
)
from app.models.models import Connection, OutboundLog

HOST = "api.example.com"
URL = f"https://{HOST}/v1/quotes"
SECRET = "s3cr3t-value-123"


def _scope(**over):
    scope = {"hosts": [HOST], "params": ["tickers", "start_date", "end_date", "series"], "auth": None}
    scope.update(over)
    return scope


def _make(session, name="prices", kind="market_data", scope=None, secret_env_key=None, enabled=True):
    row = registry.create_connection(
        session, name=name, kind=kind, scope=scope or _scope(), secret_env_key=secret_env_key
    )
    if enabled:
        registry.set_enabled(session, connection_id=row.id, enabled=True)
    session.commit()
    return row


class Recorder:
    """A MockTransport handler that counts hits and records requests."""

    def __init__(self, status=200, exc=None):
        self.status, self.exc, self.requests = status, exc, []

    def __call__(self, request):
        self.requests.append(request)
        if self.exc:
            raise self.exc
        return httpx.Response(self.status, json={"ok": True})

    @property
    def hits(self):
        return len(self.requests)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))


# ---------------------------------------------------------------- registry

def test_seeded_boc_valet_exists_and_is_disabled(session):
    row = session.query(Connection).filter_by(name="boc_valet").one()
    assert row.enabled is False
    assert row.kind == "market_data" and row.direction == "outbound"
    assert row.secret_env_key is None
    assert json.loads(row.scope) == {
        "hosts": ["www.bankofcanada.ca"],
        "params": ["start_date", "end_date"],
        "auth": None,
    }


def test_inv7_new_connection_disabled(session):
    row = registry.create_connection(session, name="prices", kind="market_data", scope=_scope())
    assert row.enabled is False
    assert row.direction == "outbound"


def test_mcp_client_is_inbound_without_hosts(session):
    row = registry.create_connection(
        session, name="claude_mcp", kind="mcp_client", scope={"hosts": [], "params": [], "auth": None}
    )
    assert row.direction == "inbound"


def test_set_enabled_toggles(session):
    row = _make(session, enabled=False)
    registry.set_enabled(session, connection_id=row.id, enabled=True)
    assert registry.get_connection(session, connection_id=row.id).enabled is True
    registry.set_enabled(session, connection_id=row.id, enabled=False)
    assert registry.get_connection(session, connection_id=row.id).enabled is False
    with pytest.raises(LookupError):
        registry.set_enabled(session, connection_id=9999, enabled=True)


def test_list_connections_includes_seed_and_new(session):
    _make(session)
    assert [c.name for c in registry.list_connections(session)] == ["boc_valet", "prices"]


def test_inv1_no_broker_connection_kinds(session):
    for kind in ("broker", "aggregator"):
        with pytest.raises(ValueError, match="INV-1"):
            registry.create_connection(session, name="nope", kind=kind, scope=_scope())
        with pytest.raises(IntegrityError):
            session.execute(
                Connection.__table__.insert().values(
                    name=f"raw_{kind}", kind=kind, direction="outbound", scope="{}"
                )
            )
        session.rollback()


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(kind="crypto"),
        dict(name="Bad Name"),
        dict(name="x"),
        dict(secret_env_key="lower_case"),
        dict(secret_env_key="sk-live-abc123"),
        dict(scope=_scope(hosts=[])),
        dict(scope=_scope(hosts=["API.example.com"])),
        dict(scope=_scope(hosts=["https://api.example.com"])),
        dict(scope=_scope(params=["tickers", "quantity"])),
        dict(scope=_scope(params=["amounts"])),  # llm-only param on market_data
        dict(scope=_scope(auth={"header": "X-Key"})),
        dict(scope=_scope(auth="Bearer")),
        dict(scope=_scope(bogus=1)),
        dict(scope="not a dict"),
    ],
)
def test_create_validation_rejects(session, kwargs):
    args = dict(name="prices", kind="market_data", scope=_scope())
    args.update(kwargs)
    with pytest.raises(ValueError):
        registry.create_connection(session, **args)


def test_create_rejects_mcp_client_with_hosts_and_duplicates(session):
    with pytest.raises(ValueError):
        registry.create_connection(session, name="claude_mcp", kind="mcp_client", scope=_scope())
    _make(session)
    with pytest.raises(ValueError, match="already exists"):
        registry.create_connection(session, name="prices", kind="market_data", scope=_scope())


def test_params_allowlist_per_kind(session):
    registry.create_connection(
        session, name="headlines", kind="news", scope=_scope(params=["tickers", "company_names"])
    )
    registry.create_connection(
        session, name="analyst", kind="llm", scope=_scope(params=["tickers", "weights", "amounts"])
    )
    with pytest.raises(ValueError):
        registry.create_connection(
            session, name="headlines2", kind="news", scope=_scope(params=["amounts"])
        )


def test_recent_log_newest_first(session):
    row = _make(session)
    rec = Recorder()
    for t in (["AAPL"], ["NVDA"], ["MDA.TO"]):
        connections.call(session, "prices", url=URL, params={"tickers": t}, client=rec.client())
    log = registry.recent_log(session, connection_id=row.id, limit=2)
    assert [json.loads(r.tickers_sent) for r in log] == [["MDA.TO"], ["NVDA"]]


# ------------------------------------------------------------- call refusals

def test_inv7_disabled_connection_makes_no_call(session):
    _make(session, enabled=False)
    rec = Recorder()
    with pytest.raises(ConnectionDisabled):
        connections.call(session, "prices", url=URL, params={"tickers": ["AAPL"]}, client=rec.client())
    assert rec.hits == 0
    assert session.query(OutboundLog).count() == 0


def test_unknown_connection(session):
    with pytest.raises(ConnectionNotFound):
        connections.call(session, "missing", url=URL, client=Recorder().client())


@pytest.mark.parametrize(
    "params",
    [
        {"tickers": ["AAPL"], "amount": Decimal("100.50")},
        {"tickers": ["AAPL"], "quantity": 10},
        {"tickers": ["AAPL"], "nickname": "TFSA"},
        {"tickers": {"AAPL": "x"}},
        {"tickers": ["aapl"]},
        {"tickers": "AAPL"},
        {"tickers": ["AAPL", 5]},
        {"tickers": [Decimal("1")]},
        {"series": ["fxusdcad"]},
        {"start_date": "2026-01-02"},
        {"start_date": datetime(2026, 1, 2, 12, 0)},
        {"start_date": 20260102},
        {"start_date": True},
        {"end_date": {"y": 2026}},
    ],
)
def test_inv4_market_data_payload_is_tickers_only(session, params):
    _make(session)
    rec = Recorder()
    with pytest.raises(ScopeViolation):
        connections.call(session, "prices", url=URL, params=params, client=rec.client())
    assert rec.hits == 0
    assert session.query(OutboundLog).count() == 0


def test_param_not_in_row_scope_refused(session):
    _make(session, scope=_scope(params=["tickers"]))
    rec = Recorder()
    with pytest.raises(ScopeViolation):
        connections.call(session, "prices", url=URL, params={"start_date": date(2026, 1, 2)}, client=rec.client())
    assert rec.hits == 0


@pytest.mark.parametrize(
    "url",
    [
        "https://other.example.com/v1/quotes",
        f"http://{HOST}/v1/quotes",
        f"https://{HOST}/v1/quotes?tickers=AAPL",
        f"https://{HOST}/v1/quotes#frag",
        f"https://{HOST}/v1/bad segment",
        f"https://{HOST}/v1/%2e%2e/x",
        f"https://{HOST}/v1//x",
        f"https://user:pw@{HOST}/v1/quotes",
        f"https://{HOST}:8443/v1/quotes",
    ],
)
def test_url_scope_violations(session, url):
    _make(session)
    rec = Recorder()
    with pytest.raises(ScopeViolation):
        connections.call(session, "prices", url=url, client=rec.client())
    assert rec.hits == 0
    assert session.query(OutboundLog).count() == 0


def test_not_configured_when_env_unset(session, monkeypatch):
    monkeypatch.delenv("PRICES_API_KEY", raising=False)
    _make(session, secret_env_key="PRICES_API_KEY", scope=_scope(auth={"header": "Authorization", "prefix": "Bearer "}))
    rec = Recorder()
    with pytest.raises(ConnectionNotConfigured):
        connections.call(session, "prices", url=URL, client=rec.client())
    assert rec.hits == 0
    assert session.query(OutboundLog).count() == 0
    monkeypatch.setenv("PRICES_API_KEY", "")
    with pytest.raises(ConnectionNotConfigured):
        connections.call(session, "prices", url=URL, client=rec.client())


def test_secret_without_auth_placement_refused(session, monkeypatch):
    monkeypatch.setenv("PRICES_API_KEY", SECRET)
    _make(session, secret_env_key="PRICES_API_KEY")
    rec = Recorder()
    with pytest.raises(ScopeViolation):
        connections.call(session, "prices", url=URL, client=rec.client())
    assert rec.hits == 0


def test_news_kind_not_callable(session):
    _make(session, name="headlines", kind="news", scope=_scope(params=["tickers"]))
    rec = Recorder()
    with pytest.raises(ConnectionNotCallable):
        connections.call(session, "headlines", url=URL, client=rec.client())
    assert rec.hits == 0
    assert session.query(OutboundLog).count() == 0


def test_inbound_kind_not_callable(session):
    _make(session, name="claude_mcp", kind="mcp_client", scope={"hosts": [], "params": [], "auth": None})
    with pytest.raises(ConnectionNotCallable):
        connections.call(session, "claude_mcp", url=URL, client=Recorder().client())


def test_pending_changes_refused(session):
    _make(session)
    session.add(Connection(name="pending", kind="market_data", direction="outbound", scope="{}"))
    rec = Recorder()
    with pytest.raises(ValueError, match="commit pending work"):
        connections.call(session, "prices", url=URL, client=rec.client())
    assert rec.hits == 0


# ------------------------------------------------------- logging and secrets

def test_inv7_every_call_logged(session):
    row = _make(session)
    assert row.last_used_at is None

    ok = Recorder(200)
    resp = connections.call(session, "prices", url=URL, params={"tickers": ["AAPL"]}, client=ok.client())
    assert resp.status_code == 200

    bad = Recorder(500)
    with pytest.raises(ProviderError, match="500"):
        connections.call(session, "prices", url=URL, params={"tickers": ["AAPL"]}, client=bad.client())

    down = Recorder(exc=httpx.ConnectError("boom"))
    with pytest.raises(ProviderError) as info:
        connections.call(session, "prices", url=URL, params={"tickers": ["AAPL"]}, client=down.client())
    assert isinstance(info.value.__cause__, httpx.ConnectError)

    logs = session.query(OutboundLog).order_by(OutboundLog.id).all()
    assert [r.succeeded for r in logs] == [True, False, False]
    assert all(r.connection_id == row.id and r.endpoint == URL for r in logs)
    assert session.get(Connection, row.id).last_used_at is not None


def test_log_tickers_sent_equals_json_of_tickers(session):
    _make(session)
    tickers = ["AAPL", "MDA.TO", "BRK-B"]
    rec = Recorder()
    connections.call(session, "prices", url=URL, params={"tickers": tickers}, client=rec.client())
    assert session.query(OutboundLog).one().tickers_sent == json.dumps(tickers)
    assert rec.requests[0].url.params["tickers"] == "AAPL,MDA.TO,BRK-B"
    connections.call(session, "prices", url=URL, client=rec.client())
    assert session.query(OutboundLog).order_by(OutboundLog.id.desc()).first().tickers_sent == "[]"


def test_dates_and_series_are_sent_as_iso_and_joined(session):
    _make(session)
    rec = Recorder()
    connections.call(
        session, "prices", url=URL,
        params={"series": ["FXUSDCAD", "FXZARCAD"], "start_date": date(2026, 1, 2), "end_date": date(2026, 1, 9)},
        client=rec.client(),
    )
    q = rec.requests[0].url.params
    assert q["series"] == "FXUSDCAD,FXZARCAD"
    assert q["start_date"] == "2026-01-02" and q["end_date"] == "2026-01-09"


def test_inv3_secret_never_logged_header(session, monkeypatch):
    monkeypatch.setenv("PRICES_API_KEY", SECRET)
    _make(session, secret_env_key="PRICES_API_KEY", scope=_scope(auth={"header": "Authorization", "prefix": "Bearer "}))
    ok = Recorder(200)
    connections.call(session, "prices", url=URL, params={"tickers": ["AAPL"]}, client=ok.client())
    assert ok.requests[0].headers["Authorization"] == f"Bearer {SECRET}"
    bad = Recorder(500)
    with pytest.raises(ProviderError) as info:
        connections.call(session, "prices", url=URL, client=bad.client())
    assert SECRET not in str(info.value)
    for r in session.query(OutboundLog):
        assert SECRET not in r.endpoint and SECRET not in r.tickers_sent


def test_inv3_secret_never_logged_query_param(session, monkeypatch):
    monkeypatch.setenv("PRICES_API_KEY", SECRET)
    _make(session, secret_env_key="PRICES_API_KEY", scope=_scope(auth={"param": "apikey"}))
    ok = Recorder(200)
    connections.call(session, "prices", url=URL, params={"tickers": ["AAPL"]}, client=ok.client())
    assert ok.requests[0].url.params["apikey"] == SECRET
    bad = Recorder(502)
    with pytest.raises(ProviderError) as info:
        connections.call(session, "prices", url=URL, client=bad.client())
    assert SECRET not in str(info.value) and SECRET not in repr(info.value)
    logs = session.query(OutboundLog).all()
    assert len(logs) == 2
    for r in logs:
        assert SECRET not in r.endpoint and "?" not in r.endpoint and "apikey" not in r.endpoint


def test_inv3_registry_never_returns_secret_values(session, monkeypatch):
    monkeypatch.setenv("PRICES_API_KEY", SECRET)
    row = _make(session, secret_env_key="PRICES_API_KEY", scope=_scope(auth={"header": "X-Api-Key", "prefix": ""}))
    view = registry.public_view(row)
    assert view["secret_configured"] is True
    assert view["secret_env_key"] == "PRICES_API_KEY"
    assert set(view) == {
        "id", "name", "kind", "direction", "scope", "secret_env_key",
        "secret_configured", "enabled", "created_at", "last_used_at",
    }
    assert SECRET not in json.dumps(view, default=str)
    monkeypatch.delenv("PRICES_API_KEY")
    assert registry.public_view(row)["secret_configured"] is False
