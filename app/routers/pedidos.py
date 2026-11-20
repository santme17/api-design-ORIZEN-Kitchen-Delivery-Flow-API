# app/routers/pedidos.py
from datetime import datetime

from fastapi import APIRouter, status

from app.api.deps import AdminOCajero, EstadoPedidoServiceDep, PedidoServiceDep, UsuarioActualDep
from app.models.enums import EstadoOrden, TipoPedido
from app.models.estado_pedido import EstadoPedidoPublic
from app.models.pedido import (
    PedidoAsignarRepartidor,
    PedidoCancelar,
    PedidoCreate,
    PedidoPublic,
    PedidoUpdate,
)

# Los pedidos no se borran: se cancelan con POST /orders/{id}/cancel.
router = APIRouter(prefix="/orders", tags=["Pedidos"])


@router.post(
    "/",
    response_model=PedidoPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Crear pedido",
    dependencies=[AdminOCajero],
    description=(
        "Crea el pedido con sus ítems. El servidor congela los precios, calcula el total, "
        "genera el código de orden y deja el estado inicial EN_COLA."
    ),
)
async def create_pedido(
    pedido_in: PedidoCreate,
    service: PedidoServiceDep,
    usuario: UsuarioActualDep,
) -> PedidoPublic:
    return await service.create(pedido_in, usuario_id=usuario.id)


@router.get(
    "/",
    response_model=list[PedidoPublic],
    summary="Listar pedidos",
    description="Lista paginada de pedidos con filtros opcionales por estado, tipo, cliente y rango de fechas.",
)
async def list_pedidos(
    service: PedidoServiceDep,
    skip: int = 0,
    limit: int = 100,
    estado: EstadoOrden | None = None,
    tipo_pedido: TipoPedido | None = None,
    cliente_id: int | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
) -> list[PedidoPublic]:
    return await service.list_all(
        skip=skip,
        limit=limit,
        estado=estado,
        tipo_pedido=tipo_pedido,
        cliente_id=cliente_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )


@router.get(
    "/{pedido_id}",
    response_model=PedidoPublic,
    summary="Obtener pedido por ID",
    description="Busca un pedido por ID o devuelve 404 si no existe.",
)
async def get_pedido(
    pedido_id: int,
    service: PedidoServiceDep,
) -> PedidoPublic:
    return await service.get_by_id(pedido_id)


@router.patch(
    "/{pedido_id}",
    response_model=PedidoPublic,
    summary="Actualizar pedido",
    dependencies=[AdminOCajero],
    description="Cambia la dirección de entrega (solo DOMICILIO). 409 si el pedido ya salió o terminó.",
)
async def update_pedido(
    pedido_id: int,
    pedido_in: PedidoUpdate,
    service: PedidoServiceDep,
) -> PedidoPublic:
    return await service.update(pedido_id, pedido_in)


@router.patch(
    "/{pedido_id}/courier",
    response_model=PedidoPublic,
    summary="Asignar repartidor",
    dependencies=[AdminOCajero],
    description="Asigna un repartidor DISPONIBLE a un pedido DOMICILIO y lo deja OCUPADO (409 si no se puede).",
)
async def assign_repartidor(
    pedido_id: int,
    asignar_in: PedidoAsignarRepartidor,
    service: PedidoServiceDep,
) -> PedidoPublic:
    return await service.assign_courier(pedido_id, asignar_in)


@router.post(
    "/{pedido_id}/cancel",
    response_model=EstadoPedidoPublic,
    summary="Cancelar pedido",
    dependencies=[AdminOCajero],
    description=(
        "Registra el estado CANCELADO (pasa por la misma validación de transiciones) "
        "y libera al repartidor si tenía uno."
    ),
)
async def cancel_pedido(
    pedido_id: int,
    cancelar_in: PedidoCancelar,
    service: EstadoPedidoServiceDep,
    usuario: UsuarioActualDep,
) -> EstadoPedidoPublic:
    return await service.cancelar(pedido_id, cancelar_in, usuario_id=usuario.id)