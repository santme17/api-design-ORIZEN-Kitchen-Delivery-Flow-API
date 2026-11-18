# app/routers/items_pedido.py
from fastapi import APIRouter

from app.api.deps import ItemPedidoServiceDep
from app.models.item_pedido import ItemPedidoPublic

# Solo lectura: los ítems se crean junto con el pedido (POST /orders) y no se
# editan ni se borran, porque descuadrarían el total (regla 6).
router = APIRouter(tags=["Ítems de pedido"])


@router.get(
    "/orders/{pedido_id}/items",
    response_model=list[ItemPedidoPublic],
    summary="Listar ítems de un pedido",
    description="Devuelve las líneas del pedido con el precio congelado al momento de la compra.",
)
async def list_items_pedido(
    pedido_id: int,
    service: ItemPedidoServiceDep,
) -> list[ItemPedidoPublic]:
    return await service.list_by_pedido(pedido_id)


@router.get(
    "/order-items/{item_id}",
    response_model=ItemPedidoPublic,
    summary="Obtener ítem por ID",
    description="Busca una línea de pedido por ID o devuelve 404 si no existe.",
)
async def get_item_pedido(
    item_id: int,
    service: ItemPedidoServiceDep,
) -> ItemPedidoPublic:
    return await service.get_by_id(item_id)
