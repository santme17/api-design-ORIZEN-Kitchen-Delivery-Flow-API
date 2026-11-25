# tests/test_seed.py
"""El script de datos demo crea todo y se puede correr dos veces sin duplicar."""
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registra las tablas)
import app.seed as seed
from app.repositories import ProductoRepository, RepartidorRepository, UsuarioRepository


def test_seed_crea_datos_y_no_duplica(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}", poolclass=NullPool)
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    monkeypatch.setattr(seed, "async_session_maker", fabrica)

    async def flujo() -> tuple[int, int, int]:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        await seed.sembrar()
        await seed.sembrar()  # segunda vez: no debe repetir nada
        async with fabrica() as session:
            usuarios = len(await UsuarioRepository(session).get_multi())
            productos = len(await ProductoRepository(session).get_multi())
            repartidores = len(await RepartidorRepository(session).get_multi())
        await engine.dispose()
        return usuarios, productos, repartidores

    usuarios, productos, repartidores = asyncio.run(flujo())
    assert usuarios == 1 + len(seed.USUARIOS)  # admin + uno por rol
    assert productos == len(seed.PRODUCTOS)
    assert repartidores == len(seed.REPARTIDORES)
