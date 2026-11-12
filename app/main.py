# app/main.py
"""
Arnés de pruebas de ORIZEN: Capa 3 (Repositorios) y Capa 4 (Servicios).

Dos formas de ejecutarlo (desde la raíz del proyecto, con el venv activo):

  1) CLI:       python -m app.main                 (repositorios + servicios, SQLite en memoria)
                python -m app.main --servicios     (solo la capa de servicios)
                python -m app.main --repositorios  (solo la capa de repositorios)
                python -m app.main --postgres      (PostgreSQL local del .env)
  2) Endpoint:  uvicorn app.main:app --reload  y abrir http://127.0.0.1:8000/docs
                GET  /test/repositories             (Capa 3)
                POST /test-services                 (Capa 4)
                Ambos aceptan ?db=postgres          (PostgreSQL local del .env)

Cada capa se prueba sobre una base de datos NUEVA, así no dependen entre sí.

Por defecto usa una SQLite EN MEMORIA y desechable: no toca tu .env, tu
fastapi_demo.db ni Neon.

Con --postgres usa DB_TYPE/POSTGRES_URL del .env, pero con dos seguros porque
BORRA y recrea las tablas: el host debe ser localhost y el nombre de la base de
datos debe contener "test" (ej. orizen_test).
"""
import asyncio
import sys
import warnings
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from collections.abc import Awaitable
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI, HTTPException
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.models import (
    ClienteCreate,
    ClienteUpdate,
    CronometroProcesoCreate,
    EstadoPedidoCreate,
    ItemPedidoCreate,
    PedidoAsignarRepartidor,
    PedidoCancelar,
    PedidoCreate,
    PedidoUpdate,
    ProductoCreate,
    ProductoUpdate,
    RepartidorCreate,
    RepartidorUpdate,
    UsuarioCreate,
    UsuarioUpdate,
)
from app.models.enums import (
    EstadoDisponibilidad,
    EstadoOrden,
    EstadoProceso,
    NombreProceso,
    RolUsuario,
    TipoPedido,
)
from app.repositories import (
    ClienteRepository,
    CronometroProcesoRepository,
    EstadoPedidoRepository,
    ItemPedidoRepository,
    PedidoRepository,
    ProductoRepository,
    RepartidorRepository,
    UsuarioRepository,
)
from app.core.security import verify_password
from app.services import (
    ClienteService,
    CronometroProcesoService,
    EstadoPedidoService,
    ItemPedidoService,
    PedidoService,
    ProductoService,
    RepartidorService,
    UsuarioService,
)

# SQLite avisa que no maneja Decimal de forma nativa; en la prueba no importa.
warnings.filterwarnings("ignore", message="Dialect sqlite.*Decimal")

SessionFactory = async_sessionmaker[AsyncSession]


# ==============================================================
# Utilidades de reporte
# ==============================================================


