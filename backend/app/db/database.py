# backend/app/db/database.py

"""
Configuración principal de la base de datos para la aplicación.

Este módulo establece la conexión con PostgreSQL usando SQLAlchemy y define
los componentes básicos que serán utilizados por toda la aplicación:
- Motor de base de datos (engine)
- Fábrica de sesiones (SessionLocal)  
- Clase base para modelos (Base)

La función get_db() se ha movido a app/api/deps.py para seguir las mejores
prácticas de FastAPI y mantener las dependencias separadas de la configuración.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings # Importamos nuestra configuración

# Crear el motor de base de datos asíncrono
engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Crear un sessionmaker asíncrono
# expire_on_commit=False es importante para que los objetos sigan siendo utilizables
# después de que la transacción se haya confirmado.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Clase base declarativa para todos los modelos ORM
# Todos los modelos en models.py heredarán de esta clase
# Proporciona funcionalidad común como metadatos de tabla y mapeo ORM
Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependencia de FastAPI para obtener una sesión de base de datos asíncrona.
    Se asegura de que la sesión se cierre siempre después de la petición.
    """
    async with AsyncSessionLocal() as session:
        yield session
