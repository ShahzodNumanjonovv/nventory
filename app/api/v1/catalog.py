"""CRUD for master data: providers, categories, products, storages, clients."""

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import DBSession
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Category, Client, Product, Provider, Storage
from app.schemas.category import CategoryCreate, CategoryRead
from app.schemas.client import ClientCreate, ClientRead
from app.schemas.product import ProductCreate, ProductRead
from app.schemas.provider import ProviderCreate, ProviderRead
from app.schemas.storage import StorageCreate, StorageRead

router = APIRouter()


# --- Providers ---------------------------------------------------------------

@router.post("/providers", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
async def create_provider(payload: ProviderCreate, db: DBSession) -> Provider:
    existing = await db.execute(select(Provider).where(Provider.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Provider '{payload.name}' already exists")
    provider = Provider(name=payload.name)
    db.add(provider)
    await db.flush()
    return provider


@router.get("/providers", response_model=list[ProviderRead])
async def list_providers(db: DBSession) -> list[Provider]:
    rows = await db.execute(select(Provider).order_by(Provider.id))
    return list(rows.scalars())


# --- Categories --------------------------------------------------------------

@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(payload: CategoryCreate, db: DBSession) -> Category:
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
    return category


@router.get("/categories", response_model=list[CategoryRead])
async def list_categories(db: DBSession) -> list[Category]:
    rows = await db.execute(select(Category).order_by(Category.id))
    return list(rows.scalars())


# --- Products ----------------------------------------------------------------

@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, db: DBSession) -> Product:
    category = await db.get(Category, payload.category_id)
    if category is None:
        raise NotFoundError(f"Category {payload.category_id} not found")
    # Products must attach to a leaf (or at least a non-root) is not a hard rule in the spec,
    # but root-category products tend to be wrong in practice. We allow them either way.
    product = Product(name=payload.name, category_id=payload.category_id)
    db.add(product)
    await db.flush()
    return product


# --- Storages ----------------------------------------------------------------

@router.post("/storages", response_model=StorageRead, status_code=status.HTTP_201_CREATED)
async def create_storage(payload: StorageCreate, db: DBSession) -> Storage:
    existing = await db.execute(select(Storage).where(Storage.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Storage '{payload.name}' already exists")
    storage = Storage(name=payload.name, location=payload.location)
    db.add(storage)
    await db.flush()
    return storage


@router.get("/storages", response_model=list[StorageRead])
async def list_storages(db: DBSession) -> list[Storage]:
    rows = await db.execute(select(Storage).order_by(Storage.id))
    return list(rows.scalars())


# --- Clients -----------------------------------------------------------------

@router.post("/clients", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def create_client(payload: ClientCreate, db: DBSession) -> Client:
    existing = await db.execute(select(Client).where(Client.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Client '{payload.name}' already exists")
    client = Client(name=payload.name)
    db.add(client)
    await db.flush()
    return client


@router.get("/clients", response_model=list[ClientRead])
async def list_clients(db: DBSession) -> list[Client]:
    rows = await db.execute(select(Client).order_by(Client.id))
    return list(rows.scalars())
