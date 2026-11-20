# app/repositories/reporte.py
"""Capa 3 - Consultas de agregación para reportes (solo lectura)."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.models.cronometro_proceso import CronometroProceso
from app.models.enums import EstadoOrden
from app.models.item_pedido import ItemPedido
from app.models.pedido import Pedido
from app.models.producto import Producto


class ReporteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def pedidos_por_estado(self, desde: datetime, hasta: datetime) -> dict[EstadoOrden, int]:
        statement = (
            select(Pedido.estado_actual, func.count())
            .where(Pedido.fecha_creacion >= desde, Pedido.fecha_creacion <= hasta)
            .group_by(Pedido.estado_actual)
        )
        resultado = await self.session.execute(statement)
        return {estado: cantidad for estado, cantidad in resultado.all()}

    async def ventas(self, desde: datetime, hasta: datetime) -> tuple[Decimal, int]:
        """(suma de totales, cantidad) de los pedidos NO cancelados del rango."""
        statement = select(func.coalesce(func.sum(Pedido.total), 0), func.count()).where(
            Pedido.fecha_creacion >= desde,
            Pedido.fecha_creacion <= hasta,
            Pedido.estado_actual != EstadoOrden.CANCELADO,
        )
        suma, cantidad = (await self.session.execute(statement)).one()
        return Decimal(str(suma)), cantidad

    async def tiempos_por_proceso(self, desde: datetime, hasta: datetime) -> list[tuple]:
        """Promedio, mínimo y máximo de duración de los cronómetros COMPLETADOS."""
        duracion = col(CronometroProceso.duracion_segundos)
        statement = (
            select(
                CronometroProceso.nombre_proceso,
                func.count(),
                func.avg(duracion),
                func.min(duracion),
                func.max(duracion),
            )
            .where(
                duracion.is_not(None),
                CronometroProceso.timestamp_inicio >= desde,
                CronometroProceso.timestamp_inicio <= hasta,
            )
            .group_by(CronometroProceso.nombre_proceso)
        )
        return list((await self.session.execute(statement)).all())

    async def productos_mas_vendidos(self, desde: datetime, hasta: datetime, limite: int) -> list[tuple]:
        """Unidades e ingresos por producto (con el precio congelado de cada ítem)."""
        unidades = func.sum(ItemPedido.cantidad)
        statement = (
            select(
                Producto.id,
                Producto.nombre,
                unidades,
                func.sum(ItemPedido.cantidad * ItemPedido.precio_unitario),
            )
            .join(ItemPedido, col(ItemPedido.producto_id) == col(Producto.id))
            .join(Pedido, col(ItemPedido.pedido_id) == col(Pedido.id))
            .where(
                Pedido.fecha_creacion >= desde,
                Pedido.fecha_creacion <= hasta,
                Pedido.estado_actual != EstadoOrden.CANCELADO,
            )
            .group_by(Producto.id, Producto.nombre)
            .order_by(unidades.desc())
            .limit(limite)
        )
        return list((await self.session.execute(statement)).all())
