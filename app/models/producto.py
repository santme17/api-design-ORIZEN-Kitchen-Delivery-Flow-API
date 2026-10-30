# Paso 3: importaciones
from decimal import Decimal
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


# Paso 4: clase Base
class ProductoBase(SQLModel):
    nombre: str = Field(max_length=120)
    precio: Decimal = Field(max_digits=10, decimal_places=2, gt=0)
    activo: bool = True


# Paso 5: tabla de base de datos
class Producto(ProductoBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)


# Paso 6: DTO de creación
class ProductoCreate(ProductoBase):
    pass


# Paso 7: DTO de edición
class ProductoUpdate(SQLModel):
    nombre: str | None = Field(default=None, max_length=120)
    precio: Decimal | None = Field(default=None, max_digits=10, decimal_places=2, gt=0)
    activo: bool | None = None


# Paso 8: DTO de respuesta
class ProductoPublic(ProductoBase):
    id: UUID