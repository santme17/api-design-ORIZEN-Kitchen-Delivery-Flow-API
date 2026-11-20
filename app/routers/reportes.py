# app/routers/reportes.py
from datetime import date

from fastapi import APIRouter, Query

from app.api.deps import ReporteServiceDep, SoloAdmin
from app.models.reporte import ProductoVendido, ResumenDia, TiempoProceso

# Solo el ADMIN ve los números del negocio.
router = APIRouter(prefix="/reports", tags=["Reportes"], dependencies=[SoloAdmin])

FechaQuery = Query(default=None, description="Día en hora de Colombia (por defecto: hoy)")


@router.get(
    "/daily-summary",
    response_model=ResumenDia,
    summary="Resumen del día",
    description="Pedidos por estado, ventas (sin cancelados) y ticket promedio.",
)
async def resumen_dia(service: ReporteServiceDep, fecha: date | None = FechaQuery) -> ResumenDia:
    return await service.resumen_dia(fecha)


@router.get(
    "/process-times",
    response_model=list[TiempoProceso],
    summary="Tiempos por proceso",
    description="Promedio, mínimo y máximo (segundos) de cada proceso con cronómetro completado.",
)
async def tiempos_proceso(
    service: ReporteServiceDep, fecha: date | None = FechaQuery
) -> list[TiempoProceso]:
    return await service.tiempos_por_proceso(fecha)


@router.get(
    "/top-products",
    response_model=list[ProductoVendido],
    summary="Productos más vendidos",
    description="Ranking por unidades vendidas en el día (sin pedidos cancelados).",
)
async def top_productos(
    service: ReporteServiceDep,
    fecha: date | None = FechaQuery,
    limite: int = Query(default=5, ge=1, le=20),
) -> list[ProductoVendido]:
    return await service.productos_mas_vendidos(fecha, limite)
