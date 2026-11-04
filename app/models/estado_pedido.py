# Paso 3: importaciones
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.common import TZDateTime, utcnow
from app.models.enums import EstadoOrden


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