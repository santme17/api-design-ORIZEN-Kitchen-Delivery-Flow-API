# app/main.py
"""
Arnés de pruebas de la Capa 3 (Repositorios) de ORIZEN.

Dos formas de ejecutarlo (desde la raíz del proyecto, con el venv activo):

  1) CLI:       python -m app.main                 (SQLite en memoria)
                python -m app.main --postgres      (PostgreSQL local del .env)
  2) Endpoint:  uvicorn app.main:app --reload
                GET /test/repositories             (SQLite en memoria)
                GET /test/repositories?db=postgres (PostgreSQL local del .env)

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
from typing import Any

from fastapi import FastAPI
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


async def ejecutar_pruebas(usar_postgres: bool = False) -> list[dict[str, Any]]:
    """Prepara la BD, corre todas las secciones y devuelve el reporte."""
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

        for nombre, prueba in SECCIONES:
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

app = FastAPI(title="ORIZEN - Arnés de pruebas de repositorios")


@app.get("/")
async def raiz() -> dict[str, str]:
    return {"mensaje": "Arnés de pruebas de la Capa 3", "ejecutar": "/test/repositories"}


@app.get("/test/repositories")
async def probar_repositorios(db: str = "sqlite") -> dict[str, Any]:
    resultados = await ejecutar_pruebas(usar_postgres=(db == "postgres"))
    return {**resumen(resultados), "resultados": resultados}


# ==============================================================
# CLI:  python -m app.main
# ==============================================================

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):  # evita errores con emojis en la consola de Windows
        sys.stdout.reconfigure(encoding="utf-8")

    usar_pg = "--postgres" in sys.argv
    destino = "PostgreSQL local (.env)" if usar_pg else "SQLite en memoria"
    print(f"\n=== Pruebas de repositorios ORIZEN ({destino}) ===\n")
    resultados = asyncio.run(ejecutar_pruebas(usar_postgres=usar_pg))

    for x in resultados:
        icono = "✅" if x["ok"] else "❌"
        extra = f"\n      -> {x['detalle']}" if not x["ok"] and x["detalle"] else ""
        print(f"{icono} {x['prueba']}{extra}")

    res = resumen(resultados)
    print(f"\nResultado: {res['exitosas']}/{res['total']} correctas, {res['fallidas']} fallidas\n")
    sys.exit(1 if res["fallidas"] else 0)