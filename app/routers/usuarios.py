# app/routers/usuarios.py
from fastapi import APIRouter, status

from app.api.deps import SoloAdmin, UsuarioServiceDep
from app.models.enums import RolUsuario
from app.models.usuario import UsuarioCreate, UsuarioPublic, UsuarioUpdate

# response_model=UsuarioPublic nunca deja salir el password_hash.
# Solo el ADMIN gestiona cuentas.
router = APIRouter(prefix="/users", tags=["Usuarios"], dependencies=[SoloAdmin])


@router.post(
    "/",
    response_model=UsuarioPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar usuario",
    description="Crea una cuenta del sistema validando que el email no exista.",
)
async def create_usuario(
    usuario_in: UsuarioCreate,
    service: UsuarioServiceDep,
) -> UsuarioPublic:
    return await service.create(usuario_in)


@router.get(
    "/",
    response_model=list[UsuarioPublic],
    summary="Listar usuarios",
    description="Lista paginada de usuarios con filtros opcionales por rol y solo activos.",
)
async def list_usuarios(
    service: UsuarioServiceDep,
    skip: int = 0,
    limit: int = 100,
    rol: RolUsuario | None = None,
    only_active: bool = False,
) -> list[UsuarioPublic]:
    return await service.list_all(skip=skip, limit=limit, rol=rol, only_active=only_active)


@router.get(
    "/{usuario_id}",
    response_model=UsuarioPublic,
    summary="Obtener usuario por ID",
    description="Busca un usuario por ID o devuelve 404 si no existe.",
)
async def get_usuario(
    usuario_id: int,
    service: UsuarioServiceDep,
) -> UsuarioPublic:
    return await service.get_by_id(usuario_id)


@router.patch(
    "/{usuario_id}",
    response_model=UsuarioPublic,
    summary="Actualizar usuario",
    description="Actualiza los campos enviados validando que el nuevo email no esté en uso.",
)
async def update_usuario(
    usuario_id: int,
    usuario_in: UsuarioUpdate,
    service: UsuarioServiceDep,
) -> UsuarioPublic:
    return await service.update(usuario_id, usuario_in)


@router.delete(
    "/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar usuario",
    description="Borrado lógico: el usuario queda inactivo (firma el historial de estados).",
)
async def delete_usuario(
    usuario_id: int,
    service: UsuarioServiceDep,
) -> None:
    await service.delete(usuario_id)
