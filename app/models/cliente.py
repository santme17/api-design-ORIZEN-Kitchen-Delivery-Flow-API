# Paso 3: importaciones
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.common import TZDateTime, utcnow

if TYPE_CHECKING:
    from app.models.pedido import Pedido


# Paso 4: clase Base
class ClienteBase(SQLModel):
    nombre: str = Field(max_length=120)
    telefono: str = Field(max_length=20)
    email: str | None = Field(default=None, max_length=255)


# Paso 5: tabla de base de datos
class Cliente(ClienteBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    fecha_registro: datetime = Field(default_factory=utcnow, sa_type=TZDateTime)

    # Relaciones (no son columnas)
    pedidos: list["Pedido"] = Relationship(back_populates="cliente")


# Paso 6: DTO de creación
class ClienteCreate(ClienteBase):
    pass


# Paso 7: DTO de edición
class ClienteUpdate(SQLModel):
    nombre: str | None = Field(default=None, max_length=120)
    telefono: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)


# Paso 8: DTO de respuesta
class ClientePublic(ClienteBase):
    id: int
    fecha_registro: datetime
