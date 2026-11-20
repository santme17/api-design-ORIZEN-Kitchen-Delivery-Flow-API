# app/api/deps.py
"""Capa 5 - Inyección de dependencias.

Árbol que arma FastAPI en cada petición:
    get_session  ->  get_*_repository  ->  get_*_service  ->  router

Como la sesión se cachea por petición, todos los repositorios y servicios de
una misma petición comparten la MISMA sesión (y la misma transacción).
"""
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import decode_access_token
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.repositories import (
    ClienteRepository,
    CronometroProcesoRepository,
    EstadoPedidoRepository,
    ItemPedidoRepository,
    PedidoRepository,
    ProductoRepository,
    RepartidorRepository,
    UsuarioRepository,
)
from app.services import (
    AuthService,
    ClienteService,
    CronometroProcesoService,
    EstadoPedidoService,
    ItemPedidoService,
    PedidoService,
    ProductoService,
    RepartidorService,
    UsuarioService,
)

# ==========================================
# Nivel 1: Sesión de base de datos (Core)
# ==========================================

SessionDep = Annotated[AsyncSession, Depends(get_session)]


# ==========================================
# Nivel 2: Fábricas de repositorios (Capa 3)
# ==========================================


def get_cliente_repository(session: SessionDep) -> ClienteRepository:
    return ClienteRepository(session)


def get_usuario_repository(session: SessionDep) -> UsuarioRepository:
    return UsuarioRepository(session)


def get_producto_repository(session: SessionDep) -> ProductoRepository:
    return ProductoRepository(session)


def get_repartidor_repository(session: SessionDep) -> RepartidorRepository:
    return RepartidorRepository(session)


def get_pedido_repository(session: SessionDep) -> PedidoRepository:
    return PedidoRepository(session)


def get_item_pedido_repository(session: SessionDep) -> ItemPedidoRepository:
    return ItemPedidoRepository(session)


def get_estado_pedido_repository(session: SessionDep) -> EstadoPedidoRepository:
    return EstadoPedidoRepository(session)


def get_cronometro_proceso_repository(session: SessionDep) -> CronometroProcesoRepository:
    return CronometroProcesoRepository(session)


ClienteRepoDep = Annotated[ClienteRepository, Depends(get_cliente_repository)]
UsuarioRepoDep = Annotated[UsuarioRepository, Depends(get_usuario_repository)]
ProductoRepoDep = Annotated[ProductoRepository, Depends(get_producto_repository)]
RepartidorRepoDep = Annotated[RepartidorRepository, Depends(get_repartidor_repository)]
PedidoRepoDep = Annotated[PedidoRepository, Depends(get_pedido_repository)]
ItemPedidoRepoDep = Annotated[ItemPedidoRepository, Depends(get_item_pedido_repository)]
EstadoPedidoRepoDep = Annotated[EstadoPedidoRepository, Depends(get_estado_pedido_repository)]
CronometroProcesoRepoDep = Annotated[
    CronometroProcesoRepository, Depends(get_cronometro_proceso_repository)
]


# ==========================================
# Nivel 3: Fábricas de servicios (Capa 4)
# Cada servicio recibe exactamente los repositorios de su constructor.
# ==========================================


def get_cliente_service(cliente_repo: ClienteRepoDep) -> ClienteService:
    return ClienteService(cliente_repo)


def get_usuario_service(usuario_repo: UsuarioRepoDep) -> UsuarioService:
    return UsuarioService(usuario_repo)


def get_producto_service(producto_repo: ProductoRepoDep) -> ProductoService:
    return ProductoService(producto_repo)


def get_repartidor_service(
    repartidor_repo: RepartidorRepoDep,
    pedido_repo: PedidoRepoDep,
) -> RepartidorService:
    return RepartidorService(repartidor_repo=repartidor_repo, pedido_repo=pedido_repo)


def get_pedido_service(
    pedido_repo: PedidoRepoDep,
    cliente_repo: ClienteRepoDep,
    producto_repo: ProductoRepoDep,
    repartidor_repo: RepartidorRepoDep,
    usuario_repo: UsuarioRepoDep,
) -> PedidoService:
    return PedidoService(
        pedido_repo=pedido_repo,
        cliente_repo=cliente_repo,
        producto_repo=producto_repo,
        repartidor_repo=repartidor_repo,
        usuario_repo=usuario_repo,
    )


