# Paso 3: importaciones
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.common import TZDateTime, utcnow
from app.models.enums import EstadoOrden

if TYPE_CHECKING:
    from app.models.pedido import Pedido
    from app.models.usuario import Usuario


# Paso 4: clase Base
class EstadoPedidoBase(SQLModel):
    estado: EstadoOrden
    observacion: str | None = Field(default=None, max_length=255)


# Paso 5: tabla de base de datos
class EstadoPedido(EstadoPedidoBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    pedido_id: int = Field(foreign_key="pedido.id", index=True)
    # Quién hizo el cambio (sale del JWT, no del body)
    usuario_id: int = Field(foreign_key="usuario.id")
    fecha_cambio: datetime = Field(default_factory=utcnow, sa_type=TZDateTime)

    # Relaciones (no son columnas). Son el otro lado de Pedido.estados y Usuario.estados:
    # sin ellas, back_populates en esas clases rompe la configuración de los mapeos.
    pedido: Optional["Pedido"] = Relationship(back_populates="estados")
    usuario: Optional["Usuario"] = Relationship(back_populates="estados")


# Paso 6: DTO de creación (pedido_id viene de la URL, usuario_id del token)
class EstadoPedidoCreate(EstadoPedidoBase):
    pass


# Paso 7: no aplica. El historial es append-only: no se edita ni se borra.


# Paso 8: DTO de respuesta
class EstadoPedidoPublic(EstadoPedidoBase):
    id: int
    pedido_id: int
    usuario_id: int
    fecha_cambio: datetime
