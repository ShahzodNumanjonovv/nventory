from fastapi import APIRouter

from app.api.v1 import analytics, catalog, orders, products, purchases, refunds

api_router = APIRouter()
api_router.include_router(catalog.router)
api_router.include_router(purchases.router)
api_router.include_router(refunds.router)
api_router.include_router(products.router)
api_router.include_router(orders.router)
api_router.include_router(analytics.router)
