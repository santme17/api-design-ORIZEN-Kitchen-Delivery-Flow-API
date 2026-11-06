# app/repositories/cliente.py
from typing import Any

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.models.cliente import Cliente, ClienteCreate, ClienteUpdate


class ClienteRepository:
    """Capa 3 - Acceso a Datos (Repositorio) para Cliente."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ==========================================
    # READ
    # ==========================================

    async def get_by_id(self, cliente_id: int) -> Cliente | None:
        """Busca un cliente por su clave primaria. Retorna None si no existe."""
        return await self.session.get(Cliente, cliente_id)

    async def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
    ) -> list[Cliente]:
        """Lista paginada. `search` busca por nombre o teléfono (sin importar mayúsculas)."""
        statement = select(Cliente)

        if search:
            patron = f"%{search}%"
            statement = statement.where(
                or_(
                    col(Cliente.nombre).ilike(patron),
                    col(Cliente.telefono).ilike(patron),
                )
            )

        statement = statement.order_by(col(Cliente.id)).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    # ==========================================
    # CREATE
    # ==========================================

    async def create(self, cliente_in: ClienteCreate) -> Cliente:
        db_cliente = Cliente.model_validate(cliente_in)
        self.session.add(db_cliente)
        await self.session.commit()
        await self.session.refresh(db_cliente)
        return db_cliente

    # ==========================================
    # UPDATE (Cliente no tiene updated_at)
    # ==========================================

    async def update(self, db_cliente: Cliente, cliente_in: ClienteUpdate) -> Cliente:
        update_data: dict[str, Any] = cliente_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_cliente, field, value)

        self.session.add(db_cliente)
        await self.session.commit()
        await self.session.refresh(db_cliente)
        return db_cliente
