"""Setup helpers shared by tests — keeps each test focused on its assertion."""

from __future__ import annotations

from httpx import AsyncClient


async def _post(client: AsyncClient, path: str, json: dict) -> dict:
    r = await client.post(f"/api/v1{path}", json=json)
    assert r.status_code in (200, 201), f"POST {path} -> {r.status_code} {r.text}"
    return r.json()


async def seed_two_providers(client: AsyncClient) -> dict:
    """
    Sets up: Ahmad Tea provider with Black/Green sub-categories and 2 products,
    a second provider Greenfield with its own product, one storage, one client.
    Returns ids in a flat dict.
    """
    p1 = await _post(client, "/providers", {"name": "Ahmad Tea"})
    p2 = await _post(client, "/providers", {"name": "Greenfield"})

    root_a = await _post(client, "/categories", {"name": "Ahmad Tea", "provider_id": p1["id"]})
    black = await _post(client, "/categories", {"name": "Black Tea", "parent_id": root_a["id"]})
    green = await _post(client, "/categories", {"name": "Green Tea", "parent_id": root_a["id"]})
    root_g = await _post(client, "/categories", {"name": "Greenfield", "provider_id": p2["id"]})

    earl = await _post(client, "/products", {"name": "Earl Grey 500g", "category_id": black["id"]})
    sencha = await _post(client, "/products", {"name": "Sencha 200g", "category_id": green["id"]})
    gf_prod = await _post(client, "/products", {"name": "GF Classic", "category_id": root_g["id"]})

    storage = await _post(client, "/storages", {"name": "Main Warehouse"})
    customer = await _post(client, "/clients", {"name": "Korzinka"})

    return {
        "p1": p1["id"], "p2": p2["id"],
        "earl": earl["id"], "sencha": sencha["id"], "gf_prod": gf_prod["id"],
        "storage": storage["id"], "client": customer["id"],
    }
