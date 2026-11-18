# app/routers/cronometros_proceso.py
from fastapi import APIRouter, status

from app.api.deps import CronometroProcesoServiceDep
from app.models.cronometro_proceso import CronometroProcesoCreate, CronometroProcesoPublic
from app.models.enums import EstadoProceso, NombreProceso

# Sin prefix: este recurso vive en dos rutas, /orders/{id}/process-timers
# (anidado al pedido) y /process-timers (el cronómetro por sí solo).
router = APIRouter(tags=["Cronómetros de proceso"])


@router.post(
    "/orders/{pedido_id}/process-timers",
    response_model=CronometroProcesoPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar cronómetro",
    description=(
        "Inicia el cronómetro de un proceso del pedido. 409 si ya hay uno en curso "
        "para ese proceso, si el pedido terminó o si se pide TRANSITO en un pedido RECOGER."
    ),
)
async def create_cronometro(
    pedido_id: int,
    cronometro_in: CronometroProcesoCreate,
    service: CronometroProcesoServiceDep,
) -> CronometroProcesoPublic:
    return await service.create(pedido_id, cronometro_in)


@router.get(
    "/orders/{pedido_id}/process-timers",
    response_model=list[CronometroProcesoPublic],
    summary="Cronómetros de un pedido",
    description="Devuelve los cronómetros del pedido en orden de inicio.",
)
async def list_cronometros_pedido(
    pedido_id: int,
    service: CronometroProcesoServiceDep,
) -> list[CronometroProcesoPublic]:
    return await service.list_by_pedido(pedido_id)


@router.get(
    "/process-timers/",
    response_model=list[CronometroProcesoPublic],
    summary="Listar cronómetros",
    description="Lista paginada de cronómetros con filtros opcionales por pedido, proceso y estado.",
)
async def list_cronometros(
    service: CronometroProcesoServiceDep,
    skip: int = 0,
    limit: int = 100,
    pedido_id: int | None = None,
    nombre_proceso: NombreProceso | None = None,
    estado_proceso: EstadoProceso | None = None,
) -> list[CronometroProcesoPublic]:
    return await service.list_all(
        skip=skip,
        limit=limit,
        pedido_id=pedido_id,
        nombre_proceso=nombre_proceso,
        estado_proceso=estado_proceso,
    )


@router.get(
    "/process-timers/{cronometro_id}",
    response_model=CronometroProcesoPublic,
    summary="Obtener cronómetro por ID",
    description="Busca un cronómetro por ID o devuelve 404 si no existe.",
)
async def get_cronometro(
    cronometro_id: int,
    service: CronometroProcesoServiceDep,
) -> CronometroProcesoPublic:
    return await service.get_by_id(cronometro_id)


@router.patch(
    "/process-timers/{cronometro_id}/stop",
    response_model=CronometroProcesoPublic,
    summary="Detener cronómetro",
    description="Detiene el cronómetro; el servidor calcula la duración (409 si ya estaba detenido).",
)
async def stop_cronometro(
    cronometro_id: int,
    service: CronometroProcesoServiceDep,
) -> CronometroProcesoPublic:
    return await service.stop(cronometro_id)
