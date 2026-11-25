# tests/test_unidad_de_trabajo.py
"""Unidad de trabajo: los repositorios hacen flush y get_session decide commit o rollback."""
import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

import app.core.database as database
import app.models  # noqa: F401  (registra las tablas)
from app.models.cliente import ClienteCreate
from app.repositories.cliente import ClienteRepository


@pytest.fixture
def factory(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'uow.db'}", poolclass=NullPool)
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    async def crear_tablas() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    asyncio.run(crear_tablas())
    # get_session usa esta fábrica en vez de la del .env
    monkeypatch.setattr(database, "async_session_maker", fabrica)
    yield fabrica
    asyncio.run(engine.dispose())


async def _contar_clientes(fabrica) -> int:
    async with fabrica() as session:
        return len(await ClienteRepository(session).get_multi())


def test_si_la_peticion_sale_bien_se_guarda(factory):
    async def flujo() -> int:
        gen = database.get_session()
        session = await gen.__anext__()
        await ClienteRepository(session).create(ClienteCreate(nombre="Ana", telefono="300"))
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()  # termina la petición -> commit
        return await _contar_clientes(factory)

    assert asyncio.run(flujo()) == 1


def test_si_hay_un_error_no_se_guarda_nada(factory):
    async def flujo() -> int:
        gen = database.get_session()
        session = await gen.__anext__()
        await ClienteRepository(session).create(ClienteCreate(nombre="Ana", telefono="300"))
        with pytest.raises(RuntimeError):
            await gen.athrow(RuntimeError("falla después del flush"))  # -> rollback
        return await _contar_clientes(factory)

    assert asyncio.run(flujo()) == 0
