"""CRUD for master data: providers, categories, products, storages, clients."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select

from app.api.deps import DBSession
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Category, Client, Product, Provider, Storage
from app.schemas.category import CategoryCreate, CategoryRead
from app.schemas.client import ClientCreate, ClientRead
from app.schemas.common import Page, PageParams
from app.schemas.product import ProductCreate, ProductRead
from app.schemas.provider import ProviderCreate, ProviderRead
from app.schemas.storage import StorageCreate, StorageRead

router = APIRouter()

PageDep = Annotated[PageParams, Depends()]


async def _paginate(db, model, schema, page: PageParams) -> Page:
    total = (await db.execute(select(func.count()).select_from(model))).scalar_one()
    rows = (
        await db.execute(
            select(model).order_by(model.id).limit(page.limit).offset(page.offset)
        )
    ).scalars()
    return Page(
        items=[schema.model_validate(r) for r in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


# --- Providers ---------------------------------------------------------------

@router.post("/providers", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
async def create_provider(payload: ProviderCreate, db: DBSession) -> ProviderRead:
    existing = await db.execute(select(Provider).where(Provider.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Provider '{payload.name}' already exists")
    provider = Provider(name=payload.name)
    db.add(provider)
    await db.flush()
    return ProviderRead.model_validate(provider)


@router.get("/providers", response_model=Page[ProviderRead])
async def list_providers(db: DBSession, page: PageDep) -> Page[ProviderRead]:
    return await _paginate(db, Provider, ProviderRead, page)


# --- Categories --------------------------------------------------------------

@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(payload: CategoryCreate, db: DBSession) -> CategoryRead:
    if payload.parent_id is not None:
        parent = await db.get(Category, payload.parent_id)
        if parent is None:
            raise NotFoundError(f"Parent category {payload.parent_id} not found")
    if payload.provider_id is not None:
        provider = await db.get(Provider, payload.provider_id)
        if provider is None:
            raise NotFoundError(f"Provider {payload.provider_id} not found")
    category = Category(
        name=payload.name, parent_id=payload.parent_id, provider_id=payload.provider_id
    )
    db.add(category)
    await db.flush()
    return CategoryRead.model_validate(category)


@router.get("/categories", response_model=Page[CategoryRead])
async def list_categories(db: DBSession, page: PageDep) -> Page[CategoryRead]:
    return await _paginate(db, Category, CategoryRead, page)


# --- Products ----------------------------------------------------------------

@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, db: DBSession) -> ProductRead:
    category = await db.get(Category, payload.category_id)
    if category is None:
        raise NotFoundError(f"Category {payload.category_id} not found")
    product = Product(name=payload.name, category_id=payload.category_id)
    db.add(product)
    await db.flush()
    return ProductRead.model_validate(product)


@router.get("/products", response_model=Page[ProductRead])
async def list_products(db: DBSession, page: PageDep) -> Page[ProductRead]:
    return await _paginate(db, Product, ProductRead, page)


# --- Storages ----------------------------------------------------------------

@router.post("/storages", response_model=StorageRead, status_code=status.HTTP_201_CREATED)
async def create_storage(payload: StorageCreate, db: DBSession) -> StorageRead:
    existing = await db.execute(select(Storage).where(Storage.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Storage '{payload.name}' already exists")
    storage = Storage(name=payload.name, location=payload.location)
    db.add(storage)
    await db.flush()
    return StorageRead.model_validate(storage)


@router.get("/storages", response_model=Page[StorageRead])
async def list_storages(db: DBSession, page: PageDep) -> Page[StorageRead]:
    return await _paginate(db, Storage, StorageRead, page)


# --- Clients -----------------------------------------------------------------

@router.post("/clients", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def create_client(payload: ClientCreate, db: DBSession) -> ClientRead:
    existing = await db.execute(select(Client).where(Client.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Client '{payload.name}' already exists")
    client = Client(name=payload.name)
    db.add(client)
    await db.flush()
    return ClientRead.model_validate(client)


@router.get("/clients", response_model=Page[ClientRead])
async def list_clients(db: DBSession, page: PageDep) -> Page[ClientRead]:
    return await _paginate(db, Client, ClientRead, page)
