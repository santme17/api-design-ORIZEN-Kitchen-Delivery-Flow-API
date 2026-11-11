# app/services/usuario.py
from fastapi import HTTPException, status

from app.core.security import hash_password
from app.models.enums import RolUsuario
from app.models.usuario import Usuario, UsuarioCreate, UsuarioUpdate
from app.repositories.usuario import UsuarioRepository


class UsuarioService:
    """Capa 4 - Lógica de Negocio para Usuario.

    Reglas:
    - Regla 1 (Unicidad): no se puede registrar un email que ya exista (400).
    - Regla 2 (Cambio de email): el nuevo email no puede pertenecer a otro usuario (400).
    - Regla 3 (Existencia): un id inexistente responde 404.
    - La contraseña se hashea aquí; el repositorio solo recibe el hash.
    - Los usuarios no se borran (firman el historial de estados): se desactivan.
    """

    def __init__(self, usuario_repo: UsuarioRepository) -> None:
        self.usuario_repo = usuario_repo

    async def get_by_id(self, usuario_id: int) -> Usuario:
        usuario = await self.usuario_repo.get_by_id(usuario_id)
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        return usuario

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        rol: RolUsuario | None = None,
        only_active: bool = False,
    ) -> list[Usuario]:
        return await self.usuario_repo.get_multi(
            skip=skip, limit=limit, rol=rol, only_active=only_active
        )

    async def create(self, usuario_in: UsuarioCreate) -> Usuario:
        email = usuario_in.email.strip().lower()
        if await self.usuario_repo.get_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un usuario con el email '{email}'",
            )
        usuario_in.email = email
        return await self.usuario_repo.create(
            usuario_in, password_hash=hash_password(usuario_in.password)
        )

    async def update(self, usuario_id: int, usuario_in: UsuarioUpdate) -> Usuario:
        usuario = await self.get_by_id(usuario_id)

        if usuario_in.email is not None:
            email = usuario_in.email.strip().lower()
            if email != usuario.email:
                existente = await self.usuario_repo.get_by_email(email)
                if existente and existente.id != usuario.id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"El email '{email}' ya está en uso",
                    )
            usuario_in.email = email

        nuevo_hash = hash_password(usuario_in.password) if usuario_in.password else None
        return await self.usuario_repo.update(usuario, usuario_in, password_hash=nuevo_hash)

    async def delete(self, usuario_id: int) -> Usuario:
        """Borrado lógico: deja el usuario inactivo (no puede iniciar sesión)."""
        usuario = await self.get_by_id(usuario_id)
        return await self.usuario_repo.update(usuario, UsuarioUpdate(activo=False))
