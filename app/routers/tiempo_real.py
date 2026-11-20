# app/routers/tiempo_real.py
import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.realtime import gestor
from app.core.security import decode_access_token
from app.models.enums import RolUsuario

# Público a nivel de router: el WebSocket no puede mandar el header Authorization
# desde el navegador, así que el token llega como ?token=<jwt>.
router = APIRouter(tags=["Tiempo real"])

ROLES_PANTALLA = {RolUsuario.ADMIN.value, RolUsuario.COCINA.value, RolUsuario.CAJERO.value}


@router.websocket("/ws/kitchen")
async def pantalla_cocina(websocket: WebSocket, token: str = Query(...)) -> None:
    """Conexión de la pantalla de cocina: recibe `pedido_creado` y `estado_cambiado`."""
    try:
        payload = decode_access_token(token)
    except jwt.InvalidTokenError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if payload.get("rol") not in ROLES_PANTALLA:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await gestor.conectar(websocket)
    try:
        while True:
            # La pantalla no necesita enviar nada; esto mantiene viva la conexión
            await websocket.receive_text()
    except WebSocketDisconnect:
        gestor.desconectar(websocket)
