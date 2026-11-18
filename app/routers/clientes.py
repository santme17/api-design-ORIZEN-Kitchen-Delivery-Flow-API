# app/routers/clientes.py
from fastapi import APIRouter, status

from app.api.deps import ClienteServiceDep
from app.models.cliente import ClienteCreate, ClientePublic, ClienteUpdate

# Los clientes no se borran (tienen pedidos asociados): no hay DELETE.
router = APIRouter(prefix="/customers", tags=["Clientes"])


@router.post(
    "/",
    response_model=ClientePublic,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar cliente",
    description="Registra un nuevo cliente con nombre y teléfono.",
)
async def create_cliente(
    cliente_in: ClienteCreate,
    service: ClienteServiceDep,
) -> ClientePublic:
    return await service.create(cliente_in)


@router.get(
    "/",
    response_model=list[ClientePublic],
    summary="Listar clientes",
    description="Lista paginada de clientes. `search` filtra por nombre.",
)
async def list_clientes(
    service: ClienteServiceDep,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> list[ClientePublic]:
    return await service.list_all(skip=skip, limit=limit, search=search)


@router.get(
    "/{cliente_id}",
    response_model=ClientePublic,
    summary="Obtener cliente por ID",
    description="Busca un cliente por ID o devuelve 404 si no existe.",
)
async def get_cliente(
    cliente_id: int,
    service: ClienteServiceDep,
) -> ClientePublic:
    return await service.get_by_id(cliente_id)


@router.patch(
    "/{cliente_id}",
    response_model=ClientePublic,
    summary="Actualizar cliente",
    description="Actualiza solo los campos enviados. Nombre y teléfono no pueden quedar vacíos.",
)
async def update_cliente(
    cliente_id: int,
    cliente_in: ClienteUpdate,
    service: ClienteServiceDep,
) -> ClientePublic:
    return await service.update(cliente_id, cliente_in)
