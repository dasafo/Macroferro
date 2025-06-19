# backend/app/core/config.py

from pydantic import PostgresDsn, AnyHttpUrl
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
    # Lee las credenciales y la información del servidor de la base de datos desde variables de entorno.
    # Proporciona valores por defecto para un entorno de desarrollo local si no se definen.
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost") # Valor por defecto si no está en .env
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "password")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "macroferro_db")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    
    # URL de conexión a la base de datos. Pydantic puede validarla si se proporciona.
    DATABASE_URL: Optional[PostgresDsn] = None

    # Redis
    # Configuración para la conexión con el servidor Redis, usado para caché o colas.
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))

    # Qdrant
    # Configuración para el motor de búsqueda de vectores Qdrant.
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT_GRPC: int = int(os.getenv("QDRANT_PORT_GRPC", 6333))
    QDRANT_PORT_REST: int = int(os.getenv("QDRANT_PORT_REST", 6334))
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY") # Si Qdrant está protegido

    # OpenAI
    # Clave de API para utilizar los servicios de OpenAI.
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")

    # Admin Token (para Fase 6)
    # Un token de seguridad para acceder a rutas de administración protegidas.
    ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "supersecretadmintoken")


    # Ensamblar DATABASE_URL
    # Este método es un ejemplo de cómo se podría construir la URL de la base de datos
    # dinámicamente, aunque no está siendo utilizado como un validador de Pydantic.
    def _assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            # Si v es una cadena, se devuelve como está
            return v
        return PostgresDsn.build(
            scheme="postgresql",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            port=str(values.get("POSTGRES_PORT")), # Pydantic espera port como string aquí
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )
    
    # Usar un pre-validador para DATABASE_URL si no se proporciona directamente
    # O simplemente definirlo como una property
    @property
    def ASSEMBLED_DATABASE_URL(self) -> PostgresDsn:
        """
        Construye dinámicamente la URL de conexión a la base de datos PostgreSQL
        a partir de las variables de entorno individuales.
        Esta propiedad asegura que siempre se tenga una URL de conexión válida.
        """
        return str(PostgresDsn.build(
            scheme="postgresql",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=f"/{self.POSTGRES_DB or ''}",
        ))

    class Config:
        # Configuración de Pydantic para el manejo de las settings.
        case_sensitive = True
        # Si vas a usar un archivo .env específicamente para la app (no el de docker-compose)
        # env_file = ".env_app" 
        # env_file_encoding = 'utf-8'

# Se crea una instancia global de la configuración para ser importada en otras partes de la aplicación.
settings = Settings()

# Prueba simple para verificar si las variables se cargan (puedes quitarla después)
#if __name__ == "__main__":
#    print("Configuraciones cargadas:")
#    print(f"  Project Name: {settings.PROJECT_NAME}")
#    print(f"  PostgreSQL Server: {settings.POSTGRES_SERVER}")
#    print(f"  DATABASE_URL: {settings.ASSEMBLED_DATABASE_URL}")
#    print(f"  OpenAI API Key: {'Presente' if settings.OPENAI_API_KEY else 'No presente'}")