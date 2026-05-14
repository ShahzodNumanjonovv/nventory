from tests._helpers import seed_two_providers


async def test_purchase_creates_batch_with_items(client):
    ids = await seed_two_providers(client)
    r = await client.post(
        "/api/v1/purchases",
        json={
            "provider_id": ids["p1"],
            "storage_id": ids["storage"],
            "items": [
                {"product_id": ids["earl"], "qty": 100, "purchase_price": "10.00", "sell_price": "15.00"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["provider_id"] == ids["p1"]
    assert body["items"][0]["qty_purchased"] == 100


async def test_purchase_rejects_cross_provider_product(client):
    ids = await seed_two_providers(client)
    r = await client.post(
        "/api/v1/purchases",
        json={
            "provider_id": ids["p1"],
            "storage_id": ids["storage"],
            "items": [
                {"product_id": ids["gf_prod"], "qty": 1, "purchase_price": "1", "sell_price": "2"},
            ],
        },
    )
    assert r.status_code == 422
    assert "belongs to provider" in r.json()["detail"]


async def test_purchase_rejects_duplicate_product_lines(client):
    ids = await seed_two_providers(client)
    r = await client.post(
        "/api/v1/purchases",
        json={
            "provider_id": ids["p1"],
            "storage_id": ids["storage"],
            "items": [
                {"product_id": ids["earl"], "qty": 1, "purchase_price": "1", "sell_price": "2"},
                {"product_id": ids["earl"], "qty": 2, "purchase_price": "1", "sell_price": "2"},
            ],
        },
    )
    assert r.status_code == 422


async def test_purchase_rejects_future_date(client):
    ids = await seed_two_providers(client)
    r = await client.post(
        "/api/v1/purchases",
        json={
            "provider_id": ids["p1"],
            "storage_id": ids["storage"],
            "purchase_date": "9999-01-01",
            "items": [
                {"product_id": ids["earl"], "qty": 1, "purchase_price": "1", "sell_price": "2"},
            ],
        },
    )
    assert r.status_code == 422
