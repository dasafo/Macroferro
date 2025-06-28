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

# ========================================
# DEPENDENCIAS FUTURAS
# ========================================
# Este módulo crecerá con dependencias adicionales según las necesidades del proyecto:

# Ejemplo de dependencia de autenticación (para implementar en fases posteriores):
# def get_current_user(token: str = Depends(oauth2_scheme)) -> models.User:
#     """
#     Extrae y valida el usuario actual desde el token JWT.
#     """
#     # Lógica de validación de token y extracción de usuario
#     pass

# Ejemplo de dependencia de autorización:
# def get_admin_user(current_user: models.User = Depends(get_current_user)) -> models.User:
#     """
#     Verifica que el usuario actual tenga permisos de administrador.
#     """
#     # Lógica de verificación de permisos
#     pass

# Ejemplo de dependencia de paginación:
# def common_parameters(q: Optional[str] = None, skip: int = 0, limit: int = 100):
#     """
#     Parámetros comunes para endpoints con paginación y búsqueda.
#     """
#     return {"q": q, "skip": skip, "limit": limit}