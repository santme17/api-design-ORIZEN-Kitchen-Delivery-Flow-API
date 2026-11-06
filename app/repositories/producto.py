# app/repositories/producto.py
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.models.producto import Producto, ProductoCreate, ProductoUpdate


class ProductoRepository:
    """Capa 3 - Acceso a Datos (Repositorio) para Producto."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ==========================================
    # READ
    # ==========================================

    async def get_by_id(self, producto_id: int) -> Producto | None:
        return await self.session.get(Producto, producto_id)

    async def get_many_by_ids(self, producto_ids: Sequence[int]) -> list[Producto]:
        """Trae varios productos en UNA consulta (para validar y congelar precios al crear un pedido)."""
        if not producto_ids:
            return []
        statement = select(Producto).where(col(Producto.id).in_(set(producto_ids)))
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        only_active: bool = False,
    ) -> list[Producto]:
        statement = select(Producto)

        if search:
            statement = statement.where(col(Producto.nombre).ilike(f"%{search}%"))
        if only_active:
            statement = statement.where(col(Producto.activo).is_(True))

        statement = statement.order_by(col(Producto.id)).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    # ==========================================
    # CREATE
    # ==========================================

    async def create(self, producto_in: ProductoCreate) -> Producto:
        db_producto = Producto.model_validate(producto_in)
        self.session.add(db_producto)
        await self.session.commit()
        await self.session.refresh(db_producto)
        return db_producto

    # ==========================================
    # UPDATE (Producto no tiene updated_at)
    # ==========================================

    async def update(self, db_producto: Producto, producto_in: ProductoUpdate) -> Producto:
        update_data: dict[str, Any] = producto_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_producto, field, value)

        self.session.add(db_producto)
        await self.session.commit()
        await self.session.refresh(db_producto)
        return db_producto
