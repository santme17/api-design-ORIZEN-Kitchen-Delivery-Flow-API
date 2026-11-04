from typing import Literal
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
    API_V1_STR: str = "/api.orizen/v1"
    ECHO_SQL: bool = False

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
            return url
            
        return self.SQLITE_URL

# Instancia única reutilizable en toda la aplicación (Singleton)
settings = Settings()