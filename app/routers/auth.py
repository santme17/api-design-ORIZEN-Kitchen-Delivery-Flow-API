# app/routers/auth.py
from fastapi import APIRouter

from app.api.deps import AuthServiceDep, UsuarioActualDep
from app.models.auth import LoginRequest, Token
from app.models.usuario import UsuarioPublic

# Único router público: el login no puede pedir token.
router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post(
    "/login",
    response_model=Token,
    summary="Iniciar sesión",
    description="Devuelve un JWT. Envíalo en el header `Authorization: Bearer <token>`.",
)
async def login(login_in: LoginRequest, service: AuthServiceDep) -> Token:
    return await service.login(login_in)


@router.get(
    "/me",
    response_model=UsuarioPublic,
    summary="Usuario actual",
    description="Devuelve el usuario dueño del token.",
)
async def me(usuario: UsuarioActualDep) -> UsuarioPublic:
    return usuario
