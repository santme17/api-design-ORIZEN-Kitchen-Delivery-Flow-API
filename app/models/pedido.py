# Paso 3: importaciones
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from pydantic import model_validator
from sqlmodel import Field, Relationship, SQLModel

from app.models.common import TZDateTime, utcnow
from app.models.enums import EstadoOrden, TipoPedido
from app.models.item_pedido import ItemPedidoCreate

if TYPE_CHECKING:
    from app.models.cliente import Cliente
    from app.models.repartidor import Repartidor
    from app.models.item_pedido import ItemPedido
    from app.models.estado_pedido import EstadoPedido
    from app.models.cronometro_proceso import CronometroProceso


# Paso 4: clase Base
class PedidoBase(SQLModel):
    cliente_id: int = Field(foreign_key="cliente.id")
    tipo_pedido: TipoPedido
    direccion_entrega: str | None = Field(default=None, max_length=255)


# Paso 5: tabla de base de datos
class Pedido(PedidoBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # Nullable: se asigna después de crear el pedido
    repartidor_id: int | None = Field(default=None, foreign_key="repartidor.id", index=True)
    codigo_orden: str = Field(max_length=20, unique=True, index=True)
    # Copia del último registro de EstadoPedido (se actualiza en la misma transacción)
    estado_actual: EstadoOrden = Field(default=EstadoOrden.EN_COLA)
    # Lo calcula el servidor: suma de cantidad * precio_unitario de los ítems
    total: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=2)
    fecha_creacion: datetime = Field(default_factory=utcnow, sa_type=TZDateTime)

    # Relaciones (no son columnas)
    cliente: Optional["Cliente"] = Relationship(back_populates="pedidos")
    repartidor: Optional["Repartidor"] = Relationship(back_populates="pedidos")
    items: list["ItemPedido"] = Relationship(back_populates="pedido")
    # Historial y cronómetros se devuelven en orden cronológico
    estados: list["EstadoPedido"] = Relationship(
        back_populates="pedido",
        sa_relationship_kwargs={"order_by": "EstadoPedido.fecha_cambio"},
    )
    cronometros: list["CronometroProceso"] = Relationship(
        back_populates="pedido",
        sa_relationship_kwargs={"order_by": "CronometroProceso.timestamp_inicio"},
    )


# Paso 6: DTO de creación (incluye los ítems; total y estado los define el servidor)
class PedidoCreate(PedidoBase):
    items: list[ItemPedidoCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validar_direccion(self):
        if self.tipo_pedido == TipoPedido.DOMICILIO and not self.direccion_entrega:
            raise ValueError("direccion_entrega es obligatoria en pedidos DOMICILIO")
        return self


# Paso 7: DTO de edición
class PedidoUpdate(SQLModel):
    direccion_entrega: str | None = Field(default=None, max_length=255)


# Paso 8: DTO de respuesta
class PedidoPublic(PedidoBase):
    id: int
    repartidor_id: int | None
    codigo_orden: str
    estado_actual: EstadoOrden
    total: Decimal
    fecha_creacion: datetime


# Extras para los endpoints PATCH /orders/{id}/courier y POST /orders/{id}/cancel
class PedidoAsignarRepartidor(SQLModel):
    repartidor_id: int


class PedidoCancelar(SQLModel):
    observacion: str | None = Field(default=None, max_length=255)