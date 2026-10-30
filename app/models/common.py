from datetime import datetime, timezone

from sqlalchemy import DateTime

# Tipo de columna para todas las fechas: timestamp con zona horaria
TZDateTime = DateTime(timezone=True)


def utcnow() -> datetime:
    """Fecha y hora actual en UTC (valor por defecto de las columnas de fecha)."""
    return datetime.now(timezone.utc)