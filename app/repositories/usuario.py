# app/repositories/usuario.py
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.models.enums import RolUsuario
from app.models.usuario import Usuario, UsuarioCreate, UsuarioUpdate


class UsuarioRepository:
    """Capa 3 - Acceso a Datos (Repositorio) para Usuario.

    El repositorio NUNCA ve la contraseña en claro como algo que guardar:
    el servicio la hashea y le entrega `password_hash` ya listo.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ==========================================
    # READ
    # ==========================================

    async def get_by_id(self, usuario_id: int) -> Usuario | None:
        return await self.session.get(Usuario, usuario_id)

    async def get_by_email(self, email: str) -> Usuario | None:
        """Usado por el login y por la regla de email único."""
        statement = select(Usuario).where(Usuario.email == email)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        rol: RolUsuario | None = None,
        only_active: bool = False,
    ) -> list[Usuario]:
        statement = select(Usuario)

        if rol is not None:
            statement = statement.where(Usuario.rol == rol)
        if only_active:
            statement = statement.where(col(Usuario.activo).is_(True))

        statement = statement.order_by(col(Usuario.id)).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    # ==========================================
    # CREATE
    # ==========================================

    async def create(self, usuario_in: UsuarioCreate, *, password_hash: str) -> Usuario:
        """Inserta el usuario. `usuario_in.password` se ignora; se guarda `password_hash`."""
        db_usuario = Usuario.model_validate(
            usuario_in, update={"password_hash": password_hash}
        )
        self.session.add(db_usuario)
        await self.session.commit()
        await self.session.refresh(db_usuario)
        return db_usuario

    # ==========================================
    # UPDATE
    # ==========================================

    async def update(
        self,
        db_usuario: Usuario,
        usuario_in: UsuarioUpdate,
        *,
        password_hash: str | None = None,
    ) -> Usuario:
        """Actualización parcial. Si el cliente envió `password`, el servicio
        pasa aquí el nuevo `password_hash`; el campo `password` nunca se asigna al modelo.
        """
        update_data: dict[str, Any] = usuario_in.model_dump(
            exclude_unset=True, exclude={"password"}
        )

        for field, value in update_data.items():
            setattr(db_usuario, field, value)

        if password_hash is not None:
            db_usuario.password_hash = password_hash

        self.session.add(db_usuario)
        await self.session.commit()
        await self.session.refresh(db_usuario)
        return db_usuario
