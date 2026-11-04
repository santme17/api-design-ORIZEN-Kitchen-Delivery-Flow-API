# Paso 3: importaciones
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.common import TZDateTime, utcnow
from app.models.enums import RolUsuario

if TYPE_CHECKING:
    from app.models.estado_pedido import EstadoPedido


# Paso 4: clase Base (campos compartidos)
class UsuarioBase(SQLModel):
    email: str = Field(max_length=255, unique=True, index=True)
    rol: RolUsuario
    activo: bool = True


# Paso 5: tabla de base de datos
class Usuario(UsuarioBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    password_hash: str
    fecha_registro: datetime = Field(default_factory=utcnow, sa_type=TZDateTime)

    # Relaciones (no son columnas)
    estados: list["EstadoPedido"] = Relationship(back_populates="usuario")


# Paso 6: DTO de creación (recibe la contraseña en claro, nunca se guarda así)
class UsuarioCreate(UsuarioBase):
    password: str = Field(min_length=8, max_length=128)


# Paso 7: DTO de edición (todos los campos opcionales)
class UsuarioUpdate(SQLModel):
    email: str | None = Field(default=None, max_length=255)
    rol: RolUsuario | None = None
    activo: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


# Paso 8: DTO de respuesta (sin password_hash)
class UsuarioPublic(UsuarioBase):
    id: int
    fecha_registro: datetime
