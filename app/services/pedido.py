# app/services/pedido.py
import secrets
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status

from app.models.enums import EstadoDisponibilidad, EstadoOrden, TipoPedido
from app.models.pedido import (
    Pedido,
    PedidoAsignarRepartidor,
    PedidoCreate,
    PedidoUpdate,
)
from app.repositories.cliente import ClienteRepository
from app.repositories.pedido import PedidoRepository
from app.repositories.producto import ProductoRepository
from app.repositories.repartidor import RepartidorRepository
from app.repositories.usuario import UsuarioRepository

# Después de salir del restaurante el pedido ya no se puede editar ni reasignar
ESTADOS_NO_EDITABLES = {EstadoOrden.EN_TRANSITO, EstadoOrden.ENTREGADO, EstadoOrden.CANCELADO}


class PedidoService:
    """Capa 4 - Lógica de Negocio para Pedido (servicio coordinador multirrepositorio).

    Reglas:
    - El cliente del pedido debe existir (404).
    - Todos los productos deben existir (404) y estar activos (400).
    - Regla 6: el total lo calcula el servidor (suma de cantidad * precio).
    - Regla 7: el precio de cada ítem se congela con el precio vigente del producto.
    - El servidor genera `codigo_orden` y deja el estado inicial EN_COLA.
    - Regla 8: solo pedidos DOMICILIO tienen repartidor, y solo si está DISPONIBLE (409).
    - Regla 9: un pedido DOMICILIO no puede quedar sin dirección (400).
    - Un pedido EN_TRANSITO, ENTREGADO o CANCELADO ya no se edita (409).
    - Los pedidos no se borran: se cancelan (ver EstadoPedidoService.cancelar).
    """

    def __init__(
        self,
        pedido_repo: PedidoRepository,
        cliente_repo: ClienteRepository,
        producto_repo: ProductoRepository,
        repartidor_repo: RepartidorRepository,
        usuario_repo: UsuarioRepository,
    ) -> None:
        self.pedido_repo = pedido_repo
        self.cliente_repo = cliente_repo
        self.producto_repo = producto_repo
        self.repartidor_repo = repartidor_repo
        self.usuario_repo = usuario_repo

    # ==========================================
    # READ
    # ==========================================

    async def get_by_id(self, pedido_id: int) -> Pedido:
        pedido = await self.pedido_repo.get_by_id(pedido_id)
        if not pedido:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido no encontrado",
            )
        return pedido

    async def get_detail(self, pedido_id: int) -> Pedido:
        """Pedido con ítems, historial y cronómetros ya cargados."""
        pedido = await self.pedido_repo.get_with_details(pedido_id)
        if not pedido:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido no encontrado",
            )
        return pedido

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        estado: EstadoOrden | None = None,
        tipo_pedido: TipoPedido | None = None,
        cliente_id: int | None = None,
        fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
    ) -> list[Pedido]:
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="fecha_desde no puede ser posterior a fecha_hasta",
            )
        return await self.pedido_repo.get_multi(
            skip=skip,
            limit=limit,
            estado=estado,
            tipo_pedido=tipo_pedido,
            cliente_id=cliente_id,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
        )

    # ==========================================
    # CREATE
    # ==========================================

    async def create(self, pedido_in: PedidoCreate, *, usuario_id: int) -> Pedido:
        """POST /orders. `usuario_id` (quien crea el pedido) sale del JWT."""
        # 1. Cliente
        if not await self.cliente_repo.get_by_id(pedido_in.cliente_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El cliente indicado no existe",
            )

        # 2. Usuario que registra el pedido
        usuario = await self.usuario_repo.get_by_id(usuario_id)
        if not usuario or not usuario.activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario que registra el pedido no existe o está inactivo",
            )

        # 3. Productos: existen y están activos (una sola consulta)
        ids = {item.producto_id for item in pedido_in.items}
        productos = {p.id: p for p in await self.producto_repo.get_many_by_ids(list(ids))}

        faltantes = sorted(ids - productos.keys())
        if faltantes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Productos no encontrados: {faltantes}",
            )
        inactivos = sorted(pid for pid, p in productos.items() if not p.activo)
        if inactivos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Productos no disponibles en el menú: {inactivos}",
            )

        # 4. Precio congelado (regla 7) y total calculado en servidor (regla 6)
        precios = {pid: p.precio for pid, p in productos.items()}
        total = sum(
            (Decimal(item.cantidad) * precios[item.producto_id] for item in pedido_in.items),
            Decimal("0"),
        ).quantize(Decimal("0.01"))

        # 5. Un pedido RECOGER no guarda dirección
        if pedido_in.tipo_pedido == TipoPedido.RECOGER:
            pedido_in.direccion_entrega = None

        return await self.pedido_repo.create(
            pedido_in,
            codigo_orden=await self._generar_codigo(),
            total=total,
            precios=precios,
            usuario_id=usuario_id,
        )

    # ==========================================
    # UPDATE
    # ==========================================

    async def update(self, pedido_id: int, pedido_in: PedidoUpdate) -> Pedido:
        """PUT /orders/:id (solo la dirección de entrega)."""
        pedido = await self.get_by_id(pedido_id)
        self._validar_editable(pedido)

        datos = pedido_in.model_dump(exclude_unset=True)
        if "direccion_entrega" in datos:
            if pedido.tipo_pedido == TipoPedido.RECOGER:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Un pedido RECOGER no lleva dirección de entrega",
                )
            if not datos["direccion_entrega"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="direccion_entrega es obligatoria en pedidos DOMICILIO",
                )

        return await self.pedido_repo.update(pedido, pedido_in)

    async def assign_courier(
        self, pedido_id: int, asignar_in: PedidoAsignarRepartidor
    ) -> Pedido:
        """PATCH /orders/:id/courier (regla 8)."""
        pedido = await self.get_by_id(pedido_id)

        if pedido.tipo_pedido != TipoPedido.DOMICILIO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo los pedidos DOMICILIO pueden tener repartidor",
            )
        self._validar_editable(pedido)
        if pedido.repartidor_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El pedido ya tiene un repartidor asignado",
            )

        repartidor = await self.repartidor_repo.get_by_id(asignar_in.repartidor_id)
        if not repartidor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repartidor no encontrado",
            )
        if repartidor.estado_disponibilidad != EstadoDisponibilidad.DISPONIBLE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El repartidor no está disponible ({repartidor.estado_disponibilidad.value})",
            )

        return await self.pedido_repo.assign_courier(pedido, repartidor)

    # ==========================================
    # Reglas internas
    # ==========================================

    @staticmethod
    def _validar_editable(pedido: Pedido) -> None:
        if pedido.estado_actual in ESTADOS_NO_EDITABLES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El pedido está {pedido.estado_actual.value} y ya no se puede modificar",
            )

    async def _generar_codigo(self) -> str:
        """Formato ORD-AAAAMMDD-XXXXXX (19 caracteres, la columna admite 20)."""
        fecha = datetime.now(timezone.utc).strftime("%Y%m%d")
        for _ in range(5):
            codigo = f"ORD-{fecha}-{secrets.token_hex(3).upper()}"
            if not await self.pedido_repo.get_by_codigo(codigo):
                return codigo
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo generar un código de orden único",
        )
