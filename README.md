# Wholesale Inventory API

FastAPI + Postgres backend for a wholesale operation: buy products in **batches**
from **providers**, hold them in **storages**, sell them to **clients**, and
handle **refunds** on either side.

Orders are FIFO-allocated against the oldest available batch per product, so the
frontend never has to think about `batch_id` mapping.

## Stack

- Python 3.11+
- FastAPI (async)
- SQLAlchemy 2.0 (async, with `asyncpg`)
- Alembic migrations
- Pydantic v2 + pydantic-settings
- PostgreSQL 16

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

API: <http://localhost:8000>
Interactive docs: <http://localhost:8000/docs>

Migrations run automatically on startup.

## Local dev (without Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                      # then edit DATABASE_URL if needed
alembic upgrade head
uvicorn app.main:app --reload
```

## Domain model

```
Provider ── 1:N ── Category (root)        Category ── 1:N ── Category (children)
                       │                        │
                       └───── 1:N ─────── Product
                                              │
                                              │
Storage ── 1:N ── Batch ── 1:N ── BatchItem ◄─┘
                    │                 │
                    │                 └─ N:1 ── OrderItem ──N:1── Order ──N:1── Client
                    │                 │
                    │                 └─ 1:N ── ProviderRefund
                    │
                    └─ N:1 ── Provider                 OrderItem ── 1:N ── ClientRefund
```

- **Category tree**: a *root* category (no parent) is tied to a single Provider.
  Subcategories inherit the provider through their root ancestor.
- **Product** belongs to one category.
- **Batch** = one purchase event (provider + storage + date). A batch carries
  multiple `BatchItem`s (product × qty × purchase price × sell price).
- **Order** is a sale; each `OrderItem` is tied to a specific `BatchItem`
  (assigned by FIFO), so cost/revenue per batch is always traceable.
- **Refunds** flow both ways: `ProviderRefund` reduces stock in a batch_item;
  `ClientRefund` reverses an order_item (puts stock back).

## Stock accounting (single source of truth)

For any `batch_item`, available qty is:

```
qty_purchased
    − Σ provider_refunds.qty
    − Σ order_items.qty
    + Σ client_refunds.qty   (only those tied to this batch_item's order_items)
```

This is implemented as a reusable SQL expression in
[`app/services/stock.py`](app/services/stock.py) so every endpoint
(available products / order creation / refund validation / historical snapshots)
applies the exact same accounting.

## Endpoints (spec)

All under `/api/v1`.

| Method | Path                              | Description                                            |
| ------ | --------------------------------- | ------------------------------------------------------ |
| POST   | `/purchases`                      | Buy products from a provider into a storage           |
| POST   | `/refunds/providers`              | Refund a batch (full or partial) back to provider     |
| POST   | `/refunds/clients`                | Refund order lines (full or partial) from a client    |
| GET    | `/products/available`             | Products available to order (`id, name, category_name, price, qty`) |
| POST   | `/orders`                         | Create a client order (FIFO batch allocation)         |
| GET    | `/storage/remaining?date=YYYY-MM-DD` | Storage-by-product qty as of a given date         |
| GET    | `/analytics/profit-per-batch`     | Per-batch revenue / cost / profit, net of refunds     |

Master-data setup endpoints (CRUD):
`/providers`, `/categories`, `/products`, `/storages`, `/clients`.

## Example flow

```bash
# 1. providers, categories, products, storage, client
curl -X POST localhost:8000/api/v1/providers \
  -H 'content-type: application/json' -d '{"name":"Ahmad Tea"}'
# -> {"id": 1, ...}

curl -X POST localhost:8000/api/v1/categories \
  -H 'content-type: application/json' \
  -d '{"name":"Ahmad Tea","provider_id":1}'
# -> {"id": 1, ...} root

curl -X POST localhost:8000/api/v1/categories \
  -H 'content-type: application/json' \
  -d '{"name":"Black Tea","parent_id":1}'
# -> {"id": 2, ...}

curl -X POST localhost:8000/api/v1/products \
  -H 'content-type: application/json' \
  -d '{"name":"Earl Grey 500g","category_id":2}'

curl -X POST localhost:8000/api/v1/storages \
  -H 'content-type: application/json' -d '{"name":"Main Warehouse"}'

curl -X POST localhost:8000/api/v1/clients \
  -H 'content-type: application/json' -d '{"name":"Korzinka"}'

# 2. purchase a batch
curl -X POST localhost:8000/api/v1/purchases \
  -H 'content-type: application/json' \
  -d '{"provider_id":1,"storage_id":1,
       "items":[{"product_id":1,"qty":100,"purchase_price":"10.00","sell_price":"15.00"}]}'

# 3. browse stock & place an order
curl localhost:8000/api/v1/products/available
curl -X POST localhost:8000/api/v1/orders \
  -H 'content-type: application/json' \
  -d '{"client_id":1,"products":[{"id":1,"qty":20}]}'

# 4. analytics
curl 'localhost:8000/api/v1/storage/remaining?date=2026-05-14'
curl localhost:8000/api/v1/analytics/profit-per-batch
```

## Project layout

```
app/
  core/         settings, async engine, exceptions
  models/       SQLAlchemy 2.0 ORM models
  schemas/      Pydantic v2 DTOs
  services/     business logic (purchase, refund, order, analytics, stock math)
  api/v1/       FastAPI routers (thin — delegate to services)
  main.py       app factory
alembic/        migrations
```

## Tests

Test scaffolding lives in `tests/`. Add unit tests for `app/services/*` and
integration tests against a throwaway Postgres (e.g. `testcontainers`).
Pytest is wired with `asyncio_mode = "auto"` in `pyproject.toml`.
