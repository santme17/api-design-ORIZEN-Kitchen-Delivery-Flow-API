# app/routers/repartidores.py
from fastapi import APIRouter, status

from app.api.deps import RepartidorServiceDep, SoloAdmin
from app.models.enums import EstadoDisponibilidad, EstadoOrden
from app.models.pedido import PedidoPublic
from app.models.repartidor import RepartidorCreate, RepartidorPublic, RepartidorUpdate

router = APIRouter(prefix="/couriers", tags=["Repartidores"])


@router.post(
    "/",
    response_model=RepartidorPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar repartidor",
    dependencies=[SoloAdmin],
    description="Registra un repartidor (no puede crearse como OCUPADO).",
)
async def create_repartidor(
    repartidor_in: RepartidorCreate,
    service: RepartidorServiceDep,
) -> RepartidorPublic:
    return await service.create(repartidor_in)


@router.get(
    "/",
    response_model=list[RepartidorPublic],
    summary="Listar repartidores",
    description="Lista paginada de repartidores. `estado` filtra por disponibilidad.",
)
async def list_repartidores(
    service: RepartidorServiceDep,
    skip: int = 0,
    limit: int = 100,
    estado: EstadoDisponibilidad | None = None,
) -> list[RepartidorPublic]:
    return await service.list_all(skip=skip, limit=limit, estado=estado)


@router.get(
    "/{repartidor_id}",
    response_model=RepartidorPublic,
    summary="Obtener repartidor por ID",
    description="Busca un repartidor por ID o devuelve 404 si no existe o fue eliminado.",
)
async def get_repartidor(
    repartidor_id: int,
    service: RepartidorServiceDep,
) -> RepartidorPublic:
    return await service.get_by_id(repartidor_id)


@router.get(
    "/{repartidor_id}/orders",
    response_model=list[PedidoPublic],
    summary="Pedidos de un repartidor",
    description="Lista los pedidos asignados al repartidor, con filtro opcional por estado.",
)
async def list_pedidos_repartidor(
    repartidor_id: int,
    service: RepartidorServiceDep,
    skip: int = 0,
    limit: int = 100,
    estado: EstadoOrden | None = None,
) -> list[PedidoPublic]:
    return await service.list_pedidos(repartidor_id, skip=skip, limit=limit, estado=estado)


@router.patch(
    "/{repartidor_id}",
    response_model=RepartidorPublic,
    summary="Actualizar repartidor",
    dependencies=[SoloAdmin],
    description="Actualiza los campos enviados. OCUPADO solo lo asigna el sistema.",
)
async def update_repartidor(
    repartidor_id: int,
    repartidor_in: RepartidorUpdate,
    service: RepartidorServiceDep,
) -> RepartidorPublic:
    return await service.update(repartidor_id, repartidor_in)


@router.delete(
    "/{repartidor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar repartidor",
    dependencies=[SoloAdmin],
    description="Borrado lógico (deleted_at). 409 si tiene un pedido activo.",
)
async def delete_repartidor(
    repartidor_id: int,
    service: RepartidorServiceDep,
) -> None:
    await service.delete(repartidor_id)
