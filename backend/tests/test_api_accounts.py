"""API tests for accounts and securities (T4 part two, F1)."""


def _acct(client, nickname="Main TFSA", **extra):
    return client.post("/api/accounts", json={"nickname": nickname, "type": "tfsa", **extra})


def test_account_create_list_patch(authed_client):
    r = _acct(authed_client, broker_label="Wealthsimple")
    assert r.status_code == 201
    body = r.json()
    assert body["nickname"] == "Main TFSA"
    assert body["base_currency"] == "CAD"
    assert body["broker_label"] == "Wealthsimple"
    assert body["last_reconciled_date"] is None
    assert "T" in body["created_at"]

    assert [a["id"] for a in authed_client.get("/api/accounts").json()] == [body["id"]]

    r = authed_client.patch(f"/api/accounts/{body['id']}", json={"nickname": " Renamed ", "type": "rrsp"})
    assert r.status_code == 200
    assert r.json()["nickname"] == "Renamed"
    assert r.json()["type"] == "rrsp"
    assert r.json()["broker_label"] == "Wealthsimple"


def test_account_duplicate_nickname_400(authed_client):
    assert _acct(authed_client).status_code == 201
    assert _acct(authed_client).status_code == 400
    other = _acct(authed_client, "Other").json()["id"]
    r = authed_client.patch(f"/api/accounts/{other}", json={"nickname": "Main TFSA"})
    assert r.status_code == 400


def test_account_patch_unknown_404_and_base_currency_immutable(authed_client):
    assert authed_client.patch("/api/accounts/999", json={"nickname": "x"}).status_code == 404
    aid = _acct(authed_client).json()["id"]
    assert authed_client.patch(f"/api/accounts/{aid}", json={"base_currency": "USD"}).status_code == 422


def test_inv8_api_rejects_account_number(authed_client):
    r = authed_client.post(
        "/api/accounts", json={"nickname": "A", "type": "tfsa", "account_number": "123456"}
    )
    assert r.status_code == 422
    aid = _acct(authed_client).json()["id"]
    r = authed_client.patch(f"/api/accounts/{aid}", json={"account_number": "123456"})
    assert r.status_code == 422


def test_account_bad_type_422(authed_client):
    r = authed_client.post("/api/accounts", json={"nickname": "A", "type": "crypto"})
    assert r.status_code == 422


def test_no_delete_route(authed_client):
    aid = _acct(authed_client).json()["id"]
    assert authed_client.delete(f"/api/accounts/{aid}").status_code == 405
    assert authed_client.delete("/api/accounts/1").status_code == 405


def test_securities_create_and_list(authed_client):
    r = authed_client.post(
        "/api/securities",
        json={"ticker": "aapl ", "exchange": " nasdaq", "currency": "USD", "kind": "stock", "name": "Apple"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["exchange"] == "NASDAQ"
    assert body["name"] == "Apple"
    assert authed_client.get("/api/securities").json() == [body]


def test_securities_duplicate_400_but_other_exchange_ok(authed_client):
    base = {"ticker": "MDA", "exchange": "TSX", "currency": "CAD", "kind": "stock"}
    assert authed_client.post("/api/securities", json=base).status_code == 201
    assert authed_client.post("/api/securities", json={**base, "ticker": "mda"}).status_code == 400
    assert authed_client.post("/api/securities", json={**base, "exchange": "NYSE"}).status_code == 201


def test_securities_validation(authed_client):
    base = {"ticker": "X", "exchange": "TSX", "currency": "CAD", "kind": "stock"}
    assert authed_client.post("/api/securities", json={**base, "kind": "bond"}).status_code == 422
    assert authed_client.post("/api/securities", json={**base, "currency": "cad"}).status_code == 400
    assert authed_client.post("/api/securities", json={**base, "extra": 1}).status_code == 422


def test_api_routes_require_auth(api_client):
    assert api_client.get("/api/accounts").status_code == 401
    assert api_client.get("/api/securities").status_code == 401
    assert api_client.post("/api/accounts/1/transactions", json={}).status_code == 401
