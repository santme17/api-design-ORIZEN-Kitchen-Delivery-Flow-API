# app/core/realtime.py
"""Avisos en tiempo real para la pantalla de cocina (WebSocket).

Cada pantalla conectada queda en `gestor`. Cuando un router crea un pedido o
cambia su estado, llama `gestor.publicar(...)` y todas las pantallas reciben el
evento al instante, sin recargar.

Limitación: vive en la memoria de UN proceso. Con varios workers/instancias
hace falta un intermediario (ej. Redis pub/sub).
"""
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("orizen")


class GestorConexiones:
    def __init__(self) -> None:
        self.conexiones: set[WebSocket] = set()

    async def conectar(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.conexiones.add(websocket)

    def desconectar(self, websocket: WebSocket) -> None:
        self.conexiones.discard(websocket)

    async def publicar(self, evento: str, datos: dict[str, Any]) -> None:
        """Envía {"evento": ..., "datos": ...} a todas las pantallas conectadas."""
        mensaje = {"evento": evento, "datos": datos}
        for websocket in list(self.conexiones):
            try:
                await websocket.send_json(mensaje)
            except Exception:  # noqa: BLE001  (pantalla que se cerró sin avisar)
                logger.info("Se quitó una pantalla de cocina desconectada")
                self.desconectar(websocket)


gestor = GestorConexiones()
