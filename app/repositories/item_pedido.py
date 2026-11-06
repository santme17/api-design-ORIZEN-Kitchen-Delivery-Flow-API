# app/repositories/item_pedido.py
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.models.item_pedido import ItemPedido


class ItemPedidoRepository:
    """Capa 3 - Acceso a Datos (Repositorio) para ItemPedido.

    Solo lectura: los ítems se insertan dentro de `PedidoRepository.create`
    (junto con el pedido) y la API no permite editarlos ni borrarlos, porque
    cambiarlos descuadraría `Pedido.total`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, item_id: int) -> ItemPedido | None:
        return await self.session.get(ItemPedido, item_id)

    async def get_by_pedido(self, pedido_id: int) -> list[ItemPedido]:
        """GET /orders/:id/items."""
        statement = (
            select(ItemPedido)
            .where(ItemPedido.pedido_id == pedido_id)
            .order_by(col(ItemPedido.id))
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def calcular_total(self, pedido_id: int) -> Decimal:
        """Suma cantidad * precio_unitario en la base de datos (regla 6: total verificable)."""
        statement = select(
            func.coalesce(
                func.sum(col(ItemPedido.cantidad) * col(ItemPedido.precio_unitario)), 0
            )
        ).where(ItemPedido.pedido_id == pedido_id)
        result = await self.session.execute(statement)
        return Decimal(str(result.scalar_one())).quantize(Decimal("0.01"))