class Reporte:
    """Acumula el resultado de cada comprobación."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def check(self, prueba: str, condicion: bool, detalle: str = "") -> None:
        self.items.append({"prueba": prueba, "ok": bool(condicion), "detalle": detalle})

    def igual(self, prueba: str, obtenido: Any, esperado: Any) -> None:
        self.check(prueba, obtenido == esperado, f"obtenido={obtenido!r}, esperado={esperado!r}")


def _utc(valor: datetime) -> datetime:
    """SQLite devuelve fechas sin zona horaria; se tratan como UTC."""
    return valor if valor.tzinfo is not None else valor.replace(tzinfo=timezone.utc)


# ==============================================================
# Pruebas por repositorio (cada una recibe la fábrica de sesiones,
# el reporte y un diccionario `ctx` para compartir ids entre pruebas)
# ==============================================================


async def prueba_cliente(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    async with factory() as session:
        repo = ClienteRepository(session)

        c = await repo.create(ClienteCreate(nombre="Ana Pérez", telefono="3001112233"))
        ctx["cliente_id"] = c.id
        r.check("Cliente.create asigna id", c.id is not None)
        r.check("Cliente.create genera fecha_registro", c.fecha_registro is not None)

        r.igual("Cliente.get_by_id encuentra", (await repo.get_by_id(c.id)).id, c.id)
        r.check("Cliente.get_by_id inexistente -> None", await repo.get_by_id(9999) is None)

        actualizado = await repo.update(c, ClienteUpdate(telefono="3009998877"))
        r.igual("Cliente.update cambia el campo enviado", actualizado.telefono, "3009998877")
        r.igual("Cliente.update NO toca campos no enviados", actualizado.nombre, "Ana Pérez")

        r.check(
            "Cliente.get_multi(search) encuentra por nombre",
            c.id in [x.id for x in await repo.get_multi(search="ana")],
        )
        r.igual("Cliente.get_multi(search) sin coincidencias", await repo.get_multi(search="zzz"), [])


async def prueba_usuario(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    async with factory() as session:
        repo = UsuarioRepository(session)

        u = await repo.create(
            UsuarioCreate(email="caja@orizen.com", rol=RolUsuario.CAJERO, password="clave12345"),
            password_hash="hash_1",
        )
        ctx["usuario_id"] = u.id
        r.check("Usuario.create asigna id", u.id is not None)
        r.igual("Usuario.create guarda password_hash (no la contraseña)", u.password_hash, "hash_1")

        r.igual("Usuario.get_by_email encuentra", (await repo.get_by_email("caja@orizen.com")).id, u.id)
        r.check("Usuario.get_by_email inexistente -> None", await repo.get_by_email("nadie@x.com") is None)

        u = await repo.update(
            u, UsuarioUpdate(rol=RolUsuario.COCINA, password="nuevaclave1"), password_hash="hash_2"
        )
        r.igual("Usuario.update cambia el rol", u.rol, RolUsuario.COCINA)
        r.igual("Usuario.update guarda el nuevo password_hash", u.password_hash, "hash_2")

        u = await repo.update(u, UsuarioUpdate(activo=True))
        r.igual("Usuario.update sin password conserva el hash", u.password_hash, "hash_2")

        inactivo = await repo.create(
            UsuarioCreate(
                email="inactivo@orizen.com", rol=RolUsuario.ADMIN, password="clave12345", activo=False
            ),
            password_hash="hash_3",
        )
        ids_activos = [x.id for x in await repo.get_multi(only_active=True)]
        r.check("Usuario.get_multi(only_active) incluye activos", u.id in ids_activos)
        r.check("Usuario.get_multi(only_active) excluye inactivos", inactivo.id not in ids_activos)
        r.igual(
            "Usuario.get_multi(rol) filtra por rol",
            [x.id for x in await repo.get_multi(rol=RolUsuario.ADMIN)],
            [inactivo.id],
        )

        # Email duplicado: la base de datos debe rechazarlo (unique=True)
        try:
            await repo.create(
                UsuarioCreate(email="caja@orizen.com", rol=RolUsuario.CAJERO, password="clave12345"),
                password_hash="hash_x",
            )
            r.check("Usuario.create con email duplicado lanza IntegrityError", False)
        except IntegrityError:
            await session.rollback()
            r.check("Usuario.create con email duplicado lanza IntegrityError", True)


async def prueba_producto(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    async with factory() as session:
        repo = ProductoRepository(session)

        p1 = await repo.create(ProductoCreate(nombre="Wok de pollo", precio=Decimal("25000.00")))
        p2 = await repo.create(ProductoCreate(nombre="Arroz frito", precio=Decimal("18000.50")))
        p3 = await repo.create(
            ProductoCreate(nombre="Postre agotado", precio=Decimal("5000.00"), activo=False)
        )
        ctx.update(p1_id=p1.id, p2_id=p2.id)
        r.check("Producto.create asigna ids", None not in (p1.id, p2.id, p3.id))

        r.igual(
            "Producto.get_many_by_ids trae varios en una consulta",
            sorted(x.id for x in await repo.get_many_by_ids([p1.id, p2.id, p1.id])),
            sorted([p1.id, p2.id]),
        )
        r.igual("Producto.get_many_by_ids con lista vacía", await repo.get_many_by_ids([]), [])

        ids_activos = [x.id for x in await repo.get_multi(only_active=True)]
        r.check("Producto.get_multi(only_active) excluye inactivos", p3.id not in ids_activos)
        r.igual(
            "Producto.get_multi(search) es insensible a mayúsculas",
            [x.id for x in await repo.get_multi(search="WOK")],
            [p1.id],
        )

        p3 = await repo.update(p3, ProductoUpdate(nombre="Postre"))
        r.igual("Producto.update cambia el nombre", p3.nombre, "Postre")
        r.igual("Producto.update conserva el precio", p3.precio, Decimal("5000.00"))


async def prueba_repartidor(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    async with factory() as session:
        repo = RepartidorRepository(session)

        r1 = await repo.create(RepartidorCreate(nombre="Carlos", telefono="3111111111", vehiculo="Moto"))
        r2 = await repo.create(RepartidorCreate(nombre="Luis", telefono="3222222222", vehiculo="Bicicleta"))
        ctx["repartidor_id"] = r2.id
        r.igual(
            "Repartidor.create deja DISPONIBLE por defecto", r1.estado_disponibilidad, EstadoDisponibilidad.DISPONIBLE
        )

        r2 = await repo.update(r2, RepartidorUpdate(vehiculo="Bicicleta eléctrica"))
        r.igual("Repartidor.update cambia el vehículo", r2.vehiculo, "Bicicleta eléctrica")

        r.igual(
            "Repartidor.get_available lista a ambos",
            sorted(x.id for x in await repo.get_available()),
            sorted([r1.id, r2.id]),
        )

        await repo.soft_delete(r1)
        r.check("Repartidor.get_by_id oculta al eliminado", await repo.get_by_id(r1.id) is None)
        borrado = await repo.get_by_id(r1.id, include_deleted=True)
        r.check(
            "Repartidor.get_by_id(include_deleted) lo devuelve con deleted_at",
            borrado is not None and borrado.deleted_at is not None,
        )
        r.igual(
            "Repartidor.get_available excluye al eliminado",
            [x.id for x in await repo.get_available()],
            [r2.id],
        )


async def prueba_pedido(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    async with factory() as session:
        pedidos = PedidoRepository(session)
        items = ItemPedidoRepository(session)
        productos = ProductoRepository(session)
        repartidores = RepartidorRepository(session)

        p1 = await productos.get_by_id(ctx["p1_id"])
        p2 = await productos.get_by_id(ctx["p2_id"])
        precios = {p1.id: p1.precio, p2.id: p2.precio}
        total = Decimal(2) * p1.precio + p2.precio  # 68000.50

        pedido_in = PedidoCreate(
            cliente_id=ctx["cliente_id"],
            tipo_pedido=TipoPedido.DOMICILIO,
            direccion_entrega="Calle 10 # 5-20",
            items=[
                ItemPedidoCreate(producto_id=p1.id, cantidad=2),
                ItemPedidoCreate(producto_id=p2.id, cantidad=1),
            ],
        )
        pedido = await pedidos.create(
            pedido_in,
            codigo_orden="ORD-0001",
            total=total,
            precios=precios,
            usuario_id=ctx["usuario_id"],
        )
        ctx["pedido_id"] = pedido.id
        r.check("Pedido.create asigna id", pedido.id is not None)
        r.igual("Pedido.create deja estado_actual EN_COLA", pedido.estado_actual, EstadoOrden.EN_COLA)
        r.igual("Pedido.create guarda el total calculado por el servicio", pedido.total, total)
        r.check("Pedido.create deja repartidor_id en None", pedido.repartidor_id is None)

        detalle = await pedidos.get_with_details(pedido.id)
        r.igual("Pedido.get_with_details carga 2 ítems", len(detalle.items), 2)
        r.igual("Pedido.get_with_details carga 1 estado inicial", len(detalle.estados), 1)
        r.igual("Pedido.get_with_details: estado inicial es EN_COLA", detalle.estados[0].estado, EstadoOrden.EN_COLA)
        r.igual("Pedido.get_with_details: estado inicial registra al usuario", detalle.estados[0].usuario_id, ctx["usuario_id"])
        r.igual("Pedido.get_with_details carga cronómetros vacíos", detalle.cronometros, [])

        lista_items = await items.get_by_pedido(pedido.id)
        r.igual("ItemPedido.get_by_pedido devuelve 2", len(lista_items), 2)
        r.igual("ItemPedido.calcular_total coincide con Pedido.total", await items.calcular_total(pedido.id), total)

        # Regla 7: precio congelado
        await productos.update(p1, ProductoUpdate(precio=Decimal("30000.00")))
        r.igual(
            "Precio congelado: cambiar el producto no altera el total del pedido",
            await items.calcular_total(pedido.id),
            total,
        )

        r.igual("Pedido.get_by_codigo encuentra", (await pedidos.get_by_codigo("ORD-0001")).id, pedido.id)
        r.check("Pedido.get_by_codigo inexistente -> None", await pedidos.get_by_codigo("NO-EXISTE") is None)
        r.check("Pedido.get_multi(estado=EN_COLA) lo incluye", pedido.id in [x.id for x in await pedidos.get_multi(estado=EstadoOrden.EN_COLA)])
        r.igual("Pedido.get_multi(estado=ENTREGADO) vacío", await pedidos.get_multi(estado=EstadoOrden.ENTREGADO), [])
        r.igual("Pedido.get_multi(tipo=RECOGER) vacío", await pedidos.get_multi(tipo_pedido=TipoPedido.RECOGER), [])
        r.check("Pedido.get_multi(cliente_id) lo incluye", pedido.id in [x.id for x in await pedidos.get_multi(cliente_id=ctx["cliente_id"])])

        pedido = await pedidos.update(pedido, PedidoUpdate(direccion_entrega="Carrera 7 # 40-10"))
        r.igual("Pedido.update cambia la dirección", pedido.direccion_entrega, "Carrera 7 # 40-10")

        repartidor = await repartidores.get_by_id(ctx["repartidor_id"])
        pedido = await pedidos.assign_courier(pedido, repartidor)
        r.igual("Pedido.assign_courier asigna el repartidor", pedido.repartidor_id, repartidor.id)
        r.igual("Pedido.assign_courier pasa al repartidor a OCUPADO", repartidor.estado_disponibilidad, EstadoDisponibilidad.OCUPADO)
        r.igual("Pedido.get_by_repartidor lo lista", [x.id for x in await pedidos.get_by_repartidor(repartidor.id)], [pedido.id])

    # Sesión nueva: comprueba que lo anterior quedó realmente guardado en la base de datos
    async with factory() as session:
        guardado = await PedidoRepository(session).get_by_id(ctx["pedido_id"])
        rep = await RepartidorRepository(session).get_by_id(ctx["repartidor_id"])
        r.igual("Persistencia: el repartidor asignado quedó guardado", guardado.repartidor_id, ctx["repartidor_id"])
        r.igual("Persistencia: el repartidor quedó OCUPADO", rep.estado_disponibilidad, EstadoDisponibilidad.OCUPADO)

    # Atomicidad: un código duplicado debe deshacer TODO (pedido, ítems y estado)
    async with factory() as session:
        pedidos = PedidoRepository(session)
        try:
            await pedidos.create(
                pedido_in,
                codigo_orden="ORD-0001",
                total=total,
                precios=precios,
                usuario_id=ctx["usuario_id"],
            )
            r.check("Pedido.create con código duplicado lanza IntegrityError", False)
        except IntegrityError:
            r.check("Pedido.create con código duplicado lanza IntegrityError", True)
        r.igual("Atomicidad: no quedó ningún pedido huérfano", len(await pedidos.get_multi()), 1)


async def prueba_estado_pedido(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    async with factory() as session:
        pedidos = PedidoRepository(session)
        estados = EstadoPedidoRepository(session)

        pedido = await pedidos.get_by_id(ctx["pedido_id"])
        nuevo = await estados.create(
            pedido,
            EstadoPedidoCreate(estado=EstadoOrden.EN_PREPARACION, observacion="Entra al wok"),
            usuario_id=ctx["usuario_id"],
        )
        r.check("EstadoPedido.create asigna id", nuevo.id is not None)
        r.igual("EstadoPedido.create enlaza con el pedido", nuevo.pedido_id, pedido.id)
        r.igual(
            "EstadoPedido.get_by_pedido devuelve el historial en orden",
            [e.estado for e in await estados.get_by_pedido(pedido.id)],
            [EstadoOrden.EN_COLA, EstadoOrden.EN_PREPARACION],
        )
        r.igual("EstadoPedido.get_last devuelve el más reciente", (await estados.get_last(pedido.id)).estado, EstadoOrden.EN_PREPARACION)

    async with factory() as session:  # sesión nueva: ¿quedó guardado en la BD?
        guardado = await PedidoRepository(session).get_by_id(ctx["pedido_id"])
        r.igual(
            "Regla 3: Pedido.estado_actual se actualizó en la misma transacción",
            guardado.estado_actual,
            EstadoOrden.EN_PREPARACION,
        )


async def prueba_cronometro(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    pedido_id = ctx["pedido_id"]

    async with factory() as session:
        repo = CronometroProcesoRepository(session)

        c1 = await repo.create(pedido_id, CronometroProcesoCreate(nombre_proceso=NombreProceso.PREPARACION))
        ctx["cronometro_id"] = c1.id
        r.check("Cronometro.create asigna id", c1.id is not None)
        r.igual("Cronometro.create arranca EN_CURSO", c1.estado_proceso, EstadoProceso.EN_CURSO)
        r.check("Cronometro.create deja timestamp_fin en None", c1.timestamp_fin is None)
        r.igual("Cronometro.get_active lo encuentra", (await repo.get_active(pedido_id, NombreProceso.PREPARACION)).id, c1.id)
        r.check("Cronometro.get_active de otro proceso -> None", await repo.get_active(pedido_id, NombreProceso.EMPAQUETADO) is None)

        c1 = await repo.stop(c1)
        r.igual("Cronometro.stop pasa a COMPLETADO", c1.estado_proceso, EstadoProceso.COMPLETADO)
        r.check("Cronometro.stop llena timestamp_fin", c1.timestamp_fin is not None)
        r.check("Cronometro.stop calcula duracion_segundos >= 0", c1.duracion_segundos is not None and c1.duracion_segundos >= 0)
        r.check("Cronometro.get_active ya no lo devuelve", await repo.get_active(pedido_id, NombreProceso.PREPARACION) is None)

        # Regla 4: tras completarse, el mismo proceso se puede iniciar otra vez...
        c2 = await repo.create(pedido_id, CronometroProcesoCreate(nombre_proceso=NombreProceso.PREPARACION))
        r.check("Regla 4: se puede reiniciar un proceso ya completado", c2.id is not None and c2.id != c1.id)

        # ...y la duración se calcula bien con un fin conocido
        fin = _utc(c2.timestamp_inicio) + timedelta(seconds=90)
        c2 = await repo.stop(c2, timestamp_fin=fin)
        r.igual("Regla 5: duración = fin - inicio (90 s)", c2.duracion_segundos, 90)

        r.igual("Cronometro.get_by_pedido devuelve 2", len(await repo.get_by_pedido(pedido_id)), 2)
        r.igual(
            "Cronometro.get_multi(estado_proceso) filtra",
            len(await repo.get_multi(pedido_id=pedido_id, estado_proceso=EstadoProceso.COMPLETADO)),
            2,
        )
        r.check("Cronometro.get_by_id inexistente -> None", await repo.get_by_id(9999) is None)

    # Regla 4: dos cronómetros activos del mismo proceso deben ser imposibles
    async with factory() as session:
        repo = CronometroProcesoRepository(session)
        await repo.create(pedido_id, CronometroProcesoCreate(nombre_proceso=NombreProceso.EMPAQUETADO))
        try:
            await repo.create(pedido_id, CronometroProcesoCreate(nombre_proceso=NombreProceso.EMPAQUETADO))
            r.check("Regla 4: dos activos del mismo proceso lanzan IntegrityError", False)
        except IntegrityError:
            r.check("Regla 4: dos activos del mismo proceso lanzan IntegrityError", True)


SECCIONES = [
    ("Cliente", prueba_cliente),
    ("Usuario", prueba_usuario),
    ("Producto", prueba_producto),
    ("Repartidor", prueba_repartidor),
    ("Pedido + ItemPedido", prueba_pedido),
    ("EstadoPedido", prueba_estado_pedido),
    ("CronometroProceso", prueba_cronometro),
]


# ==============================================================
# Capa 4 - Pruebas de la capa de SERVICIOS (reglas de negocio)
# Cada servicio recibe sus repositorios por el constructor, todos
# sobre la MISMA sesión (igual que hará la inyección de dependencias).
# ==============================================================


def _servicios(session: AsyncSession) -> SimpleNamespace:
    """Arma todos los servicios sobre una sesión, como lo hará la capa de routers."""
    clientes = ClienteRepository(session)
    usuarios = UsuarioRepository(session)
    productos = ProductoRepository(session)
    repartidores = RepartidorRepository(session)
    pedidos = PedidoRepository(session)
    items = ItemPedidoRepository(session)
    estados = EstadoPedidoRepository(session)
    cronometros = CronometroProcesoRepository(session)
    return SimpleNamespace(
        cliente=ClienteService(clientes),
        usuario=UsuarioService(usuarios),
        producto=ProductoService(productos),
        repartidor=RepartidorService(repartidores, pedidos),
        pedido=PedidoService(pedidos, clientes, productos, repartidores, usuarios),
        item=ItemPedidoService(items, pedidos),
        estado=EstadoPedidoService(estados, pedidos, usuarios, repartidores),
        cronometro=CronometroProcesoService(cronometros, pedidos),
    )


async def _espera_http(r: Reporte, prueba: str, codigo: int, coro: Awaitable[Any]) -> None:
    """Comprueba que el servicio bloquee la operación con el código HTTP esperado."""
    try:
        await coro
        r.check(prueba, False, f"no lanzó HTTPException (esperado {codigo})")
    except HTTPException as exc:
        r.check(
            prueba,
            exc.status_code == codigo,
            f"obtenido={exc.status_code} ({exc.detail}), esperado={codigo}",
        )


async def servicio_usuario(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    async with factory() as session:
        s = _servicios(session).usuario

        u = await s.create(
            UsuarioCreate(email="Caja@Orizen.com", rol=RolUsuario.CAJERO, password="clave12345")
        )
        ctx["usuario_id"] = u.id
        r.igual("UsuarioService.create normaliza el email", u.email, "caja@orizen.com")
        r.check("UsuarioService.create NO guarda la contraseña en claro", u.password_hash != "clave12345")
        r.check("UsuarioService.create guarda un hash verificable", verify_password("clave12345", u.password_hash))

        await _espera_http(
            r, "Regla email único: duplicado (otras mayúsculas) -> 400", 400,
            s.create(UsuarioCreate(email="CAJA@orizen.com", rol=RolUsuario.ADMIN, password="clave12345")),
        )

        otro = await s.create(
            UsuarioCreate(email="cocina@orizen.com", rol=RolUsuario.COCINA, password="clave12345")
        )
        await _espera_http(
            r, "Regla cambio de email: usar el de otro usuario -> 400", 400,
            s.update(otro.id, UsuarioUpdate(email="caja@orizen.com")),
        )
        otro = await s.update(otro.id, UsuarioUpdate(password="otraclave99"))
        r.check("UsuarioService.update re-hashea la contraseña", verify_password("otraclave99", otro.password_hash))

        await _espera_http(r, "UsuarioService.get_by_id(999999) -> 404", 404, s.get_by_id(999999))

        otro = await s.delete(otro.id)
        r.igual("UsuarioService.delete lo desactiva (borrado lógico)", otro.activo, False)
        ctx["usuario_inactivo_id"] = otro.id


async def servicio_cliente(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    async with factory() as session:
        s = _servicios(session).cliente

        c = await s.create(ClienteCreate(nombre="Ana Pérez", telefono="3001112233"))
        ctx["cliente_id"] = c.id
        r.check("ClienteService.create asigna id", c.id is not None)

        await _espera_http(r, "ClienteService.get_by_id(999999) -> 404", 404, s.get_by_id(999999))
        await _espera_http(r, "ClienteService.update(999999) -> 404", 404, s.update(999999, ClienteUpdate(telefono="1")))
        await _espera_http(
            r, "ClienteService.update no deja el nombre vacío -> 400", 400,
            s.update(c.id, ClienteUpdate(nombre="")),
        )
        c = await s.update(c.id, ClienteUpdate(telefono="3009998877"))
        r.igual("ClienteService.update cambia el teléfono", c.telefono, "3009998877")


async def servicio_producto(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    async with factory() as session:
        s = _servicios(session).producto

        p1 = await s.create(ProductoCreate(nombre="Wok de pollo", precio=Decimal("25000.00")))
        p2 = await s.create(ProductoCreate(nombre="Arroz frito", precio=Decimal("18000.50")))
        p3 = await s.create(ProductoCreate(nombre="Rollitos", precio=Decimal("9000.00")))
        ctx.update(p1_id=p1.id, p2_id=p2.id, p3_id=p3.id)
        r.check("ProductoService.create asigna ids", None not in (p1.id, p2.id, p3.id))

        await _espera_http(
            r, "Regla nombre único: ' wok DE pollo ' -> 400", 400,
            s.create(ProductoCreate(nombre=" wok DE pollo ", precio=Decimal("1000"))),
        )
        await _espera_http(
            r, "Regla nombre único al editar -> 400", 400,
            s.update(p2.id, ProductoUpdate(nombre="Wok de pollo")),
        )
        p2 = await s.update(p2.id, ProductoUpdate(nombre="Arroz Frito"))
        r.igual("ProductoService.update permite cambiar mayúsculas de su propio nombre", p2.nombre, "Arroz Frito")

        p3 = await s.delete(p3.id)
        r.igual("ProductoService.delete lo desactiva (borrado lógico)", p3.activo, False)
        await _espera_http(r, "ProductoService.get_by_id(999999) -> 404", 404, s.get_by_id(999999))


async def servicio_repartidor(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    async with factory() as session:
        s = _servicios(session).repartidor

        r1 = await s.create(RepartidorCreate(nombre="Carlos", telefono="3111111111", vehiculo="Moto"))
        r2 = await s.create(RepartidorCreate(nombre="Luis", telefono="3222222222", vehiculo="Bicicleta"))
        ctx.update(repartidor_id=r1.id, repartidor2_id=r2.id)
        r.igual("RepartidorService.create deja DISPONIBLE", r1.estado_disponibilidad, EstadoDisponibilidad.DISPONIBLE)

        await _espera_http(
            r, "Regla: registrar un repartidor OCUPADO -> 400", 400,
            s.create(RepartidorCreate(
                nombre="X", telefono="1", vehiculo="Moto",
                estado_disponibilidad=EstadoDisponibilidad.OCUPADO,
            )),
        )
        await _espera_http(
            r, "Regla: poner OCUPADO a mano -> 400", 400,
            s.update(r1.id, RepartidorUpdate(estado_disponibilidad=EstadoDisponibilidad.OCUPADO)),
        )
        await _espera_http(r, "RepartidorService.get_by_id(999999) -> 404", 404, s.get_by_id(999999))
        await _espera_http(r, "RepartidorService.list_pedidos(999999) -> 404", 404, s.list_pedidos(999999))


async def servicio_pedido(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    async with factory() as session:
        sv = _servicios(session)
        s = sv.pedido

        domicilio = PedidoCreate(
            cliente_id=ctx["cliente_id"],
            tipo_pedido=TipoPedido.DOMICILIO,
            direccion_entrega="Calle 10 # 5-20",
            items=[
                ItemPedidoCreate(producto_id=ctx["p1_id"], cantidad=2),
                ItemPedidoCreate(producto_id=ctx["p2_id"], cantidad=1),
            ],
        )
        p = await s.create(domicilio, usuario_id=ctx["usuario_id"])
        ctx["pedido_id"] = p.id
        r.igual("Regla 6: el servicio calcula el total (2x25000 + 18000.50)", p.total, Decimal("68000.50"))
        r.igual("PedidoService.create deja EN_COLA", p.estado_actual, EstadoOrden.EN_COLA)
        r.check(
            "PedidoService.create genera codigo_orden ORD-AAAAMMDD-XXXXXX",
            p.codigo_orden.startswith("ORD-") and len(p.codigo_orden) == 19,
            p.codigo_orden,
        )
        r.igual(
            "Regla 7: los ítems guardan el precio vigente",
            sorted(i.precio_unitario for i in await sv.item.list_by_pedido(p.id)),
            [Decimal("18000.50"), Decimal("25000.00")],
        )

        def con(**cambios: Any) -> PedidoCreate:
            return domicilio.model_copy(update=cambios)

        await _espera_http(
            r, "Cliente inexistente -> 404", 404,
            s.create(con(cliente_id=999999), usuario_id=ctx["usuario_id"]),
        )
        await _espera_http(
            r, "Producto inexistente -> 404", 404,
            s.create(con(items=[ItemPedidoCreate(producto_id=999999, cantidad=1)]), usuario_id=ctx["usuario_id"]),
        )
        await _espera_http(
            r, "Producto inactivo -> 400", 400,
            s.create(con(items=[ItemPedidoCreate(producto_id=ctx["p3_id"], cantidad=1)]), usuario_id=ctx["usuario_id"]),
        )
        await _espera_http(
            r, "Usuario inactivo no puede crear pedidos -> 400", 400,
            s.create(domicilio, usuario_id=ctx["usuario_inactivo_id"]),
        )
        await _espera_http(
            r, "list_all con fecha_desde > fecha_hasta -> 400", 400,
            s.list_all(fecha_desde=datetime(2026, 2, 1), fecha_hasta=datetime(2026, 1, 1)),
        )

        recoger = await s.create(
            con(tipo_pedido=TipoPedido.RECOGER, direccion_entrega="no aplica"), usuario_id=ctx["usuario_id"]
        )
        ctx["pedido_recoger_id"] = recoger.id
        r.check("Pedido RECOGER no guarda dirección", recoger.direccion_entrega is None)
        await _espera_http(
            r, "Regla 9: dirección en un pedido RECOGER -> 400", 400,
            s.update(recoger.id, PedidoUpdate(direccion_entrega="Calle 1")),
        )
        await _espera_http(
            r, "Regla 9: dejar sin dirección un DOMICILIO -> 400", 400,
            s.update(p.id, PedidoUpdate(direccion_entrega=None)),
        )
        p = await s.update(p.id, PedidoUpdate(direccion_entrega="Carrera 7 # 1-1"))
        r.igual("PedidoService.update cambia la dirección", p.direccion_entrega, "Carrera 7 # 1-1")

        # Regla 8: asignación de repartidor
        await _espera_http(
            r, "Regla 8: repartidor en pedido RECOGER -> 409", 409,
            s.assign_courier(recoger.id, PedidoAsignarRepartidor(repartidor_id=ctx["repartidor_id"])),
        )
        await _espera_http(
            r, "Regla 8: repartidor inexistente -> 404", 404,
            s.assign_courier(p.id, PedidoAsignarRepartidor(repartidor_id=999999)),
        )
        p = await s.assign_courier(p.id, PedidoAsignarRepartidor(repartidor_id=ctx["repartidor_id"]))
        rep = await sv.repartidor.get_by_id(ctx["repartidor_id"])
        r.igual("Regla 8: asignar pasa al repartidor a OCUPADO", rep.estado_disponibilidad, EstadoDisponibilidad.OCUPADO)
        await _espera_http(
            r, "Pedido que ya tiene repartidor -> 409", 409,
            s.assign_courier(p.id, PedidoAsignarRepartidor(repartidor_id=ctx["repartidor2_id"])),
        )

        otro = await s.create(domicilio, usuario_id=ctx["usuario_id"])
        ctx["pedido_sin_repartidor_id"] = otro.id
        await _espera_http(
            r, "Regla 8: repartidor OCUPADO -> 409", 409,
            s.assign_courier(otro.id, PedidoAsignarRepartidor(repartidor_id=ctx["repartidor_id"])),
        )

        # El repartidor con pedido activo queda "bloqueado"
        await _espera_http(
            r, "Repartidor con pedido activo: cambiar disponibilidad -> 409", 409,
            sv.repartidor.update(ctx["repartidor_id"], RepartidorUpdate(estado_disponibilidad=EstadoDisponibilidad.INACTIVO)),
        )
        await _espera_http(
            r, "Repartidor con pedido activo: eliminar -> 409", 409,
            sv.repartidor.delete(ctx["repartidor_id"]),
        )
        r.igual(
            "RepartidorService.list_pedidos lista su pedido",
            [x.id for x in await sv.repartidor.list_pedidos(ctx["repartidor_id"])],
            [p.id],
        )
        await _espera_http(r, "PedidoService.get_by_id(999999) -> 404", 404, s.get_by_id(999999))
        await _espera_http(r, "ItemPedidoService.list_by_pedido(999999) -> 404", 404, sv.item.list_by_pedido(999999))


async def servicio_estado(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    uid = ctx["usuario_id"]

    def nuevo(e: EstadoOrden) -> EstadoPedidoCreate:
        return EstadoPedidoCreate(estado=e)

    async with factory() as session:
        sv = _servicios(session)
        s = sv.estado
        pid = ctx["pedido_id"]  # DOMICILIO con repartidor

        await _espera_http(r, "Regla 1: EN_COLA -> EMPAQUETADO (salto) -> 409", 409, s.create(pid, nuevo(EstadoOrden.EMPAQUETADO), usuario_id=uid))
        await _espera_http(r, "Regla 1: EN_COLA -> EN_COLA -> 409", 409, s.create(pid, nuevo(EstadoOrden.EN_COLA), usuario_id=uid))
        await _espera_http(
            r, "Usuario inactivo no puede cambiar estados -> 400", 400,
            s.create(pid, nuevo(EstadoOrden.EN_PREPARACION), usuario_id=ctx["usuario_inactivo_id"]),
        )
        await _espera_http(r, "Pedido inexistente -> 404", 404, s.create(999999, nuevo(EstadoOrden.EN_PREPARACION), usuario_id=uid))

        await s.create(pid, nuevo(EstadoOrden.EN_PREPARACION), usuario_id=uid)
        await s.create(pid, nuevo(EstadoOrden.EMPAQUETADO), usuario_id=uid)
        await _espera_http(
            r, "DOMICILIO: EMPAQUETADO -> ENTREGADO sin tránsito -> 409", 409,
            s.create(pid, nuevo(EstadoOrden.ENTREGADO), usuario_id=uid),
        )
        await s.create(pid, nuevo(EstadoOrden.EN_TRANSITO), usuario_id=uid)
        await _espera_http(
            r, "Regla 1: CANCELADO después de EN_TRANSITO -> 409", 409,
            s.cancelar(pid, PedidoCancelar(observacion="tarde"), usuario_id=uid),
        )
        await _espera_http(
            r, "Pedido EN_TRANSITO ya no se edita -> 409", 409,
            sv.pedido.update(pid, PedidoUpdate(direccion_entrega="Otra")),
        )
        await s.create(pid, nuevo(EstadoOrden.ENTREGADO), usuario_id=uid)
        await _espera_http(r, "ENTREGADO es final -> 409", 409, s.create(pid, nuevo(EstadoOrden.CANCELADO), usuario_id=uid))
        r.igual(
            "Flujo DOMICILIO completo queda en el historial",
            [e.estado for e in await s.list_by_pedido(pid)],
            [EstadoOrden.EN_COLA, EstadoOrden.EN_PREPARACION, EstadoOrden.EMPAQUETADO, EstadoOrden.EN_TRANSITO, EstadoOrden.ENTREGADO],
        )

        # DOMICILIO sin repartidor no puede salir
        sid = ctx["pedido_sin_repartidor_id"]
        await s.create(sid, nuevo(EstadoOrden.EN_PREPARACION), usuario_id=uid)
        await s.create(sid, nuevo(EstadoOrden.EMPAQUETADO), usuario_id=uid)
        await _espera_http(
            r, "DOMICILIO sin repartidor -> EN_TRANSITO -> 409", 409,
            s.create(sid, nuevo(EstadoOrden.EN_TRANSITO), usuario_id=uid),
        )

        # RECOGER: salta EN_TRANSITO
        rid = ctx["pedido_recoger_id"]
        await s.create(rid, nuevo(EstadoOrden.EN_PREPARACION), usuario_id=uid)
        await s.create(rid, nuevo(EstadoOrden.EMPAQUETADO), usuario_id=uid)
        await _espera_http(r, "RECOGER: EMPAQUETADO -> EN_TRANSITO -> 409", 409, s.create(rid, nuevo(EstadoOrden.EN_TRANSITO), usuario_id=uid))
        e = await s.create(rid, nuevo(EstadoOrden.ENTREGADO), usuario_id=uid)
        r.igual("RECOGER: EMPAQUETADO -> ENTREGADO permitido", e.estado, EstadoOrden.ENTREGADO)

        # Cancelar un pedido con repartidor lo libera
        nuevo_pedido = await sv.pedido.create(
            PedidoCreate(
                cliente_id=ctx["cliente_id"], tipo_pedido=TipoPedido.DOMICILIO, direccion_entrega="Calle 3",
                items=[ItemPedidoCreate(producto_id=ctx["p1_id"], cantidad=1)],
            ),
            usuario_id=uid,
        )
        ctx["pedido_cancelado_id"] = nuevo_pedido.id
        await sv.pedido.assign_courier(nuevo_pedido.id, PedidoAsignarRepartidor(repartidor_id=ctx["repartidor2_id"]))
        cancel = await s.cancelar(nuevo_pedido.id, PedidoCancelar(observacion="Cliente desistió"), usuario_id=uid)
        r.igual("cancelar registra CANCELADO con la observación", (cancel.estado, cancel.observacion), (EstadoOrden.CANCELADO, "Cliente desistió"))

    async with factory() as session:  # sesión nueva: ¿quedó guardado?
        sv = _servicios(session)
        r1 = await sv.repartidor.get_by_id(ctx["repartidor_id"])
        r2 = await sv.repartidor.get_by_id(ctx["repartidor2_id"])
        r.igual("Al ENTREGAR, el repartidor vuelve a DISPONIBLE (persistido)", r1.estado_disponibilidad, EstadoDisponibilidad.DISPONIBLE)
        r.igual("Al CANCELAR, el repartidor vuelve a DISPONIBLE (persistido)", r2.estado_disponibilidad, EstadoDisponibilidad.DISPONIBLE)
        r.igual(
            "Regla 3: estado_actual quedó ENTREGADO",
            (await sv.pedido.get_by_id(ctx["pedido_id"])).estado_actual,
            EstadoOrden.ENTREGADO,
        )


async def servicio_cronometro(factory: SessionFactory, r: Reporte, ctx: dict[str, Any]) -> None:
    async with factory() as session:
        sv = _servicios(session)
        s = sv.cronometro
        pid = ctx["pedido_sin_repartidor_id"]  # DOMICILIO, EMPAQUETADO

        c = await s.create(pid, CronometroProcesoCreate(nombre_proceso=NombreProceso.EMPAQUETADO))
        r.igual("CronometroService.create arranca EN_CURSO", c.estado_proceso, EstadoProceso.EN_CURSO)
        await _espera_http(
            r, "Regla 4: segundo cronómetro activo del mismo proceso -> 409", 409,
            s.create(pid, CronometroProcesoCreate(nombre_proceso=NombreProceso.EMPAQUETADO)),
        )
        await _espera_http(
            r, "TRANSITO en un pedido RECOGER -> 409", 409,
            s.create(ctx["pedido_recoger_id"], CronometroProcesoCreate(nombre_proceso=NombreProceso.TRANSITO)),
        )
        await _espera_http(
            r, "Cronómetro en un pedido CANCELADO -> 409", 409,
            s.create(ctx["pedido_cancelado_id"], CronometroProcesoCreate(nombre_proceso=NombreProceso.PREPARACION)),
        )
        await _espera_http(
            r, "Cronómetro en un pedido inexistente -> 404", 404,
            s.create(999999, CronometroProcesoCreate(nombre_proceso=NombreProceso.PREPARACION)),
        )

        c = await s.stop(c.id)
        r.check(
            "Regla 5: stop calcula la duración en el servidor",
            c.estado_proceso == EstadoProceso.COMPLETADO and c.duracion_segundos is not None,
        )
        await _espera_http(r, "Detener dos veces -> 409", 409, s.stop(c.id))
        await _espera_http(r, "CronometroService.get_by_id(999999) -> 404", 404, s.get_by_id(999999))
        r.igual("list_by_pedido devuelve el cronómetro", len(await s.list_by_pedido(pid)), 1)


SECCIONES_SERVICIOS = [
    ("UsuarioService", servicio_usuario),
    ("ClienteService", servicio_cliente),
    ("ProductoService", servicio_producto),
    ("RepartidorService", servicio_repartidor),
    ("PedidoService + ItemPedidoService", servicio_pedido),
    ("EstadoPedidoService (máquina de estados)", servicio_estado),
    ("CronometroProcesoService", servicio_cronometro),
]


# ==============================================================
# Ejecutor
# ==============================================================


def _crear_engine(usar_postgres: bool) -> AsyncEngine:
    """SQLite en memoria (por defecto) o el PostgreSQL LOCAL configurado en el .env."""
    if not usar_postgres:
        return create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)

    from app.core.config import settings  # import tardío: solo se necesita con --postgres

    if settings.DB_TYPE != "postgres":
        raise ValueError("Pon DB_TYPE=postgres y POSTGRES_URL en tu .env")

    url = make_url(settings.DATABASE_URL)
    if url.host not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError(f"Por seguridad solo se permite localhost (host actual: {url.host!r})")
    if "test" not in (url.database or "").lower():
        raise ValueError(
            f"Por seguridad el nombre de la base debe contener 'test' (actual: {url.database!r})"
        )
    return create_async_engine(url)


async def ejecutar_pruebas(
    usar_postgres: bool = False, secciones: list | None = None
) -> list[dict[str, Any]]:
    """Prepara una BD nueva, corre las secciones indicadas y devuelve el reporte.

    Por defecto corre las de la Capa 3 (SECCIONES); para la Capa 4 se pasa SECCIONES_SERVICIOS.
    """
    reporte = Reporte()
    try:
        engine = _crear_engine(usar_postgres)
    except Exception as exc:  # noqa: BLE001
        reporte.check("Preparar la conexión", False, f"{type(exc).__name__}: {exc}")
        return reporte.items

    # Mismas opciones que app/core/database.py (autoflush=False y expire_on_commit=False)
    factory: SessionFactory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    ctx: dict[str, Any] = {}

    try:
        try:
            async with engine.begin() as conn:
                if usar_postgres:  # empieza siempre desde cero
                    await conn.run_sync(SQLModel.metadata.drop_all)
                await conn.run_sync(SQLModel.metadata.create_all)
            reporte.check("Crear las tablas (create_all)", True)
        except Exception as exc:  # noqa: BLE001
            reporte.check("Crear las tablas (create_all)", False, f"{type(exc).__name__}: {exc}")
            return reporte.items

        for nombre, prueba in secciones or SECCIONES:
            try:
                await prueba(factory, reporte, ctx)
            except Exception as exc:  # noqa: BLE001
                reporte.check(
                    f"{nombre}: la sección terminó sin excepción", False, f"{type(exc).__name__}: {exc}"
                )
    finally:
        await engine.dispose()

    return reporte.items


def resumen(resultados: list[dict[str, Any]]) -> dict[str, int]:
    fallidas = sum(1 for x in resultados if not x["ok"])
    return {"total": len(resultados), "exitosas": len(resultados) - fallidas, "fallidas": fallidas}


# ==============================================================
# Endpoint de prueba (FastAPI)
# ==============================================================

app = FastAPI(title="ORIZEN - Arnés de pruebas (Capa 3 y Capa 4)")


@app.get("/")
async def raiz() -> dict[str, str]:
    return {
        "mensaje": "Arnés de pruebas de ORIZEN",
        "repositorios": "GET /test/repositories",
        "servicios": "POST /test-services",
    }


@app.get("/test/repositories", tags=["Pruebas"])
async def probar_repositorios(db: str = "sqlite") -> dict[str, Any]:
    resultados = await ejecutar_pruebas(usar_postgres=(db == "postgres"))
    return {**resumen(resultados), "resultados": resultados}


@app.post("/test-services", tags=["Pruebas"])
async def probar_servicios(db: str = "sqlite") -> dict[str, Any]:
    resultados = await ejecutar_pruebas(
        usar_postgres=(db == "postgres"), secciones=SECCIONES_SERVICIOS
    )
    res = resumen(resultados)
    mensaje = (
        "Todas las reglas de negocio de la capa de servicios fueron validadas exitosamente"
        if res["fallidas"] == 0
        else "Hay reglas de negocio que fallaron; revisa 'resultados'"
    )
    return {"mensaje": mensaje, **res, "resultados": resultados}


# ==============================================================
# CLI:  python -m app.main
# ==============================================================

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):  # evita errores con emojis en la consola de Windows
        sys.stdout.reconfigure(encoding="utf-8")

    usar_pg = "--postgres" in sys.argv
    destino = "PostgreSQL local (.env)" if usar_pg else "SQLite en memoria"

    capas = []
    if "--servicios" not in sys.argv:
        capas.append(("CAPA 3: REPOSITORIOS", SECCIONES))
    if "--repositorios" not in sys.argv:
        capas.append(("CAPA 4: SERVICIOS (REGLAS DE NEGOCIO)", SECCIONES_SERVICIOS))

    total_fallidas = 0
    for titulo, secciones in capas:
        print("\n" + "=" * 65)
        print(f"[INICIO] PRUEBA DE LA {titulo} - {destino}")
        print("=" * 65 + "\n")
        resultados = asyncio.run(ejecutar_pruebas(usar_postgres=usar_pg, secciones=secciones))

        for x in resultados:
            icono = "✅" if x["ok"] else "❌"
            extra = f"\n      -> {x['detalle']}" if not x["ok"] and x["detalle"] else ""
            print(f"{icono} {x['prueba']}{extra}")

        res = resumen(resultados)
        total_fallidas += res["fallidas"]
        print(f"\nResultado: {res['exitosas']}/{res['total']} correctas, {res['fallidas']} fallidas")

    print("\n" + "=" * 65)
    print("[EXITO] TODO VERIFICADO" if total_fallidas == 0 else f"[FALLO] {total_fallidas} pruebas fallidas")
    print("=" * 65 + "\n")
    sys.exit(1 if total_fallidas else 0)