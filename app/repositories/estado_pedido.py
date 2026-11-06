# app/repositories/estado_pedido.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.models.estado_pedido import EstadoPedido, EstadoPedidoCreate
from app.models.pedido import Pedido


class EstadoPedidoRepository:
    """Capa 3 - Acceso a Datos (Repositorio) para EstadoPedido.

    Historial append-only: solo se agregan registros. No hay update ni delete.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ==========================================
    # READ
    # ==========================================

    async def get_by_pedido(self, pedido_id: int) -> list[EstadoPedido]:
        """GET /orders/:id/statuses, en orden cronológico."""
        statement = (
            select(EstadoPedido)
            .where(EstadoPedido.pedido_id == pedido_id)
            .order_by(col(EstadoPedido.fecha_cambio), col(EstadoPedido.id))
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_last(self, pedido_id: int) -> EstadoPedido | None:
        """Último estado registrado del pedido (útil para validar la transición)."""
        statement = (
            select(EstadoPedido)
            .where(EstadoPedido.pedido_id == pedido_id)
            .order_by(col(EstadoPedido.fecha_cambio).desc(), col(EstadoPedido.id).desc())
            .limit(1)
        )
        result = await self.session.execute(statement)
        return result.scalars().first()

    # ==========================================
    # CREATE
    # ==========================================

    async def create(
        self,
        db_pedido: Pedido,
        estado_in: EstadoPedidoCreate,
        *,
        usuario_id: int,
    ) -> EstadoPedido:
        """POST /orders/:id/statuses (también sirve para cancelar).

        Inserta el historial Y actualiza `Pedido.estado_actual` en la MISMA
        transacción (regla 3). El servicio ya validó que la transición sea legal.
        """
        db_estado = EstadoPedido.model_validate(
            estado_in, update={"pedido_id": db_pedido.id, "usuario_id": usuario_id}
        )
        db_pedido.estado_actual = estado_in.estado

        try:
            self.session.add(db_estado)
            self.session.add(db_pedido)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(db_estado)
        return db_estado