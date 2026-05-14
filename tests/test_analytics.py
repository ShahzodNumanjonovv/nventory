from tests._helpers import seed_two_providers


async def _setup_two_batches_with_activity(client, ids):
    b1 = (await client.post("/api/v1/purchases", json={
        "provider_id": ids["p1"], "storage_id": ids["storage"],
        "purchase_date": "2026-05-01",
        "items": [
            {"product_id": ids["earl"], "qty": 100, "purchase_price": "10", "sell_price": "15"},
            {"product_id": ids["sencha"], "qty": 50, "purchase_price": "8", "sell_price": "12"},
        ],
    })).json()
    b2 = (await client.post("/api/v1/purchases", json={
        "provider_id": ids["p1"], "storage_id": ids["storage"],
        "purchase_date": "2026-05-10",
        "items": [{"product_id": ids["earl"], "qty": 50, "purchase_price": "11", "sell_price": "16"}],
    })).json()
    order = (await client.post("/api/v1/orders", json={
        "client_id": ids["client"], "products": [{"id": ids["earl"], "qty": 120}],
    })).json()
    await client.post("/api/v1/refunds/providers", json={
        "batch_id": b1["id"], "items": [{"product_id": ids["sencha"], "qty": 10}],
    })
    await client.post("/api/v1/refunds/clients", json={
        "items": [{"order_item_id": order["items"][0]["id"], "qty": 5}],
    })
    return b1, b2, order


async def test_storage_remaining_current(client):
    ids = await seed_two_providers(client)
    await _setup_two_batches_with_activity(client, ids)

    rows = (await client.get("/api/v1/storage/remaining?date=2026-05-14")).json()
    by_p = {r["product_id"]: r["qty"] for r in rows}
    # earl: 150 purchased − 120 sold + 5 returned = 35
    # sencha: 50 purchased − 10 returned-to-provider = 40
    assert by_p[ids["earl"]] == 35
    assert by_p[ids["sencha"]] == 40


async def test_storage_remaining_historical_snapshot(client):
    ids = await seed_two_providers(client)
    await _setup_two_batches_with_activity(client, ids)

    rows = (await client.get("/api/v1/storage/remaining?date=2026-05-01")).json()
    # Only batch 1 existed on this date; no sales or refunds yet.
    by_p = {r["product_id"]: r["qty"] for r in rows}
    assert by_p[ids["earl"]] == 100
    assert by_p[ids["sencha"]] == 50


async def test_profit_per_batch_with_refunds_on_both_sides(client):
    ids = await seed_two_providers(client)
    b1, b2, _order = await _setup_two_batches_with_activity(client, ids)

    rows = (await client.get("/api/v1/analytics/profit-per-batch")).json()
    by_batch = {p["batch_id"]: p for p in rows}

    # batch1: cost = 100*10 + 50*8 = 1400, recovered = 80 → 1320
    #         revenue = 100*15 = 1500, refunded = 75 → 1425
    #         profit = 105
    assert by_batch[b1["id"]]["cost"] == "1320.00"
    assert by_batch[b1["id"]]["revenue"] == "1425.00"
    assert by_batch[b1["id"]]["profit"] == "105.00"

    # batch2: cost = 50*11 = 550, revenue = 20*16 = 320, profit = -230
    assert by_batch[b2["id"]]["cost"] == "550.00"
    assert by_batch[b2["id"]]["revenue"] == "320.00"
    assert by_batch[b2["id"]]["profit"] == "-230.00"
