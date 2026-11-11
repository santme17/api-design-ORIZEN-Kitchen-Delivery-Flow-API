# app/services/repartidor.py
from fastapi import HTTPException, status

from app.models.enums import EstadoDisponibilidad, EstadoOrden
from app.models.pedido import Pedido
from app.models.repartidor import Repartidor, RepartidorCreate, RepartidorUpdate
from app.repositories.pedido import PedidoRepository
from app.repositories.repartidor import RepartidorRepository

# Un pedido en estos estados ya no ocupa al repartidor
ESTADOS_FINALES = {EstadoOrden.ENTREGADO, EstadoOrden.CANCELADO}


class RepartidorService:
    """Capa 4 - Lógica de Negocio para Repartidor.

    Reglas:
    - Un repartidor eliminado (deleted_at) se comporta como inexistente (404).
    - OCUPADO solo lo pone el sistema al asignar un pedido; no se envía a mano (400).
    - Mientras tenga un pedido activo no se le puede cambiar la disponibilidad
      ni eliminar (409).
    - El borrado es lógico (regla 10).
    """

    def __init__(
        self,
        repartidor_repo: RepartidorRepository,
        pedido_repo: PedidoRepository,  # para saber si tiene pedidos activos
    ) -> None:
        self.repartidor_repo = repartidor_repo
        self.pedido_repo = pedido_repo

    async def get_by_id(self, repartidor_id: int) -> Repartidor:
        repartidor = await self.repartidor_repo.get_by_id(repartidor_id)
        if not repartidor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repartidor no encontrado",
            )
        return repartidor

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        estado: EstadoDisponibilidad | None = None,
    ) -> list[Repartidor]:
        return await self.repartidor_repo.get_multi(skip=skip, limit=limit, estado=estado)

    async def list_pedidos(
        self,
        repartidor_id: int,
        skip: int = 0,
        limit: int = 100,
        estado: EstadoOrden | None = None,
    ) -> list[Pedido]:
        """GET /couriers/:id/orders."""
        await self.get_by_id(repartidor_id)
        return await self.pedido_repo.get_by_repartidor(
            repartidor_id, skip=skip, limit=limit, estado=estado
        )

    async def create(self, repartidor_in: RepartidorCreate) -> Repartidor:
        if repartidor_in.estado_disponibilidad == EstadoDisponibilidad.OCUPADO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un repartidor nuevo no puede registrarse como OCUPADO",
            )
        return await self.repartidor_repo.create(repartidor_in)

    async def update(self, repartidor_id: int, repartidor_in: RepartidorUpdate) -> Repartidor:
        repartidor = await self.get_by_id(repartidor_id)
        nuevo_estado = repartidor_in.estado_disponibilidad

        if nuevo_estado is not None and nuevo_estado != repartidor.estado_disponibilidad:
            if nuevo_estado == EstadoDisponibilidad.OCUPADO:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OCUPADO se asigna automáticamente al asignar un pedido",
                )
            if await self._tiene_pedido_activo(repartidor.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El repartidor tiene un pedido activo; no se puede cambiar su disponibilidad",
                )

        return await self.repartidor_repo.update(repartidor, repartidor_in)

    async def delete(self, repartidor_id: int) -> None:
        repartidor = await self.get_by_id(repartidor_id)
        if await self._tiene_pedido_activo(repartidor.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede eliminar un repartidor con un pedido activo",
            )
        await self.repartidor_repo.soft_delete(repartidor)

    # ==========================================
    # Reglas internas
    # ==========================================

    async def _tiene_pedido_activo(self, repartidor_id: int) -> bool:
        pedidos = await self.pedido_repo.get_by_repartidor(repartidor_id, limit=1000)
        return any(p.estado_actual not in ESTADOS_FINALES for p in pedidos)
