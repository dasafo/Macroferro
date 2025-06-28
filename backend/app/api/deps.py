# backend/app/api/deps.py
"""
Módulo de dependencias para FastAPI.

Este archivo centraliza todas las dependencias que pueden ser inyectadas
en los endpoints de la API. Sigue el patrón de Dependency Injection de FastAPI
para promover código reutilizable y testeable.

Principales ventajas de este enfoque:
- Separación de responsabilidades: las dependencias están separadas de la lógica de negocio
- Facilita el testing: se pueden mock fácilmente las dependencias
- Código DRY: evita repetir la misma lógica en múltiples endpoints
- Gestión centralizada de recursos como conexiones de BD, autenticación, etc.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import AsyncSessionLocal
from app.core.config import settings

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependencia de FastAPI para obtener una sesión de base de datos asíncrona.
    Se asegura de que la sesión se cierre siempre después de la petición.
    """
    async with AsyncSessionLocal() as session:
        yield session

def get_settings():
    """
    Dependencia de FastAPI para obtener el objeto de configuración.
    """
    return settings
