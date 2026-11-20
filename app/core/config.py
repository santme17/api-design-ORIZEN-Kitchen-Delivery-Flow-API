from typing import Literal
from pydantic import Field  # import nuevo, arriba de pydantic_settings
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Configuración global de la aplicación cargada desde variables de entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Configuración General (.env)
    PROJECT_NAME: str = "api-design-ORIZEN-Kitchen-Delivery-Flow-API"
    API_V1_STR: str = "/api/v1"
    ECHO_SQL: bool = False

    # Seguridad (JWT). SECRET_KEY se cambia SIEMPRE en el .env (mín. 32 caracteres)
    SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # un turno de trabajo

    # Zona horaria del negocio (para "pedidos de hoy" y reportes por día)
    TIMEZONE: str = "America/Bogota"

    # Orígenes del frontend que pueden llamar la API (CORS)
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Primer administrador: se crea al arrancar si la tabla de usuarios está vacía
    FIRST_ADMIN_EMAIL: str = "admin@orizen.com"
    FIRST_ADMIN_PASSWORD: str = Field(min_length=8)

    # Selección de Base de Datos: "sqlite" o "postgres"
    DB_TYPE: Literal["sqlite", "postgres"] = "sqlite"

    # Cadenas de conexión configurables
    SQLITE_URL: str = "sqlite+aiosqlite:///./fastapi_demo.db"
    POSTGRES_URL: str = ""

    @property
    def DATABASE_URL(self) -> str:
        """Retorna la URL asíncrona adecuada según DB_TYPE adaptando la cadena de Neon."""
        if self.DB_TYPE == "postgres":
            if not self.POSTGRES_URL:
                raise ValueError(
                    "DB_TYPE está configurado como 'postgres' pero POSTGRES_URL no está definida en el .env"
                )
            url = self.POSTGRES_URL
            # Neon entrega 'postgresql://' o 'postgres://'.
            # SQLAlchemy/SQLModel asíncrono requiere el driver 'postgresql+asyncpg://'.
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return _adaptar_parametros_asyncpg(url)
            
        return self.SQLITE_URL

def _adaptar_parametros_asyncpg(url: str) -> str:
    """Adapta la URL de Neon al driver asyncpg.

    Neon entrega '?sslmode=require&channel_binding=require', pero asyncpg no
    acepta esos parámetros (TypeError: unexpected keyword argument 'sslmode').
    - sslmode=require  ->  ssl=require  (misma seguridad: conexión cifrada)
    - channel_binding  ->  se quita (asyncpg lo negocia solo)
    """
    partes = urlsplit(url)
    parametros = []
    for clave, valor in parse_qsl(partes.query, keep_blank_values=True):
        if clave == "sslmode":
            parametros.append(("ssl", valor))
        elif clave != "channel_binding":
            parametros.append((clave, valor))
    return urlunsplit(partes._replace(query=urlencode(parametros)))


# Instancia única reutilizable en toda la aplicación (Singleton)
settings = Settings()