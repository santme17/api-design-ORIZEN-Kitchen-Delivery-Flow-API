# app/repositories/repartidor.py
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.models.common import utcnow
from app.models.enums import EstadoDisponibilidad
from app.models.repartidor import Repartidor, RepartidorCreate, RepartidorUpdate


class RepartidorRepository:
    """Capa 3 - Acceso a Datos (Repositorio) para Repartidor.

    Soporta borrado lógico: toda lectura ignora los registros con `deleted_at`,
    salvo que se pida explícitamente `include_deleted=True`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ==========================================
    # READ
    # ==========================================

    async def get_by_id(
        self, repartidor_id: int, *, include_deleted: bool = False
    ) -> Repartidor | None:
        statement = select(Repartidor).where(Repartidor.id == repartidor_id)
        if not include_deleted:
            statement = statement.where(col(Repartidor.deleted_at).is_(None))
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        estado: EstadoDisponibilidad | None = None,
    ) -> list[Repartidor]:
        statement = select(Repartidor).where(col(Repartidor.deleted_at).is_(None))

        if estado is not None:
            statement = statement.where(Repartidor.estado_disponibilidad == estado)

        statement = statement.order_by(col(Repartidor.id)).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_available(self) -> list[Repartidor]:
        """Repartidores DISPONIBLES y no eliminados (candidatos para asignar a un pedido)."""
        return await self.get_multi(estado=EstadoDisponibilidad.DISPONIBLE)

    # ==========================================
    # CREATE
    # ==========================================

    async def create(self, repartidor_in: RepartidorCreate) -> Repartidor:
        db_repartidor = Repartidor.model_validate(repartidor_in)
        self.session.add(db_repartidor)
        await self.session.commit()
        await self.session.refresh(db_repartidor)
        return db_repartidor

    # ==========================================
    # UPDATE (Repartidor no tiene updated_at)
    # ==========================================

    async def update(
        self, db_repartidor: Repartidor, repartidor_in: RepartidorUpdate
    ) -> Repartidor:
        update_data: dict[str, Any] = repartidor_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_repartidor, field, value)

        self.session.add(db_repartidor)
        await self.session.commit()
        await self.session.refresh(db_repartidor)
        return db_repartidor

    # ==========================================
    # DELETE (lógico)
    # ==========================================

    async def soft_delete(self, db_repartidor: Repartidor) -> None:
        """Marca al repartidor como eliminado (DELETE /couriers/:id). No borra la fila."""
        db_repartidor.deleted_at = utcnow()
        self.session.add(db_repartidor)
        await self.session.commit()
