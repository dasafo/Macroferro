# backend/app/api/deps.py
"""
Este archivo contiene las dependencias para la API.

Módulo de dependencias para FastAPI.

Este archivo centraliza todas las dependencias que pueden ser inyectadas
en los endpoints de la API. Sigue el patrón de Dependency Injection de FastAPI
para promover código reutilizable y testeable.
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
