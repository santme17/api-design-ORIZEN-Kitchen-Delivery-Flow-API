# app/services/cronometro_proceso.py
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.models.cronometro_proceso import CronometroProceso, CronometroProcesoCreate
from app.models.enums import EstadoOrden, EstadoProceso, NombreProceso, TipoPedido
from app.models.pedido import Pedido
from app.repositories.cronometro_proceso import CronometroProcesoRepository
from app.repositories.pedido import PedidoRepository

ESTADOS_FINALES = {EstadoOrden.ENTREGADO, EstadoOrden.CANCELADO}


class CronometroProcesoService:
    """Capa 4 - Lógica de Negocio para CronometroProceso.

    Reglas:
    - El pedido debe existir (404) y no estar ENTREGADO ni CANCELADO (409).
    - El proceso TRANSITO solo aplica a pedidos DOMICILIO (409).
    - Regla 4: un solo cronómetro activo por proceso y pedido (409). Se revisa
      antes de insertar y, si dos peticiones llegan a la vez, el índice único
      parcial lanza IntegrityError, que también se traduce a 409.
    - Regla 5: la duración la calcula el servidor al detener; no se detiene dos veces (409).
    """

    def __init__(
        self,
        cronometro_repo: CronometroProcesoRepository,
        pedido_repo: PedidoRepository,
    ) -> None:
        self.cronometro_repo = cronometro_repo
        self.pedido_repo = pedido_repo

    async def get_by_id(self, cronometro_id: int) -> CronometroProceso:
        cronometro = await self.cronometro_repo.get_by_id(cronometro_id)
        if not cronometro:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cronómetro no encontrado",
            )
        return cronometro

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        pedido_id: int | None = None,
        nombre_proceso: NombreProceso | None = None,
        estado_proceso: EstadoProceso | None = None,
    ) -> list[CronometroProceso]:
        """GET /process-timers."""
        return await self.cronometro_repo.get_multi(
            skip=skip,
            limit=limit,
            pedido_id=pedido_id,
            nombre_proceso=nombre_proceso,
            estado_proceso=estado_proceso,
        )

    async def list_by_pedido(self, pedido_id: int) -> list[CronometroProceso]:
        """GET /orders/:id/process-timers."""
        await self._get_pedido(pedido_id)
        return await self.cronometro_repo.get_by_pedido(pedido_id)

    async def create(
        self, pedido_id: int, cronometro_in: CronometroProcesoCreate
    ) -> CronometroProceso:
        """POST /orders/:id/process-timers (iniciar un cronómetro)."""
        pedido = await self._get_pedido(pedido_id)

        if pedido.estado_actual in ESTADOS_FINALES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El pedido está {pedido.estado_actual.value}; no se pueden iniciar cronómetros",
            )
        if (
            cronometro_in.nombre_proceso == NombreProceso.TRANSITO
            and pedido.tipo_pedido != TipoPedido.DOMICILIO
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El proceso TRANSITO solo aplica a pedidos DOMICILIO",
            )
        if await self.cronometro_repo.get_active(pedido_id, cronometro_in.nombre_proceso):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya hay un cronómetro {cronometro_in.nombre_proceso.value} en curso para este pedido",
            )

        try:
            return await self.cronometro_repo.create(pedido_id, cronometro_in)
        except IntegrityError:
            # Carrera: otra petición creó el mismo cronómetro entre la revisión y el INSERT
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya hay un cronómetro {cronometro_in.nombre_proceso.value} en curso para este pedido",
            ) from None

    async def stop(self, cronometro_id: int) -> CronometroProceso:
        """PATCH /process-timers/:id/stop."""
        cronometro = await self.get_by_id(cronometro_id)
        if cronometro.estado_proceso == EstadoProceso.COMPLETADO or cronometro.timestamp_fin:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El cronómetro ya fue detenido",
            )
        return await self.cronometro_repo.stop(cronometro)

    # ==========================================
    # Reglas internas
    # ==========================================

    async def _get_pedido(self, pedido_id: int) -> Pedido:
        pedido = await self.pedido_repo.get_by_id(pedido_id)
        if not pedido:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido no encontrado",
            )
        return pedido
