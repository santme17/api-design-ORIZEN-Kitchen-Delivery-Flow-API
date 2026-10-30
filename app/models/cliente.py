# Paso 3: importaciones
from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models.common import TZDateTime, utcnow


# Paso 4: clase Base
class ClienteBase(SQLModel):
    nombre: str = Field(max_length=120)
    telefono: str = Field(max_length=20)
    email: str | None = Field(default=None, max_length=255)


# Paso 5: tabla de base de datos
class Cliente(ClienteBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    fecha_registro: datetime = Field(default_factory=utcnow, sa_type=TZDateTime)


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
    id: UUID
    fecha_registro: datetime
