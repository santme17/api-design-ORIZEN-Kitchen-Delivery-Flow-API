# app/services/item_pedido.py
from fastapi import HTTPException, status

from app.models.item_pedido import ItemPedido
from app.repositories.item_pedido import ItemPedidoRepository
from app.repositories.pedido import PedidoRepository


class ItemPedidoService:
    """Capa 4 - Lógica de Negocio para ItemPedido.

    Solo lectura: los ítems se crean junto con el pedido (PedidoService.create)
    y no se editan ni se borran, porque descuadrarían `Pedido.total` (regla 6).
    """

    def __init__(self, item_repo: ItemPedidoRepository, pedido_repo: PedidoRepository) -> None:
        self.item_repo = item_repo
        self.pedido_repo = pedido_repo

    async def get_by_id(self, item_id: int) -> ItemPedido:
        item = await self.item_repo.get_by_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ítem de pedido no encontrado",
            )
        return item

    async def list_by_pedido(self, pedido_id: int) -> list[ItemPedido]:
        """GET /orders/:id/items."""
        if not await self.pedido_repo.get_by_id(pedido_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido no encontrado",
            )
        return await self.item_repo.get_by_pedido(pedido_id)
