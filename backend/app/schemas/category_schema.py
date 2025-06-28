# backend/app/schemas/category_schema.py

"""
Esquemas Pydantic para el modelo Category.

Los esquemas definen la estructura de datos que fluye a través de la API:
- Validación automática de tipos de datos
- Serialización/deserialización JSON
- Documentación automática en OpenAPI/Swagger
- Separación entre modelo de base de datos y API

Patrón de esquemas utilizado:
- CategoryBase: Propiedades comunes compartidas
- CategoryCreate: Para crear nuevas categorías (POST)
- CategoryUpdate: Para actualizar categorías existentes (PUT/PATCH)
- CategoryResponse: Para respuestas de la API (GET)
"""

from typing import Optional, List
from pydantic import BaseModel, ConfigDict

# ========================================
# ESQUEMA BASE
# ========================================

class CategoryBase(BaseModel):
    """Propiedades comunes compartidas entre esquemas de categoría."""
    name: str
    parent_id: Optional[int] = None


# ========================================
# ESQUEMAS PARA OPERACIONES
# ========================================

class CategoryCreate(CategoryBase):
    """Esquema para crear una nueva categoría. El ID se provee externamente."""
    category_id: int


class CategoryUpdate(CategoryBase):
    """Esquema para actualizar una categoría. Todos los campos son opcionales."""
    name: Optional[str] = None
    parent_id: Optional[int] = None


# ========================================
# ESQUEMA DE RESPUESTA
# ========================================

class CategoryResponse(CategoryBase):
    """Esquema para las respuestas de la API al leer categorías."""
    category_id: int
    
    # Para incluir subcategorías anidadas en el futuro:
    # children: List["CategoryResponse"] = []

    model_config = ConfigDict(from_attributes=True)

# ========================================
# RESOLUCIÓN DE REFERENCIAS FUTURAS
# ========================================

# Para manejar la recursividad en la respuesta si mostramos hijos anidados
# Esto se necesitaría si descomentáramos el campo 'children' en CategoryResponse
# CategoryResponse.update_forward_refs()

# Nota: La recursividad en esquemas puede causar problemas de rendimiento
# en categorías con muchos niveles. Para casos complejos, considerar:
# 1. Endpoints separados para obtener hijos: GET /categories/{id}/children
# 2. Parámetros de consulta para controlar profundidad: ?include_children=true&max_depth=2
# 3. Paginación en subcategorías si hay muchas