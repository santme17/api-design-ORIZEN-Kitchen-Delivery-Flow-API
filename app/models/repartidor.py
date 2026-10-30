# Paso 3: importaciones
from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models.common import TZDateTime, utcnow
from app.models.enums import EstadoDisponibilidad


# Paso 4: clase Base
class RepartidorBase(SQLModel):
    nombre: str = Field(max_length=120)
    telefono: str = Field(max_length=20)
    vehiculo: str = Field(max_length=60)
    estado_disponibilidad: EstadoDisponibilidad = EstadoDisponibilidad.DISPONIBLE


# Paso 5: tabla de base de datos
class Repartidor(RepartidorBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    fecha_registro: datetime = Field(default_factory=utcnow, sa_type=TZDateTime)
    # Soft delete: si tiene fecha, el repartidor está "eliminado"
    deleted_at: datetime | None = Field(default=None, sa_type=TZDateTime)


# Paso 6: DTO de creación
class RepartidorCreate(RepartidorBase):
    pass


# Paso 7: DTO de edición
class RepartidorUpdate(SQLModel):
    nombre: str | None = Field(default=None, max_length=120)
    telefono: str | None = Field(default=None, max_length=20)
    vehiculo: str | None = Field(default=None, max_length=60)
    estado_disponibilidad: EstadoDisponibilidad | None = None


# Paso 8: DTO de respuesta (no expone deleted_at)
class RepartidorPublic(RepartidorBase):
    id: UUID
    fecha_registro: datetime