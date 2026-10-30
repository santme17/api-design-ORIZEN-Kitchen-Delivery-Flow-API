from enum import Enum


class RolUsuario(str, Enum):
    CAJERO = "CAJERO"
    COCINA = "COCINA"
    REPARTIDOR = "REPARTIDOR"
    ADMIN = "ADMIN"


class EstadoDisponibilidad(str, Enum):
    DISPONIBLE = "DISPONIBLE"
    OCUPADO = "OCUPADO"
    INACTIVO = "INACTIVO"


class TipoPedido(str, Enum):
    DOMICILIO = "DOMICILIO"
    RECOGER = "RECOGER"


class EstadoOrden(str, Enum):
    EN_COLA = "EN_COLA"
    EN_PREPARACION = "EN_PREPARACION"
    EMPAQUETADO = "EMPAQUETADO"
    EN_TRANSITO = "EN_TRANSITO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"


class NombreProceso(str, Enum):
    ESPERA_COLA = "ESPERA_COLA"
    PREPARACION = "PREPARACION"
    EMPAQUETADO = "EMPAQUETADO"
    TRANSITO = "TRANSITO"


class EstadoProceso(str, Enum):
    EN_CURSO = "EN_CURSO"
    COMPLETADO = "COMPLETADO"