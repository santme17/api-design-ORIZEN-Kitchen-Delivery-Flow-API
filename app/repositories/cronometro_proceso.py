# app/repositories/cronometro_proceso.py
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.models.common import utcnow
from app.models.cronometro_proceso import CronometroProceso, CronometroProcesoCreate
from app.models.enums import EstadoProceso, NombreProceso


def _con_zona_utc(valor: datetime) -> datetime:
    """SQLite devuelve fechas sin zona horaria; las tratamos como UTC para poder restarlas."""
    return valor if valor.tzinfo is not None else valor.replace(tzinfo=timezone.utc)


class CronometroProcesoRepository:
    """Capa 3 - Acceso a Datos (Repositorio) para CronometroProceso."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ==========================================
    # READ
    # ==========================================

    async def get_by_id(self, cronometro_id: int) -> CronometroProceso | None:
        return await self.session.get(CronometroProceso, cronometro_id)

    async def get_by_pedido(self, pedido_id: int) -> list[CronometroProceso]:
        """GET /orders/:id/process-timers, en orden cronológico."""
        statement = (
            select(CronometroProceso)
            .where(CronometroProceso.pedido_id == pedido_id)
            .order_by(col(CronometroProceso.timestamp_inicio), col(CronometroProceso.id))
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_active(
        self, pedido_id: int, nombre_proceso: NombreProceso
    ) -> CronometroProceso | None:
        """Cronómetro EN_CURSO de ese proceso y pedido (regla 4: solo puede haber uno)."""
        statement = select(CronometroProceso).where(
            CronometroProceso.pedido_id == pedido_id,
            CronometroProceso.nombre_proceso == nombre_proceso,
            col(CronometroProceso.timestamp_fin).is_(None),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        pedido_id: int | None = None,
        nombre_proceso: NombreProceso | None = None,
        estado_proceso: EstadoProceso | None = None,
    ) -> list[CronometroProceso]:
        """GET /process-timers con filtros opcionales (pedido, proceso, estado)."""
        statement = select(CronometroProceso)

        if pedido_id is not None:
            statement = statement.where(CronometroProceso.pedido_id == pedido_id)
        if nombre_proceso is not None:
            statement = statement.where(CronometroProceso.nombre_proceso == nombre_proceso)
        if estado_proceso is not None:
            statement = statement.where(CronometroProceso.estado_proceso == estado_proceso)

        statement = statement.order_by(col(CronometroProceso.id)).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    # ==========================================
    # CREATE
    # ==========================================

    async def create(
        self, pedido_id: int, cronometro_in: CronometroProcesoCreate
    ) -> CronometroProceso:
        """POST /orders/:id/process-timers. `pedido_id` viene de la URL, no del body.

        Si dos peticiones llegan a la vez, el índice único parcial lanza
        IntegrityError: el servicio debe capturarlo y responder 409.
        """
        db_cronometro = CronometroProceso.model_validate(
            cronometro_in, update={"pedido_id": pedido_id}
        )
        try:
            self.session.add(db_cronometro)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(db_cronometro)
        return db_cronometro

    # ==========================================
    # UPDATE (detener)
    # ==========================================

    async def stop(
        self,
        db_cronometro: CronometroProceso,
        *,
        timestamp_fin: datetime | None = None,
    ) -> CronometroProceso:
        """PATCH /process-timers/:id/stop. Cierra el cronómetro y calcula la duración (regla 5)."""
        fin = _con_zona_utc(timestamp_fin or utcnow())
        inicio = _con_zona_utc(db_cronometro.timestamp_inicio)

        db_cronometro.timestamp_fin = fin
        db_cronometro.duracion_segundos = max(0, int((fin - inicio).total_seconds()))
        db_cronometro.estado_proceso = EstadoProceso.COMPLETADO

        self.session.add(db_cronometro)
        await self.session.commit()
        await self.session.refresh(db_cronometro)
        return db_cronometro