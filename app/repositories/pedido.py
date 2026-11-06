# app/repositories/pedido.py
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import col, select

from app.models.enums import EstadoDisponibilidad, EstadoOrden, TipoPedido
from app.models.estado_pedido import EstadoPedido
from app.models.item_pedido import ItemPedido
from app.models.pedido import Pedido, PedidoCreate, PedidoUpdate
from app.models.repartidor import Repartidor


class PedidoRepository:
    """Capa 3 - Acceso a Datos (Repositorio) para Pedido.

    Los pedidos nunca se borran (se cancelan con un estado), por eso no hay `delete`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ==========================================
    # READ
    # ==========================================

    async def get_by_id(self, pedido_id: int) -> Pedido | None:
        return await self.session.get(Pedido, pedido_id)

    async def get_by_codigo(self, codigo_orden: str) -> Pedido | None:
        statement = select(Pedido).where(Pedido.codigo_orden == codigo_orden)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_with_details(self, pedido_id: int) -> Pedido | None:
        """Pedido con items, estados y cronómetros ya cargados.

        Con AsyncSession NO se pueden leer relaciones "perezosas" (lazy) después:
        hay que cargarlas aquí con selectinload o se obtiene MissingGreenlet.
        """
        statement = (
            select(Pedido)
            .where(Pedido.id == pedido_id)
            .options(
                selectinload(Pedido.items),  # type: ignore[arg-type]
                selectinload(Pedido.estados),  # type: ignore[arg-type]
                selectinload(Pedido.cronometros),  # type: ignore[arg-type]
            )
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        estado: EstadoOrden | None = None,
        tipo_pedido: TipoPedido | None = None,
        cliente_id: int | None = None,
        fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
    ) -> list[Pedido]:
        """GET /orders con filtros opcionales (estado, tipo, cliente y rango de fechas). Más recientes primero."""
        statement = select(Pedido)

        if estado is not None:
            statement = statement.where(Pedido.estado_actual == estado)
        if tipo_pedido is not None:
            statement = statement.where(Pedido.tipo_pedido == tipo_pedido)
        if cliente_id is not None:
            statement = statement.where(Pedido.cliente_id == cliente_id)
        if fecha_desde is not None:
            statement = statement.where(Pedido.fecha_creacion >= fecha_desde)
        if fecha_hasta is not None:
            statement = statement.where(Pedido.fecha_creacion <= fecha_hasta)

        statement = statement.order_by(col(Pedido.id).desc()).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_by_repartidor(
        self,
        repartidor_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        estado: EstadoOrden | None = None,
    ) -> list[Pedido]:
        """GET /couriers/:id/orders."""
        statement = select(Pedido).where(Pedido.repartidor_id == repartidor_id)

        if estado is not None:
            statement = statement.where(Pedido.estado_actual == estado)

        statement = statement.order_by(col(Pedido.id).desc()).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    # ==========================================
    # CREATE (pedido + ítems + estado inicial en UNA transacción)
    # ==========================================

    async def create(
        self,
        pedido_in: PedidoCreate,
        *,
        codigo_orden: str,
        total: Decimal,
        precios: dict[int, Decimal],
        usuario_id: int,
    ) -> Pedido:
        """Persiste el pedido completo de forma atómica.

        El SERVICIO decide y calcula: `codigo_orden`, `total` y `precios`
        ({producto_id: precio vigente}, que se congela en cada ítem).
        `usuario_id` (quien crea el pedido, sale del JWT) es obligatorio porque
        el estado inicial EN_COLA se registra en el historial.
        """
        try:
            db_pedido = Pedido(
                **pedido_in.model_dump(exclude={"items"}),
                codigo_orden=codigo_orden,
                total=total,
                estado_actual=EstadoOrden.EN_COLA,
            )
            self.session.add(db_pedido)
            # flush envía el INSERT sin cerrar la transacción: así db_pedido.id ya existe
            await self.session.flush()

            for item_in in pedido_in.items:
                self.session.add(
                    ItemPedido(
                        pedido_id=db_pedido.id,
                        producto_id=item_in.producto_id,
                        cantidad=item_in.cantidad,
                        precio_unitario=precios[item_in.producto_id],
                    )
                )

            self.session.add(
                EstadoPedido(
                    pedido_id=db_pedido.id,
                    usuario_id=usuario_id,
                    estado=EstadoOrden.EN_COLA,
                )
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(db_pedido)
        return db_pedido

    # ==========================================
    # UPDATE
    # ==========================================

    async def update(self, db_pedido: Pedido, pedido_in: PedidoUpdate) -> Pedido:
        update_data: dict[str, Any] = pedido_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_pedido, field, value)

        self.session.add(db_pedido)
        await self.session.commit()
        await self.session.refresh(db_pedido)
        return db_pedido

    async def assign_courier(
        self, db_pedido: Pedido, db_repartidor: Repartidor
    ) -> Pedido:
        """PATCH /orders/:id/courier. Asigna el repartidor y lo pasa a OCUPADO en la MISMA transacción.

        Las reglas (solo DOMICILIO, repartidor DISPONIBLE) las valida el servicio antes.
        """
        db_pedido.repartidor_id = db_repartidor.id
        db_repartidor.estado_disponibilidad = EstadoDisponibilidad.OCUPADO

        self.session.add(db_pedido)
        self.session.add(db_repartidor)
        await self.session.commit()
        await self.session.refresh(db_pedido)
        return db_pedido
