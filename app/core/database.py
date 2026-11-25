from collections.abc import AsyncGenerator
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Argumentos de conexión especiales (ej. desactivar statement cache si se usa Neon Pooler)
connect_args: dict[str, Any] = {}
if "neon.tech" in settings.DATABASE_URL and "pooler" in settings.DATABASE_URL:
    connect_args["statement_cache_size"] = 0

# Motor asíncrono compatible con SQLite y Neon PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ECHO_SQL,
    pool_pre_ping=True,
    connect_args=connect_args,
    future=True,
)

# Fábrica de sesiones asíncronas
async_session_maker = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia de FastAPI: una sesión = una transacción por petición (unidad de trabajo).

    Los repositorios solo hacen flush(). Aquí se decide el final:
    - Si la petición terminó bien  -> commit() (se guarda todo junto).
    - Si hubo cualquier error       -> rollback() (no se guarda nada a medias).
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
