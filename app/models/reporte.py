# app/models/reporte.py
"""DTOs de los reportes (no son tablas: se calculan con consultas de agregación)."""
from datetime import date
from decimal import Decimal

from sqlmodel import SQLModel

from app.models.enums import EstadoOrden, NombreProceso


class ResumenDia(SQLModel):
    fecha: date
    total_pedidos: int
    pedidos_por_estado: dict[EstadoOrden, int]
    ventas: Decimal  # suma de pedidos no cancelados
    ticket_promedio: Decimal


class TiempoProceso(SQLModel):
    nombre_proceso: NombreProceso
    cantidad: int
    promedio_segundos: float
    minimo_segundos: int
    maximo_segundos: int


class ProductoVendido(SQLModel):
    producto_id: int
    nombre: str
    unidades: int
    ingresos: Decimal
