# app/routers/productos.py
from fastapi import APIRouter, status

from app.api.deps import LimitQuery, ProductoServiceDep, SkipQuery, SoloAdmin
from app.models.producto import ProductoCreate, ProductoPublic, ProductoUpdate

router = APIRouter(prefix="/products", tags=["Productos"])


@router.post(
    "/",
    response_model=ProductoPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Crear producto",
    dependencies=[SoloAdmin],
    description="Agrega un producto al menú validando que el nombre no exista.",
)
async def create_producto(
    producto_in: ProductoCreate,
    service: ProductoServiceDep,
) -> ProductoPublic:
    return await service.create(producto_in)


@router.get(
    "/",
    response_model=list[ProductoPublic],
    summary="Listar productos",
    description="Lista paginada del menú. `search` filtra por nombre y `only_active` oculta los desactivados.",
)
async def list_productos(
    service: ProductoServiceDep,
    skip: SkipQuery = 0,
    limit: LimitQuery = 100,
    search: str | None = None,
    only_active: bool = False,
) -> list[ProductoPublic]:
    return await service.list_all(skip=skip, limit=limit, search=search, only_active=only_active)


@router.get(
    "/{producto_id}",
    response_model=ProductoPublic,
    summary="Obtener producto por ID",
    description="Busca un producto por ID o devuelve 404 si no existe.",
)
async def get_producto(
    producto_id: int,
    service: ProductoServiceDep,
) -> ProductoPublic:
    return await service.get_by_id(producto_id)


@router.patch(
    "/{producto_id}",
    response_model=ProductoPublic,
    summary="Actualizar producto",
    dependencies=[SoloAdmin],
    description="Actualiza nombre, precio o disponibilidad. El cambio de precio no altera pedidos existentes.",
)
async def update_producto(
    producto_id: int,
    producto_in: ProductoUpdate,
    service: ProductoServiceDep,
) -> ProductoPublic:
    return await service.update(producto_id, producto_in)


@router.delete(
    "/{producto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar producto",
    dependencies=[SoloAdmin],
    description="Borrado lógico: el producto queda inactivo y sale del menú.",
)
async def delete_producto(
    producto_id: int,
    service: ProductoServiceDep,
) -> None:
    await service.delete(producto_id)
