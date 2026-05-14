from tests._helpers import seed_two_providers


async def test_order_splits_across_batches_in_fifo_order(client):
    ids = await seed_two_providers(client)

    # Batch 1 (older): 100 earl @ sell 15
    await client.post("/api/v1/purchases", json={
        "provider_id": ids["p1"], "storage_id": ids["storage"],
        "purchase_date": "2026-05-01",
        "items": [{"product_id": ids["earl"], "qty": 100, "purchase_price": "10", "sell_price": "15"}],
    })
    # Batch 2 (newer): 50 earl @ sell 16
    await client.post("/api/v1/purchases", json={
        "provider_id": ids["p1"], "storage_id": ids["storage"],
        "purchase_date": "2026-05-10",
        "items": [{"product_id": ids["earl"], "qty": 50, "purchase_price": "11", "sell_price": "16"}],
    })

    order = (await client.post("/api/v1/orders", json={
        "client_id": ids["client"], "products": [{"id": ids["earl"], "qty": 120}],
    })).json()

    assert len(order["items"]) == 2
    assert order["items"][0]["qty"] == 100 and order["items"][0]["sell_price"] == "15.00"
    assert order["items"][1]["qty"] == 20 and order["items"][1]["sell_price"] == "16.00"


async def test_order_rejects_oversell(client):
    ids = await seed_two_providers(client)
    await client.post("/api/v1/purchases", json={
        "provider_id": ids["p1"], "storage_id": ids["storage"],
        "items": [{"product_id": ids["earl"], "qty": 5, "purchase_price": "1", "sell_price": "2"}],
    })
    r = await client.post("/api/v1/orders", json={
        "client_id": ids["client"], "products": [{"id": ids["earl"], "qty": 100}],
    })
    assert r.status_code == 409
    assert r.json()["type"] == "InsufficientStockError"


async def test_available_products_uses_oldest_batch_price(client):
    ids = await seed_two_providers(client)
    await client.post("/api/v1/purchases", json={
        "provider_id": ids["p1"], "storage_id": ids["storage"],
        "purchase_date": "2026-05-01",
        "items": [{"product_id": ids["earl"], "qty": 100, "purchase_price": "10", "sell_price": "15"}],
    })
    await client.post("/api/v1/purchases", json={
        "provider_id": ids["p1"], "storage_id": ids["storage"],
        "purchase_date": "2026-05-10",
        "items": [{"product_id": ids["earl"], "qty": 50, "purchase_price": "11", "sell_price": "16"}],
    })

    avail = (await client.get("/api/v1/products/available")).json()
    earl_row = next(p for p in avail if p["id"] == ids["earl"])
    assert earl_row["qty"] == 150
    assert earl_row["price"] == "15.00"  # oldest batch (FIFO next-up)