def get_item_pedido_service(
    item_repo: ItemPedidoRepoDep,
    pedido_repo: PedidoRepoDep,
) -> ItemPedidoService:
    return ItemPedidoService(item_repo=item_repo, pedido_repo=pedido_repo)


def get_estado_pedido_service(
    estado_repo: EstadoPedidoRepoDep,
    pedido_repo: PedidoRepoDep,
    usuario_repo: UsuarioRepoDep,
    repartidor_repo: RepartidorRepoDep,
) -> EstadoPedidoService:
    return EstadoPedidoService(
        estado_repo=estado_repo,
        pedido_repo=pedido_repo,
        usuario_repo=usuario_repo,
        repartidor_repo=repartidor_repo,
    )


def get_cronometro_proceso_service(
    cronometro_repo: CronometroProcesoRepoDep,
    pedido_repo: PedidoRepoDep,
) -> CronometroProcesoService:
    return CronometroProcesoService(cronometro_repo=cronometro_repo, pedido_repo=pedido_repo)


ClienteServiceDep = Annotated[ClienteService, Depends(get_cliente_service)]
UsuarioServiceDep = Annotated[UsuarioService, Depends(get_usuario_service)]
ProductoServiceDep = Annotated[ProductoService, Depends(get_producto_service)]
RepartidorServiceDep = Annotated[RepartidorService, Depends(get_repartidor_service)]
PedidoServiceDep = Annotated[PedidoService, Depends(get_pedido_service)]
ItemPedidoServiceDep = Annotated[ItemPedidoService, Depends(get_item_pedido_service)]
EstadoPedidoServiceDep = Annotated[EstadoPedidoService, Depends(get_estado_pedido_service)]
CronometroProcesoServiceDep = Annotated[
    CronometroProcesoService, Depends(get_cronometro_proceso_service)
]


def get_auth_service(usuario_repo: UsuarioRepoDep) -> AuthService:
    return AuthService(usuario_repo)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


# ==========================================
# Nivel 4: Usuario autenticado (JWT) y roles
# ==========================================

# auto_error=False para responder 401 (y no 403) cuando falta el token
bearer_scheme = HTTPBearer(auto_error=False, description="Token obtenido en POST /auth/login")


async def get_usuario_actual(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    usuario_repo: UsuarioRepoDep,
) -> Usuario:
    """Lee el token del header `Authorization: Bearer <token>` y devuelve el usuario."""
    no_autorizado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o vencido",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credenciales is None:
        raise no_autorizado
    try:
        payload = decode_access_token(credenciales.credentials)
        usuario_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise no_autorizado from None

    usuario = await usuario_repo.get_by_id(usuario_id)
    if not usuario or not usuario.activo:
        raise no_autorizado
    return usuario


UsuarioActualDep = Annotated[Usuario, Depends(get_usuario_actual)]


def requiere_roles(*roles: RolUsuario) -> Any:
    """Dependencia que deja pasar solo a los roles indicados (403 para los demás).

    Uso en un router:  dependencies=[SoloAdmin]
    """

    async def verificar_rol(usuario: UsuarioActualDep) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu rol no tiene permiso para esta acción",
            )
        return usuario

    return Depends(verificar_rol)


SoloAdmin = requiere_roles(RolUsuario.ADMIN)
AdminOCajero = requiere_roles(RolUsuario.ADMIN, RolUsuario.CAJERO)
AdminOCocina = requiere_roles(RolUsuario.ADMIN, RolUsuario.COCINA)
EquipoOperativo = requiere_roles(
    RolUsuario.ADMIN, RolUsuario.COCINA, RolUsuario.REPARTIDOR
)


# ==========================================
# Paginación con tope (evita ?limit=1000000)
# ==========================================

SkipQuery = Annotated[int, Query(ge=0, description="Registros a saltar")]
LimitQuery = Annotated[int, Query(ge=1, le=100, description="Máximo 100 por página")]
