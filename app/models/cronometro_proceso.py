# Paso 3: importaciones
from datetime import datetime

from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel

from app.models.common import TZDateTime, utcnow
from app.models.enums import EstadoProceso, NombreProceso


# Paso 4: clase Base
class CronometroProcesoBase(SQLModel):
    nombre_proceso: NombreProceso


# Paso 5: tabla de base de datos
class CronometroProceso(CronometroProcesoBase, table=True):
    # Un solo cronómetro activo por proceso y pedido (índice único parcial de PostgreSQL)
    __table_args__ = (
        Index(
            "uq_cronometro_activo",
            "pedido_id",
            "nombre_proceso",
            unique=True,
            postgresql_where=text("timestamp_fin IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    pedido_id: int = Field(foreign_key="pedido.id", index=True)
    estado_proceso: EstadoProceso = Field(default=EstadoProceso.EN_CURSO)
    timestamp_inicio: datetime = Field(default_factory=utcnow, sa_type=TZDateTime)
    timestamp_fin: datetime | None = Field(default=None, sa_type=TZDateTime)
    # Lo calcula el servidor al detener el cronómetro
    duracion_segundos: int | None = Field(default=None, ge=0)


# Paso 6: DTO de creación (pedido_id viene de la URL)
class CronometroProcesoCreate(CronometroProcesoBase):
    pass


# Paso 7: no aplica. Se detiene con PATCH /process-timers/{id}/stop, sin body;
# el servidor llena timestamp_fin, estado_proceso y duracion_segundos.


# Paso 8: DTO de respuesta
class CronometroProcesoPublic(CronometroProcesoBase):
    id: int
    pedido_id: int
    estado_proceso: EstadoProceso
    timestamp_inicio: datetime
    timestamp_fin: datetime | None
    duracion_segundos: int | None