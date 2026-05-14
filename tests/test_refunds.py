from tests._helpers import seed_two_providers


async def test_partial_provider_refund_reduces_storage(client):
    ids = await seed_two_providers(client)
    batch = (await client.post("/api/v1/purchases", json={
        "provider_id": ids["p1"], "storage_id": ids["storage"],
        "items": [{"product_id": ids["sencha"], "qty": 50, "purchase_price": "8", "sell_price": "12"}],
    })).json()

    r = await client.post("/api/v1/refunds/providers", json={
        "batch_id": batch["id"], "items": [{"product_id": ids["sencha"], "qty": 10}],
    })
    assert r.status_code == 201
    body = r.json()
    assert body[0]["qty"] == 10
    assert body[0]["refund_amount"] == "80.00"  # 10 * 8


async def test_provider_refund_rejects_overrefund(client):
    ids = await seed_two_providers(client)
    batch = (await client.post("/api/v1/purchases", json={
        "provider_id": ids["p1"], "storage_id": ids["storage"],
        "items": [{"product_id": ids["sencha"], "qty": 5, "purchase_price": "8", "sell_price": "12"}],
    })).json()

    r = await client.post("/api/v1/refunds/providers", json={
        "batch_id": batch["id"], "items": [{"product_id": ids["sencha"], "qty": 100}],
    })
    assert r.status_code == 409


async def test_partial_client_refund_recomputes_net(client):
    ids = await seed_two_providers(client)
    await client.post("/api/v1/purchases", json={
        "provider_id": ids["p1"], "storage_id": ids["storage"],
        "items": [{"product_id": ids["earl"], "qty": 100, "purchase_price": "10", "sell_price": "15"}],
    })
    order = (await client.post("/api/v1/orders", json={
        "client_id": ids["client"], "products": [{"id": ids["earl"], "qty": 20}],
    })).json()

    r = await client.post("/api/v1/refunds/clients", json={
        "items": [{"order_item_id": order["items"][0]["id"], "qty": 5}],
    })
    assert r.status_code == 201
    assert r.json()[0]["refund_amount"] == "75.00"

    # A second refund of 16 should fail: only 15 remain refundable (20 - 5).
    r2 = await client.post("/api/v1/refunds/clients", json={
        "items": [{"order_item_id": order["items"][0]["id"], "qty": 16}],
    })
    assert r2.status_code == 409
