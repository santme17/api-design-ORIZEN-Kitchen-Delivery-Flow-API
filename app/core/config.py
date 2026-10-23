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

    PROJECT_NAME: str = "FastAPI SQLModel API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Selector de base de datos: "sqlite" o "postgres"
    DB_TYPE: Literal["sqlite", "postgres"] = "sqlite"

    # Cadenas de conexión configurables
    SQLITE_URL: str = "sqlite+aiosqlite:///./fastapi_demo.db"
    POSTGRES_URL: str = ""

    ECHO_SQL: bool = False

    @property
    def DATABASE_URL(self) -> str:
        """Retorna la URL asíncrona adecuada según DB_TYPE adaptando la cadena de Neon."""
        if self.DB_TYPE == "postgres" and self.POSTGRES_URL:
            url = self.POSTGRES_URL
            # Neon entrega 'postgresql://' o 'postgres://'.
            # SQLAlchemy asíncrono requiere 'postgresql+asyncpg://'.
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and not url.startswith(
                "postgresql+asyncpg://"
            ):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return self.SQLITE_URL

# Instancia única reutilizable en toda la aplicación (Singleton)
settings = Settings()