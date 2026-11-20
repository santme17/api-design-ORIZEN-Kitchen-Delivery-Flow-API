# app/services/auth.py
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.auth import LoginRequest, Token
from app.models.enums import RolUsuario
from app.models.usuario import UsuarioCreate
from app.repositories.usuario import UsuarioRepository


class AuthService:
    """Capa 4 - Autenticación.

    Reglas:
    - Email o contraseña incorrectos -> 401 con el MISMO mensaje (no revela cuál falló).
    - Un usuario inactivo no puede iniciar sesión (401).
    """

    def __init__(self, usuario_repo: UsuarioRepository) -> None:
        self.usuario_repo = usuario_repo

    async def login(self, login_in: LoginRequest) -> Token:
        usuario = await self.usuario_repo.get_by_email(login_in.email.strip().lower())
        if (
            not usuario
            or not usuario.activo
            or not verify_password(login_in.password, usuario.password_hash)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return Token(access_token=create_access_token(usuario.id, usuario.rol.value))

    async def crear_admin_inicial(self) -> None:
        """Si no hay ningún usuario, crea el ADMIN del .env (si no, nadie podría entrar)."""
        if await self.usuario_repo.get_multi(limit=1):
            return
        await self.usuario_repo.create(
            UsuarioCreate(
                email=settings.FIRST_ADMIN_EMAIL.strip().lower(),
                rol=RolUsuario.ADMIN,
                password=settings.FIRST_ADMIN_PASSWORD,
            ),
            password_hash=hash_password(settings.FIRST_ADMIN_PASSWORD),
        )
