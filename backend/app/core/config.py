# backend/app/core/config.py

from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """
    Configuración de la aplicación usando Pydantic BaseSettings.
    Variables sensibles desde .env, defaults seguros para el resto.
    """
    # Configuración general del proyecto
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Macroferro API"
    PROJECT_VERSION: str = "0.1.0"

    # Base de datos PostgreSQL - Del .env
    DATABASE_URL: str

    # Redis - Default seguro
    REDIS_HOST: str = "redis"

    # Qdrant - Combinado: algunos del .env, otros defaults
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT_GRPC: int = 6333
    QDRANT_PORT_REST: int = 6334
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "macroferro_products"

    # OpenAI - Del .env (sensibles)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini-2024-07-18"

    # Admin Token - REQUERIDO del .env (sensible)
    ADMIN_TOKEN: str

    # Logging - Defaults seguros
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE_PATH: str = "logs/app.log"
    
    # App Info - Del .env con defaults
    APP_NAME: str = "Macroferro"
    APP_VERSION: str = "1.0.0"
    APP_ENVIRONMENT: str = "development"
    
    # Server - Del .env con defaults
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Rate Limiting - Del .env con defaults
    RATE_LIMIT_DEFAULT: int = 60
    RATE_LIMIT_USER: int = 120
    RATE_LIMIT_ADMIN: int = 300
    
    # Telegram Bot - Opcionales
    telegram_bot_token: Optional[str] = None
    telegram_webhook_url: Optional[str] = None
    telegram_webhook_secret: Optional[str] = None

    # SMTP for emails - From .env
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SENDER_EMAIL: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False

# Instancia global de la configuración
settings = Settings()
