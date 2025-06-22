# backend/app/core/config.py

from pydantic import PostgresDsn, AnyHttpUrl, Field
from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

# Cargar variables desde el archivo .env en la raíz del proyecto
# Asumiendo que el script se ejecuta desde la raíz o que .env está en el path
# Si ejecutas `docker-compose run backend ...` .env en la raíz del proyecto será leído por python-dotenv
# Si no, Docker Compose ya inyecta las variables de entorno desde el .env
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
dotenv_path = os.path.join(project_root, ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

class Settings(BaseSettings):
    """
    Configuración de la aplicación
    """
    # Configuración general del proyecto
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Macroferro API"
    PROJECT_VERSION: str = "0.1.0"

    # Base de datos PostgreSQL
    # La URL completa se pasa desde docker-compose.yml
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # Redis
    # La URL completa se pasa desde docker-compose.yml
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")

    # Qdrant
    # Configuración para el motor de búsqueda de vectores Qdrant.
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT_GRPC: int = int(os.getenv("QDRANT_PORT_GRPC", 6333))
    QDRANT_PORT_REST: int = int(os.getenv("QDRANT_PORT_REST", 6334))
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY") # Si Qdrant está protegido
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "macroferro_products")

    # OpenAI
    # Clave de API para utilizar los servicios de OpenAI.
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")

    # Admin Token (para Fase 6)
    # Un token de seguridad para acceder a rutas de administración protegidas.
    ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "supersecretadmintoken")

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Telegram Bot
    telegram_bot_token: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_webhook_url: Optional[str] = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    telegram_webhook_secret: Optional[str] = os.getenv("TELEGRAM_WEBHOOK_SECRET")

    model_config = {
        "env_file": ".env", 
        "extra": "ignore",
        "case_sensitive": False
    }

# Se crea una instancia global de la configuración para ser importada en otras partes de la aplicación.
settings = Settings()

# Prueba simple para verificar si las variables se cargan (puedes quitarla después)
#if __name__ == "__main__":
#    print("Configuraciones cargadas:")
#    print(f"  Project Name: {settings.PROJECT_NAME}")
#    print(f"  PostgreSQL Server: {settings.POSTGRES_SERVER}")
#    print(f"  DATABASE_URL: {settings.ASSEMBLED_DATABASE_URL}")
#    print(f"  OpenAI API Key: {'Presente' if settings.OPENAI_API_KEY else 'No presente'}")