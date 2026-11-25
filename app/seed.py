# app/seed.py
"""Datos de demo para presentar ORIZEN.

Crea un usuario por rol, el menú y dos repartidores. Se puede correr varias
veces: lo que ya existe no se repite.

    python -m app.seed                                   (base del .env)
    docker compose exec api python -m app.seed           (base de Docker)

La contraseña de los usuarios demo sale de SEED_PASSWORD (por defecto orizen2026).
"""
import asyncio
import os
from decimal import Decimal

from app.core.config import settings
from app.core.database import async_session_maker
from app.models import ProductoCreate, RepartidorCreate, UsuarioCreate
from app.models.enums import RolUsuario
from app.repositories import (
    PedidoRepository,
    ProductoRepository,
    RepartidorRepository,
    UsuarioRepository,
)
from app.services import ProductoService, RepartidorService, UsuarioService

SEED_PASSWORD = os.getenv("SEED_PASSWORD", "orizen2026")

USUARIOS = [
    ("cajero@orizen.com", RolUsuario.CAJERO),
    ("cocina@orizen.com", RolUsuario.COCINA),
    ("repartidor@orizen.com", RolUsuario.REPARTIDOR),
]

PRODUCTOS = [
    ("Wok de pollo teriyaki", "28000"),
    ("Wok de res con vegetales", "32000"),
    ("Arroz frito especial", "26000"),
    ("Pad thai de camarón", "35000"),
    ("Rollitos primavera (4 und)", "14000"),
    ("Limonada de hierbabuena", "8000"),
]

REPARTIDORES = [
    ("Carlos Gómez", "3001234567", "Moto"),
    ("Laura Ríos", "3109876543", "Bicicleta"),
]


async def sembrar() -> None:
    async with async_session_maker() as session:
        usuarios_repo = UsuarioRepository(session)
        productos_repo = ProductoRepository(session)
        repartidores_repo = RepartidorRepository(session)

        usuarios = UsuarioService(usuarios_repo)
        productos = ProductoService(productos_repo)
        repartidores = RepartidorService(repartidores_repo, PedidoRepository(session))

        # Admin: el mismo del .env (por si la API todavía no ha arrancado)
        admin_email = settings.FIRST_ADMIN_EMAIL.strip().lower()
        if not await usuarios_repo.get_by_email(admin_email):
            await usuarios.create(
                UsuarioCreate(email=admin_email, rol=RolUsuario.ADMIN, password=settings.FIRST_ADMIN_PASSWORD)
            )
            print(f"+ usuario {admin_email} (ADMIN)")

        for email, rol in USUARIOS:
            if await usuarios_repo.get_by_email(email):
                continue
            await usuarios.create(UsuarioCreate(email=email, rol=rol, password=SEED_PASSWORD))
            print(f"+ usuario {email} ({rol.value})")

        existentes = {p.nombre.lower() for p in await productos_repo.get_multi(limit=1000)}
        for nombre, precio in PRODUCTOS:
            if nombre.lower() in existentes:
                continue
            await productos.create(ProductoCreate(nombre=nombre, precio=Decimal(precio)))
            print(f"+ producto {nombre}")

        if not await repartidores_repo.get_multi(limit=1):
            for nombre, telefono, vehiculo in REPARTIDORES:
                await repartidores.create(RepartidorCreate(nombre=nombre, telefono=telefono, vehiculo=vehiculo))
                print(f"+ repartidor {nombre}")

        # Los repositorios solo hacen flush: aquí se guarda todo junto
        await session.commit()

    print("Datos demo listos.")


if __name__ == "__main__":
    asyncio.run(sembrar())
