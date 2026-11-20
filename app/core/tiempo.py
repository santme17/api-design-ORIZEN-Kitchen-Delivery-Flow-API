# app/core/tiempo.py
"""Fechas en la zona horaria del negocio (Colombia).

En la BD todo se guarda en UTC. Pero "los pedidos de hoy" se cuentan con la hora
de Bogotá: un pedido de las 8:00 p.m. del 18 de noviembre en Bogotá ya es
19 de noviembre en UTC. Estas funciones convierten un día local en su rango UTC.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings

ZONA_NEGOCIO = ZoneInfo(settings.TIMEZONE)


def hoy_local() -> date:
    """La fecha de hoy en la zona del negocio."""
    return datetime.now(ZONA_NEGOCIO).date()


def rango_dia_utc(dia: date) -> tuple[datetime, datetime]:
    """Primer y último instante (en UTC) del día `dia` hora local.

    Devuelve (inicio, fin) para usar con >= inicio y <= fin.
    """
    inicio_local = datetime.combine(dia, time.min, tzinfo=ZONA_NEGOCIO)
    fin_local = inicio_local + timedelta(days=1) - timedelta(microseconds=1)
    return inicio_local.astimezone(timezone.utc), fin_local.astimezone(timezone.utc)
