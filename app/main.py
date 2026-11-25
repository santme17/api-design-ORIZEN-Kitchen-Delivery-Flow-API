# app/main.py
"""Punto de entrada de la API de ORIZEN.

Local:   uvicorn app.main:app --reload   y abrir http://127.0.0.1:8000/scalar
Docker:  docker compose up --build       (mismo puerto 8000)

Las tablas las crea Alembic (alembic upgrade head) antes de arrancar.
Las pruebas viven en tests/ y se corren con: pytest -q
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from scalar_fastapi import get_scalar_api_reference
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.database import async_session_maker
from app.core.errors import registrar_manejadores
from app.repositories import UsuarioRepository
from app.routers import api_router
from app.services import AuthService


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Si no hay usuarios, crea el ADMIN del .env para poder hacer el primer login
    async with async_session_maker() as session:
        await AuthService(UsuarioRepository(session)).crear_admin_inicial()
        await session.commit()
    yield


# docs_url/redoc_url en None: la documentación es solo Scalar
app = FastAPI(
    title="ORIZEN - Kitchen & Delivery Flow API",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

# Convierte los IntegrityError de la BD en 409 (en vez de 500)
registrar_manejadores(app)

# CORS: deja que el frontend (otro dominio) llame la API desde el navegador
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Todos los routers quedan bajo /api/v1
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", include_in_schema=False)
async def raiz() -> dict[str, str]:
    return {"api": app.title, "docs": "/scalar", "health": "/health"}


@app.get("/scalar", include_in_schema=False)
async def scalar_docs() -> HTMLResponse:
    """Documentación interactiva con Scalar."""
    return get_scalar_api_reference(openapi_url=app.openapi_url, title=app.title)


@app.get("/health", tags=["Health"])
async def health_check(session: SessionDep) -> JSONResponse:
    """La API responde y la base de datos también (503 si la base no responde)."""
    try:
        await session.execute(text("SELECT 1"))
        base_datos = "ok"
    except Exception:  # noqa: BLE001
        base_datos = "sin conexión"
    sano = base_datos == "ok"
    return JSONResponse(
        status_code=200 if sano else 503,
        content={
            "status": "healthy" if sano else "unhealthy",
            "project": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "database": base_datos,
        },
    )
