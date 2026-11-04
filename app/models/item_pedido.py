# Paso 3: importaciones
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.pedido import Pedido
    from app.models.producto import Producto


# Paso 4: clase Base
class ItemPedidoBase(SQLModel):
    producto_id: int = Field(foreign_key="producto.id")
    cantidad: int = Field(gt=0)


# Paso 5: tabla de base de datos
class ItemPedido(ItemPedidoBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    pedido_id: int = Field(foreign_key="pedido.id", index=True)
    # Precio del producto al momento de la compra (lo fija el servidor)
    precio_unitario: Decimal = Field(max_digits=10, decimal_places=2)

    # Relaciones (no son columnas)
    pedido: Optional["Pedido"] = Relationship(back_populates="items")
    producto: Optional["Producto"] = Relationship(back_populates="items")


# Paso 6: DTO de creación (se usa anidado dentro de PedidoCreate)
class ItemPedidoCreate(ItemPedidoBase):
    pass


# Paso 7: DTO de edición
class ItemPedidoUpdate(SQLModel):
    cantidad: int | None = Field(default=None, gt=0)


# Paso 8: DTO de respuesta
class ItemPedidoPublic(ItemPedidoBase):
    id: int
    pedido_id: int
    precio_unitario: Decimal