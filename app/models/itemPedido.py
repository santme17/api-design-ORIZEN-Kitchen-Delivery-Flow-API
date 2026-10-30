# Paso 3: importaciones
from decimal import Decimal
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


# Paso 4: clase Base
class ItemPedidoBase(SQLModel):
    producto_id: UUID = Field(foreign_key="producto.id")
    cantidad: int = Field(gt=0)


# Paso 5: tabla de base de datos
class ItemPedido(ItemPedidoBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pedido_id: UUID = Field(foreign_key="pedido.id", index=True)
    # Precio del producto al momento de la compra (lo fija el servidor)
    precio_unitario: Decimal = Field(max_digits=10, decimal_places=2)


# Paso 6: DTO de creación (se usa anidado dentro de PedidoCreate)
class ItemPedidoCreate(ItemPedidoBase):
    pass


# Paso 7: DTO de edición
class ItemPedidoUpdate(SQLModel):
    cantidad: int | None = Field(default=None, gt=0)


# Paso 8: DTO de respuesta
class ItemPedidoPublic(ItemPedidoBase):
    id: UUID
    pedido_id: UUID
    precio_unitario: Decimal