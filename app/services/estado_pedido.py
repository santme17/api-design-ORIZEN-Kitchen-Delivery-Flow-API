# app/services/estado_pedido.py
from fastapi import HTTPException, status

from app.models.enums import EstadoDisponibilidad, EstadoOrden, TipoPedido
from app.models.estado_pedido import EstadoPedido, EstadoPedidoCreate
from app.models.pedido import Pedido, PedidoCancelar
from app.repositories.estado_pedido import EstadoPedidoRepository
from app.repositories.pedido import PedidoRepository
from app.repositories.repartidor import RepartidorRepository
from app.repositories.usuario import UsuarioRepository

# ==========================================
# Máquina de estados (regla 1 del README)
# EN_COLA -> EN_PREPARACION -> EMPAQUETADO -> EN_TRANSITO -> ENTREGADO
# RECOGER salta EN_TRANSITO. CANCELADO solo antes de EN_TRANSITO.
# ==========================================
TRANSICIONES: dict[EstadoOrden, set[EstadoOrden]] = {
    EstadoOrden.EN_COLA: {EstadoOrden.EN_PREPARACION, EstadoOrden.CANCELADO},
    EstadoOrden.EN_PREPARACION: {EstadoOrden.EMPAQUETADO, EstadoOrden.CANCELADO},
    EstadoOrden.EMPAQUETADO: {
        EstadoOrden.EN_TRANSITO,  # solo DOMICILIO
        EstadoOrden.ENTREGADO,  # solo RECOGER
        EstadoOrden.CANCELADO,
    },
    EstadoOrden.EN_TRANSITO: {EstadoOrden.ENTREGADO},
    EstadoOrden.ENTREGADO: set(),
    EstadoOrden.CANCELADO: set(),
}

ESTADOS_FINALES = {EstadoOrden.ENTREGADO, EstadoOrden.CANCELADO}


def _conflicto(detalle: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detalle)


def validar_transicion(pedido: Pedido, nuevo: EstadoOrden) -> None:
    """Lanza 409 si el pedido no puede pasar de su estado actual a `nuevo`."""
    actual = pedido.estado_actual

    if nuevo not in TRANSICIONES[actual]:
        raise _conflicto(f"Transición inválida: {actual.value} -> {nuevo.value}")

    if actual == EstadoOrden.EMPAQUETADO:
        if pedido.tipo_pedido == TipoPedido.RECOGER and nuevo == EstadoOrden.EN_TRANSITO:
            raise _conflicto("Los pedidos RECOGER no pasan por EN_TRANSITO")
        if pedido.tipo_pedido == TipoPedido.DOMICILIO and nuevo == EstadoOrden.ENTREGADO:
            raise _conflicto("Un pedido DOMICILIO debe pasar por EN_TRANSITO antes de ENTREGADO")

    if nuevo == EstadoOrden.EN_TRANSITO and pedido.repartidor_id is None:
        raise _conflicto("Asigna un repartidor antes de enviar el pedido (EN_TRANSITO)")


class EstadoPedidoService:
    """Capa 4 - Lógica de Negocio para el historial de estados de un pedido.

    Reglas:
    - El pedido debe existir (404).
    - Solo se permiten las transiciones de la máquina de estados (409).
    - Quien registra el cambio debe ser un usuario existente y activo (400).
    - Historial append-only: no hay update ni delete (regla 2).
    - Al terminar el pedido (ENTREGADO o CANCELADO) el repartidor vuelve a DISPONIBLE,
      en la MISMA transacción que el nuevo estado.
    """

    def __init__(
        self,
        estado_repo: EstadoPedidoRepository,
        pedido_repo: PedidoRepository,
        usuario_repo: UsuarioRepository,
        repartidor_repo: RepartidorRepository,
    ) -> None:
        self.estado_repo = estado_repo
        self.pedido_repo = pedido_repo
        self.usuario_repo = usuario_repo
        self.repartidor_repo = repartidor_repo

    async def list_by_pedido(self, pedido_id: int) -> list[EstadoPedido]:
        """GET /orders/:id/statuses."""
        await self._get_pedido(pedido_id)
        return await self.estado_repo.get_by_pedido(pedido_id)

    async def create(
        self, pedido_id: int, estado_in: EstadoPedidoCreate, *, usuario_id: int
    ) -> EstadoPedido:
        """POST /orders/:id/statuses. `usuario_id` sale del JWT."""
        pedido = await self._get_pedido(pedido_id)
        await self._validar_usuario(usuario_id)
        validar_transicion(pedido, estado_in.estado)

        if estado_in.estado in ESTADOS_FINALES:
            await self._liberar_repartidor(pedido)

        # El repositorio guarda el estado + Pedido.estado_actual (+ el repartidor
        # modificado arriba, que está en la misma sesión) en un solo commit.
        return await self.estado_repo.create(pedido, estado_in, usuario_id=usuario_id)

    async def cancelar(
        self, pedido_id: int, cancelar_in: PedidoCancelar, *, usuario_id: int
    ) -> EstadoPedido:
        """POST /orders/:id/cancel. Es un cambio de estado más (pasa por la misma validación)."""
        return await self.create(
            pedido_id,
            EstadoPedidoCreate(estado=EstadoOrden.CANCELADO, observacion=cancelar_in.observacion),
            usuario_id=usuario_id,
        )

    # ==========================================
    # Reglas internas
    # ==========================================

    async def _get_pedido(self, pedido_id: int) -> Pedido:
        pedido = await self.pedido_repo.get_by_id(pedido_id)
        if not pedido:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido no encontrado",
            )
        return pedido

    async def _validar_usuario(self, usuario_id: int) -> None:
        usuario = await self.usuario_repo.get_by_id(usuario_id)
        if not usuario or not usuario.activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario que registra el cambio no existe o está inactivo",
            )

    async def _liberar_repartidor(self, pedido: Pedido) -> None:
        if pedido.repartidor_id is None:
            return
        repartidor = await self.repartidor_repo.get_by_id(
            pedido.repartidor_id, include_deleted=True
        )
        if repartidor and repartidor.estado_disponibilidad == EstadoDisponibilidad.OCUPADO:
            repartidor.estado_disponibilidad = EstadoDisponibilidad.DISPONIBLE
