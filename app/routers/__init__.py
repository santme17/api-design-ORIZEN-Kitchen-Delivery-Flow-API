# app/routers/__init__.py
"""Capa 5 - Agrupa todos los routers en `api_router`.

main.py lo monta bajo /api/v1, así "/" de clientes.py queda en /api/v1/customers/.
Todos los routers, menos /auth, exigen un token válido (get_usuario_actual).
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_usuario_actual
from app.routers.auth import router as auth_router
from app.routers.clientes import router as clientes_router
from app.routers.cronometros_proceso import router as cronometros_proceso_router
from app.routers.estados_pedido import router as estados_pedido_router
from app.routers.items_pedido import router as items_pedido_router
from app.routers.pedidos import router as pedidos_router
from app.routers.productos import router as productos_router
from app.routers.repartidores import router as repartidores_router
from app.routers.reportes import router as reportes_router
from app.routers.usuarios import router as usuarios_router

# Público: solo el login
api_router = APIRouter()
api_router.include_router(auth_router)

# Protegido: sin token válido responde 401
protegido = APIRouter(dependencies=[Depends(get_usuario_actual)])
protegido.include_router(usuarios_router)
protegido.include_router(clientes_router)
protegido.include_router(productos_router)
protegido.include_router(repartidores_router)
protegido.include_router(pedidos_router)
protegido.include_router(items_pedido_router)
protegido.include_router(estados_pedido_router)
protegido.include_router(cronometros_proceso_router)
protegido.include_router(reportes_router)

api_router.include_router(protegido)

__all__ = ["api_router"]
