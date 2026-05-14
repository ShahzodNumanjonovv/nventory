async def test_health_live(client):
    r = await client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_health_ready_pings_db(client):
    r = await client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["db"] == "ok"


async def test_request_id_header_round_trips(client):
    r = await client.get("/health/live", headers={"X-Request-ID": "abc123"})
    assert r.headers.get("X-Request-ID") == "abc123"


async def test_request_id_generated_when_missing(client):
    r = await client.get("/health/live")
    rid = r.headers.get("X-Request-ID")
    assert rid and len(rid) >= 8


async def test_pagination_envelope(client):
    r = await client.get("/api/v1/providers?limit=5&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"items", "total", "limit", "offset"}
    assert body["limit"] == 5
