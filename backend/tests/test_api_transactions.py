"""API tests for transactions and positions (T4 part two, F1; INV-2, INV-6, INV-9)."""

from decimal import Decimal

import pytest
from fastapi.routing import APIRoute

from app.main import app


def _account(client, nickname="TFSA"):
    return client.post("/api/accounts", json={"nickname": nickname, "type": "tfsa"}).json()["id"]


def _security(client, ticker, exchange="NASDAQ", currency="USD", kind="stock"):
    r = client.post(
        "/api/securities",
        json={"ticker": ticker, "exchange": exchange, "currency": currency, "kind": kind},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _tx(client, account_id, **body):
    return client.post(f"/api/accounts/{account_id}/transactions", json=body)


def _buy(client, account_id, security_id, qty, amount, day="2025-01-10", currency="USD"):
    return _tx(
        client, account_id, type="buy", security_id=security_id, quantity=qty,
        amount=amount, currency=currency, trade_date=day,
    )


@pytest.fixture
def setup(authed_client):
    return authed_client, _account(authed_client), _security(authed_client, "AAPL")


def test_create_buy_exact_strings(setup):
    c, aid, sid = setup
    r = _tx(c, aid, type="buy", security_id=sid, quantity="1.2345", price="150.10",
            amount="185.30", currency="USD", trade_date="2025-01-10", note="first")
    assert r.status_code == 201
    b = r.json()
    assert (b["quantity"], b["price"], b["amount"]) == ("1.2345", "150.10", "185.30")
    assert b["source"] == "manual"
    assert b["split_ratio"] is None and b["voided_at"] is None and b["replaces_id"] is None
    assert b["security_ticker"] == "AAPL" and b["security_exchange"] == "NASDAQ"
    assert "natural_key" not in b


def test_no_scientific_notation(setup):
    c, aid, sid = setup
    r = _buy(c, aid, sid, "0.00000001", "0.0000001")
    assert r.json()["quantity"] == "0.00000001"
    assert r.json()["amount"] == "0.0000001"


def test_inv9_api_rejects_json_numbers(setup):
    c, aid, sid = setup
    base = dict(type="buy", security_id=sid, currency="USD", trade_date="2025-01-10")
    assert _tx(c, aid, **base, quantity="1", amount=100).status_code == 422
    assert _tx(c, aid, **base, quantity=1.5, amount="100").status_code == 422
    assert _tx(c, aid, **base, quantity="1", amount="100", price=1.5).status_code == 422
    assert _tx(c, aid, type="split", security_id=sid, currency="USD",
               trade_date="2025-01-10", amount="0", split_ratio=2).status_code == 422
    assert c.get(f"/api/accounts/{aid}/transactions").json() == []


@pytest.mark.parametrize(
    "field,value",
    [("source", "import"), ("proposal_id", 1), ("import_batch_id", 1), ("natural_key", "k")],
)
def test_inv6_api_cannot_set_source_or_proposal(setup, field, value):
    c, aid, sid = setup
    r = _tx(c, aid, type="buy", security_id=sid, quantity="1", amount="10",
            currency="USD", trade_date="2025-01-10", **{field: value})
    assert r.status_code == 422
    assert c.get(f"/api/accounts/{aid}/transactions").json() == []


def test_oversell_400_and_no_row(setup):
    c, aid, sid = setup
    _buy(c, aid, sid, "2", "200")
    r = _tx(c, aid, type="sell", security_id=sid, quantity="3", amount="300",
            currency="USD", trade_date="2025-02-01")
    assert r.status_code == 400
    assert "negative" in r.json()["detail"]
    assert len(c.get(f"/api/accounts/{aid}/transactions").json()) == 1


def test_unknown_security_and_account_404(setup):
    c, aid, sid = setup
    assert _buy(c, aid, 9999, "1", "10").status_code == 404
    assert _buy(c, 9999, sid, "1", "10").status_code == 404
    assert c.get("/api/accounts/9999/transactions").status_code == 404
    assert c.get("/api/accounts/9999/positions").status_code == 404
    assert c.post("/api/transactions/9999/void").status_code == 404


def test_bad_values_400(setup):
    c, aid, sid = setup
    assert _buy(c, aid, sid, "abc", "10").status_code == 400
    assert _buy(c, aid, sid, "1", "10", currency="CAD").status_code == 400


def test_void_then_void_again_400(setup):
    c, aid, sid = setup
    tid = _buy(c, aid, sid, "1", "10").json()["id"]
    r = c.post(f"/api/transactions/{tid}/void")
    assert r.status_code == 200 and r.json()["voided_at"] is not None
    assert c.post(f"/api/transactions/{tid}/void").status_code == 400


def test_replace(setup):
    c, aid, sid = setup
    old = _buy(c, aid, sid, "1", "10").json()["id"]
    r = c.post(
        f"/api/transactions/{old}/replace",
        json=dict(account_id=aid, type="buy", security_id=sid, quantity="2.5",
                  amount="25", currency="USD", trade_date="2025-01-11"),
    )
    assert r.status_code == 201
    new = r.json()
    assert new["replaces_id"] == old and new["source"] == "manual"
    rows = {t["id"]: t for t in c.get(f"/api/accounts/{aid}/transactions").json()}
    assert rows[old]["voided_at"] is not None
    pos = c.get(f"/api/accounts/{aid}/positions").json()
    assert [p["quantity"] for p in pos] == ["2.5"]
    assert c.post(
        f"/api/transactions/{old}/replace",
        json=dict(account_id=aid, type="buy", security_id=sid, quantity="1",
                  amount="1", currency="USD", trade_date="2025-01-11"),
    ).status_code == 400
    r = c.post(
        f"/api/transactions/{new['id']}/replace",
        json=dict(account_id=aid, type="buy", security_id=sid, quantity="1",
                  amount="1", currency="USD", trade_date="2025-01-11", source="import"),
    )
    assert r.status_code == 422


def test_list_includes_voided_newest_first(setup):
    c, aid, sid = setup
    a = _buy(c, aid, sid, "1", "10", day="2025-01-01").json()["id"]
    b = _buy(c, aid, sid, "1", "10", day="2025-03-01").json()["id"]
    d = _buy(c, aid, sid, "1", "10", day="2025-03-01").json()["id"]
    c.post(f"/api/transactions/{a}/void")
    rows = c.get(f"/api/accounts/{aid}/transactions").json()
    assert [r["id"] for r in rows] == [d, b, a]
    assert rows[2]["voided_at"] is not None


def test_deposit_without_security(setup):
    c, aid, _ = setup
    r = _tx(c, aid, type="deposit", amount="500.00", currency="CAD", trade_date="2025-01-02")
    assert r.status_code == 201
    assert r.json()["security_ticker"] is None


def test_positions_as_of_and_include_closed(setup):
    c, aid, sid = setup
    _buy(c, aid, sid, "10", "1000", day="2025-01-01")
    _tx(c, aid, type="sell", security_id=sid, quantity="10", amount="1200",
        currency="USD", trade_date="2025-06-01")
    assert c.get(f"/api/accounts/{aid}/positions").json() == []
    closed = c.get(f"/api/accounts/{aid}/positions?include_closed=true").json()
    assert len(closed) == 1
    assert closed[0]["quantity"] == "0" and closed[0]["average_cost"] is None
    assert Decimal(closed[0]["realised_gain"]) == Decimal("200")
    past = c.get(f"/api/accounts/{aid}/positions?as_of=2025-03-01").json()
    assert len(past) == 1
    p = past[0]
    assert (p["ticker"], p["exchange"], p["currency"]) == ("AAPL", "NASDAQ", "USD")
    assert Decimal(p["quantity"]) == 10
    assert Decimal(p["total_cost"]) == 1000 and Decimal(p["average_cost"]) == 100


def test_f1_manual_entry_via_api_nine_positions(authed_client):
    c = authed_client
    aid = _account(c)
    specs = [
        ("AAPL", "NASDAQ", "USD", "stock"), ("GOOG", "NASDAQ", "USD", "stock"),
        ("NVDA", "NASDAQ", "USD", "stock"), ("RKLB", "NASDAQ", "USD", "stock"),
        ("NOK", "NYSE", "USD", "stock"), ("MDA", "TSX", "CAD", "stock"),
        ("VGRO", "TSX", "CAD", "etf"), ("XEQT", "TSX", "CAD", "etf"),
        ("XGRO", "TSX", "CAD", "etf"),
    ]
    ids = {t: _security(c, t, ex, cur, kind) for t, ex, cur, kind in specs}
    cur = {t: cu for t, _, cu, _ in specs}
    buys = {
        "AAPL": ("3.5", "700.00"), "GOOG": ("1.2345", "250.50"), "NVDA": ("10", "1200"),
        "RKLB": ("25.25", "400.10"), "NOK": ("100", "450"), "MDA": ("12.5", "300"),
        "VGRO": ("40.1234", "1500"), "XEQT": ("55", "1700"), "XGRO": ("20.0001", "600"),
    }
    for t, (q, a) in buys.items():
        assert _buy(c, aid, ids[t], q, a, currency=cur[t]).status_code == 201
    r = _tx(c, aid, type="sell", security_id=ids["NVDA"], quantity="2.5", amount="400",
            currency="USD", trade_date="2025-02-01")
    assert r.status_code == 201
    expected = {
        "AAPL": "3.5000", "GOOG": "1.2345", "NVDA": "7.5000", "RKLB": "25.2500",
        "NOK": "100.0000", "MDA": "12.5000", "VGRO": "40.1234", "XEQT": "55.0000",
        "XGRO": "20.0001",
    }
    pos = c.get(f"/api/accounts/{aid}/positions").json()
    assert len(pos) == 9
    assert {p["ticker"]: f"{Decimal(p['quantity']):.4f}" for p in pos} == expected


def test_inv2_no_position_write_endpoint():
    found = False
    for route in app.routes:
        path = getattr(route, "path", "")
        if "position" in path:
            found = True
            assert set(route.methods) <= {"GET", "HEAD"}, (path, route.methods)
        if "/positions" in path:
            assert not set(route.methods) & {"POST", "PUT", "PATCH", "DELETE"}
    assert found


def test_no_delete_routes_anywhere():
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/"):
            assert "DELETE" not in route.methods, route.path
