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

from typing import Generator
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.config import settings

def get_settings():
    """
    Dependencia de FastAPI para obtener el objeto de configuración.
    """
    return settings
