# app/routers/estados_pedido.py
from fastapi import APIRouter, HTTPException, status

from app.api.deps import EstadoPedidoServiceDep, NotificadorDep, UsuarioActualDep
from app.models.enums import EstadoOrden, RolUsuario
from app.models.estado_pedido import EstadoPedidoCreate, EstadoPedidoPublic

# Historial append-only (regla 2): no existen PATCH ni DELETE sobre estados.
router = APIRouter(prefix="/orders", tags=["Estados de pedido"])

# Quién puede registrar cada estado. El ADMIN puede todos.
# EN_COLA no está porque lo pone el sistema al crear el pedido.
ROLES_POR_ESTADO: dict[EstadoOrden, set[RolUsuario]] = {
    EstadoOrden.EN_PREPARACION: {RolUsuario.COCINA},
    EstadoOrden.EMPAQUETADO: {RolUsuario.COCINA},
    EstadoOrden.EN_TRANSITO: {RolUsuario.REPARTIDOR},
    EstadoOrden.ENTREGADO: {RolUsuario.REPARTIDOR, RolUsuario.CAJERO},  # cajero: pedidos RECOGER
    EstadoOrden.CANCELADO: {RolUsuario.CAJERO},
}


def validar_rol_para_estado(rol: RolUsuario, estado: EstadoOrden) -> None:
    """403 si el rol del usuario no puede poner ese estado."""
    if rol == RolUsuario.ADMIN:
        return
    if rol not in ROLES_POR_ESTADO.get(estado, set()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"El rol {rol.value} no puede marcar un pedido como {estado.value}",
        )


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
        "Registra un cambio de estado. Primero revisa que tu rol pueda poner ese estado "
        "(403 si no), luego valida la máquina de estados (409 si la transición no es válida). "
        "COCINA: EN_PREPARACION y EMPAQUETADO. REPARTIDOR: EN_TRANSITO y ENTREGADO. "
        "CAJERO: ENTREGADO (recoger) y CANCELADO. ADMIN: todos."
    ),
)
async def create_estado_pedido(
    pedido_id: int,
    estado_in: EstadoPedidoCreate,
    service: EstadoPedidoServiceDep,
    usuario: UsuarioActualDep,
    notificador: NotificadorDep,
) -> EstadoPedidoPublic:
    validar_rol_para_estado(usuario.rol, estado_in.estado)
    estado = await service.create(pedido_id, estado_in, usuario_id=usuario.id)
    await notificador.publicar("estado_cambiado", EstadoPedidoPublic.model_validate(estado).model_dump(mode="json"))
    return estado
