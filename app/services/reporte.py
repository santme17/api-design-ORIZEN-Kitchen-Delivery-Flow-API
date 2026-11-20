# app/services/reporte.py
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status

from app.core.tiempo import hoy_local, rango_dia_utc
from app.models.enums import EstadoOrden
from app.models.reporte import ProductoVendido, ResumenDia, TiempoProceso
from app.repositories.reporte import ReporteRepository


class ReporteService:
    """Capa 4 - Reportes del negocio.

    Reglas:
    - Si no se envía fecha, se usa HOY en hora de Colombia.
    - Los días se cuentan en hora local (rango_dia_utc), no en UTC.
    - Las ventas excluyen pedidos CANCELADOS.
    - No se aceptan fechas futuras (400).
    """

    def __init__(self, reporte_repo: ReporteRepository) -> None:
        self.reporte_repo = reporte_repo

    def _rango(self, fecha: date | None):
        dia = fecha or hoy_local()
        if dia > hoy_local():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pueden pedir reportes de fechas futuras",
            )
        return dia, *rango_dia_utc(dia)

    async def resumen_dia(self, fecha: date | None = None) -> ResumenDia:
        dia, desde, hasta = self._rango(fecha)
        por_estado = await self.reporte_repo.pedidos_por_estado(desde, hasta)
        ventas, pedidos_validos = await self.reporte_repo.ventas(desde, hasta)
        ticket = (ventas / pedidos_validos) if pedidos_validos else Decimal("0")
        return ResumenDia(
            fecha=dia,
            total_pedidos=sum(por_estado.values()),
            # Todos los estados aparecen, aunque tengan 0
            pedidos_por_estado={e: por_estado.get(e, 0) for e in EstadoOrden},
            ventas=ventas.quantize(Decimal("0.01")),
            ticket_promedio=ticket.quantize(Decimal("0.01")),
        )

    async def tiempos_por_proceso(self, fecha: date | None = None) -> list[TiempoProceso]:
        _, desde, hasta = self._rango(fecha)
        filas = await self.reporte_repo.tiempos_por_proceso(desde, hasta)
        return [
            TiempoProceso(
                nombre_proceso=nombre,
                cantidad=cantidad,
                promedio_segundos=round(float(promedio), 1),
                minimo_segundos=minimo,
                maximo_segundos=maximo,
            )
            for nombre, cantidad, promedio, minimo, maximo in filas
        ]

    async def productos_mas_vendidos(
        self, fecha: date | None = None, limite: int = 5
    ) -> list[ProductoVendido]:
        _, desde, hasta = self._rango(fecha)
        filas = await self.reporte_repo.productos_mas_vendidos(desde, hasta, limite)
        return [
            ProductoVendido(
                producto_id=pid,
                nombre=nombre,
                unidades=unidades,
                ingresos=Decimal(str(ingresos)).quantize(Decimal("0.01")),
            )
            for pid, nombre, unidades, ingresos in filas
        ]
