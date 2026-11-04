# Paso 9: registrar todas las entidades.
# Importar cada tabla aquí garantiza que SQLModel.metadata las conozca
# (necesario para create_all y para las migraciones de Alembic).
from app.models.cliente import (
    Cliente,
    ClienteCreate,
    ClientePublic,
    ClienteUpdate,
)
from app.models.cronometro_proceso import (
    CronometroProceso,
    CronometroProcesoCreate,
    CronometroProcesoPublic,
)
from app.models.estado_pedido import (
    EstadoPedido,
    EstadoPedidoCreate,
    EstadoPedidoPublic,
)
from app.models.item_pedido import (
    ItemPedido,
    ItemPedidoCreate,
    ItemPedidoPublic,
    ItemPedidoUpdate,
)
from app.models.pedido import (
    Pedido,
    PedidoAsignarRepartidor,
    PedidoCancelar,
    PedidoCreate,
    PedidoPublic,
    PedidoUpdate,
)
from app.models.producto import (
    Producto,
    ProductoCreate,
    ProductoPublic,
    ProductoUpdate,
)
from app.models.repartidor import (
    Repartidor,
    RepartidorCreate,
    RepartidorPublic,
    RepartidorUpdate,
)
from app.models.usuario import (
    Usuario,
    UsuarioCreate,
    UsuarioPublic,
    UsuarioUpdate,
)

__all__ = [
    "Cliente", "ClienteCreate", "ClientePublic", "ClienteUpdate",
    "CronometroProceso", "CronometroProcesoCreate", "CronometroProcesoPublic",
    "EstadoPedido", "EstadoPedidoCreate", "EstadoPedidoPublic",
    "ItemPedido", "ItemPedidoCreate", "ItemPedidoPublic", "ItemPedidoUpdate",
    "Pedido", "PedidoAsignarRepartidor", "PedidoCancelar", "PedidoCreate",
    "PedidoPublic", "PedidoUpdate",
    "Producto", "ProductoCreate", "ProductoPublic", "ProductoUpdate",
    "Repartidor", "RepartidorCreate", "RepartidorPublic", "RepartidorUpdate",
    "Usuario", "UsuarioCreate", "UsuarioPublic", "UsuarioUpdate",
]