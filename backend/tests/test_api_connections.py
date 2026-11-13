"""API tests for the connection registry routes (T6 part two, INV-3, INV-7)."""

import json

from app.models.models import OutboundLog

EXAMPLE_SCOPE = {
    "hosts": ["api.example.com"],
    "params": ["tickers"],
    "auth": {"header": "X-Api-Key", "prefix": ""},
}


def _create(client, name="example_feed", **extra):
    body = {
        "name": name,
        "kind": "market_data",
        "scope": EXAMPLE_SCOPE,
        "secret_env_key": "EXAMPLE_KEY",
        **extra,
    }
    return client.post("/api/connections", json=body)


def test_list_shows_seeded_boc_valet_disabled(authed_client):
    rows = authed_client.get("/api/connections").json()
    boc = next(r for r in rows if r["name"] == "boc_valet")
    assert boc["enabled"] is False
    assert boc["kind"] == "market_data"
    assert boc["direction"] == "outbound"
    assert boc["secret_configured"] is False


def test_create_market_data_row_disabled(authed_client, monkeypatch):
    monkeypatch.delenv("EXAMPLE_KEY", raising=False)
    r = _create(authed_client)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "example_feed"
    assert body["kind"] == "market_data"
    assert body["direction"] == "outbound"
    assert body["scope"] == EXAMPLE_SCOPE
    assert body["secret_env_key"] == "EXAMPLE_KEY"
    assert body["enabled"] is False
    assert body["secret_configured"] is False
    assert body["last_used_at"] is None


def test_create_broker_kind_422(authed_client):
    r = authed_client.post(
        "/api/connections",
        json={"name": "nope_feed", "kind": "broker", "scope": EXAMPLE_SCOPE},
    )
    assert r.status_code == 422


def test_create_with_enabled_field_422(authed_client):
    r = _create(authed_client, enabled=True)
    assert r.status_code == 422


def test_create_bad_scope_400(authed_client):
    r = authed_client.post(
        "/api/connections",
        json={"name": "bad_scope", "kind": "market_data", "scope": {"hosts": [], "params": []}},
    )
    assert r.status_code == 400


def test_patch_enabled_on_and_off_and_unknown_404(authed_client):
    cid = _create(authed_client).json()["id"]
    r = authed_client.patch(f"/api/connections/{cid}", json={"enabled": True})
    assert r.status_code == 200
    assert r.json()["enabled"] is True
    r = authed_client.patch(f"/api/connections/{cid}", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    assert authed_client.patch("/api/connections/999", json={"enabled": True}).status_code == 404


def test_patch_strict_bool_422(authed_client):
    cid = _create(authed_client).json()["id"]
    assert authed_client.patch(f"/api/connections/{cid}", json={"enabled": "yes"}).status_code == 422


def test_log_empty_then_newest_first_with_tickers_parsed(authed_client, session):
    cid = _create(authed_client).json()["id"]
    assert authed_client.get(f"/api/connections/{cid}/log").json() == []

    session.add(
        OutboundLog(connection_id=cid, endpoint="/first", tickers_sent=json.dumps(["AAA"]), succeeded=True)
    )
    session.add(
        OutboundLog(
            connection_id=cid,
            endpoint="/second",
            tickers_sent=json.dumps(["BBB", "CCC"]),
            succeeded=False,
        )
    )
    session.commit()

    body = authed_client.get(f"/api/connections/{cid}/log").json()
    assert [e["endpoint"] for e in body] == ["/second", "/first"]
    assert body[0]["tickers_sent"] == ["BBB", "CCC"]
    assert body[0]["succeeded"] is False
    assert body[1]["tickers_sent"] == ["AAA"]
    assert body[1]["succeeded"] is True


def test_log_limit_bounds_422(authed_client):
    cid = _create(authed_client).json()["id"]
    assert authed_client.get(f"/api/connections/{cid}/log?limit=0").status_code == 422
    assert authed_client.get(f"/api/connections/{cid}/log?limit=201").status_code == 422


def test_log_unknown_connection_404(authed_client):
    assert authed_client.get("/api/connections/999/log").status_code == 404


def test_inv3_connections_api_never_returns_secret(authed_client, monkeypatch):
    monkeypatch.setenv("EXAMPLE_KEY", "s3cr3t-value")
    created = _create(authed_client)
    assert created.status_code == 201
    assert "s3cr3t-value" not in created.text

    r = authed_client.get("/api/connections")
    assert r.status_code == 200
    row = next(x for x in r.json() if x["name"] == "example_feed")
    assert row["secret_configured"] is True
    assert "s3cr3t-value" not in r.text


def test_connections_api_routes_require_auth(api_client):
    assert api_client.get("/api/connections").status_code == 401
    assert api_client.post("/api/connections", json={}).status_code == 401
    assert api_client.patch("/api/connections/1", json={"enabled": True}).status_code == 401
    assert api_client.get("/api/connections/1/log").status_code == 401
