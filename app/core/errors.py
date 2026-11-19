# app/core/errors.py
"""Manejadores globales de errores.

IntegrityError: cuando dos peticiones chocan al mismo tiempo (ej. el mismo email),
la validación del servicio pasa en ambas y la BD rechaza la segunda. Sin esto,
el cliente recibe un 500; con esto recibe un 409 claro.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("orizen")


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    # El detalle real va al log del servidor, nunca al cliente (puede revelar la BD)
    logger.warning("IntegrityError en %s %s: %s", request.method, request.url.path, exc.orig)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "El registro entra en conflicto con datos existentes (duplicado o referencia inválida)"},
    )


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(IntegrityError, integrity_error_handler)