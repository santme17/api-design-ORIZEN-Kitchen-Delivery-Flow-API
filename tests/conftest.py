# tests/conftest.py
"""Fixtures de pytest para probar la API por HTTP sin tocar la BD del .env.

Cada prueba usa una SQLite NUEVA en una carpeta temporal y reemplaza get_session
con dependency_overrides (como explica la guía de la capa 5).
"""
import asyncio
from collections.abc import AsyncGenerator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registra las tablas)
from app.core.config import settings
from app.core.database import get_session
from app.core.security import hash_password
from app.main import app
from app.models.enums import RolUsuario
from app.models.usuario import UsuarioCreate
from app.repositories.usuario import UsuarioRepository

API = settings.API_V1_STR
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin12345"


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    async def preparar() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with factory() as session:
            await UsuarioRepository(session).create(
                UsuarioCreate(email=ADMIN_EMAIL, rol=RolUsuario.ADMIN, password=ADMIN_PASSWORD),
                password_hash=hash_password(ADMIN_PASSWORD),
            )
            await session.commit()  # los repositorios solo hacen flush

    asyncio.run(preparar())

    async def get_session_test() -> AsyncGenerator[AsyncSession, None]:
        # Igual que get_session: commit si todo sale bien, rollback si hay error
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = get_session_test
    # Sin "with": no se ejecuta el lifespan, así no se toca la BD del .env
    yield TestClient(app)
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin(client: TestClient) -> dict[str, str]:
    return login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture
def crear_usuario(client: TestClient, admin: dict[str, str]):
    """Crea un usuario con el rol pedido y devuelve sus headers con token."""

    def _crear(rol: str, email: str) -> dict[str, str]:
        r = client.post(f"{API}/users/", headers=admin, json={"email": email, "rol": rol, "password": "clave12345"})
        assert r.status_code == 201, r.text
        return login(client, email, "clave12345")

    return _crear
