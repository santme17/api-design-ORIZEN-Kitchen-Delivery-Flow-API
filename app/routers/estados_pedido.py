# app/routers/estados_pedido.py
from fastapi import APIRouter, status

from app.api.deps import EstadoPedidoServiceDep, NotificadorDep, UsuarioActualDep
from app.models.estado_pedido import EstadoPedidoCreate, EstadoPedidoPublic

# Historial append-only (regla 2): no existen PATCH ni DELETE sobre estados.
router = APIRouter(prefix="/orders", tags=["Estados de pedido"])


@router.get(
    "/{pedido_id}/statuses",
    response_model=list[EstadoPedidoPublic],
    summary="Historial de estados",
    description="Devuelve los cambios de estado del pedido en orden cronológico.",
)
async def list_estados_pedido(
    pedido_id: int,
    service: EstadoPedidoServiceDep,
) -> list[EstadoPedidoPublic]:
    return await service.list_by_pedido(pedido_id)


@router.post(
    "/{pedido_id}/statuses",
    response_model=EstadoPedidoPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo estado",
    description=(
        "Registra un cambio de estado validando la máquina de estados (409 si la "
        "transición no es válida). Actualiza `estado_actual` del pedido en la misma transacción."
    ),
)
async def create_estado_pedido(
    pedido_id: int,
    estado_in: EstadoPedidoCreate,
    service: EstadoPedidoServiceDep,
    usuario: UsuarioActualDep,
    notificador: NotificadorDep,
) -> EstadoPedidoPublic:
    estado = await service.create(pedido_id, estado_in, usuario_id=usuario.id)
    await notificador.publicar("estado_cambiado", EstadoPedidoPublic.model_validate(estado).model_dump(mode="json"))
    return estado
